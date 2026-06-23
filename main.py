import os
import json
import random
import asyncio
import requests
import hmac
import hashlib
import time
from collections import defaultdict
from datetime import datetime
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

import database as db
import dentidesk
import agent

load_dotenv()

# Variables de entorno de seguridad
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN")
ENV = os.getenv("ENV", "development")
META_APP_SECRET = os.getenv("META_APP_SECRET")

# Configurar esquema Bearer
security = HTTPBearer(auto_error=False)

# Modelos Pydantic para Validación de Entrada
class LoginRequest(BaseModel):
    password: str

class SimulateIncomingRequest(BaseModel):
    phone_number: Optional[str] = "56912345678"
    message: str = Field(..., min_length=1, max_length=2000)
    referral: Optional[str] = None

class BookSlotRequest(BaseModel):
    phone_number: Optional[str] = None
    patient_name: str
    patient_rut: str
    patient_phone: Optional[str] = None
    slot_str: str
    treatment: Optional[str] = "general"
    duration_minutes: int
    notes: Optional[str] = ""

class DeleteBookingRequest(BaseModel):
    slot_str: str

# Almacenamiento en memoria para Rate Limiting
RATE_LIMIT_STORE = defaultdict(list)

def check_rate_limit(identifier: str, max_requests: int = 15, period: int = 60):
    """
    Verifica si un identificador (IP o Teléfono) excede el rate limit.
    Por defecto: Máximo 15 peticiones por minuto.
    """
    now = time.time()
    # Mantener solo las marcas de tiempo dentro del período
    RATE_LIMIT_STORE[identifier] = [t for t in RATE_LIMIT_STORE[identifier] if now - t < period]
    
    if len(RATE_LIMIT_STORE[identifier]) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Límite de peticiones excedido. Inténtelo más tarde."
        )
    RATE_LIMIT_STORE[identifier].append(now)

def audit_log(action: str, ip: str):
    """Registra una acción de auditoría en audit.log y stdout."""
    timestamp = datetime.now().isoformat()
    log_line = f"[{timestamp}] IP: {ip} | Action: {action}\n"
    print(f"[AUDIT] {log_line.strip()}")
    try:
        with open("audit.log", "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Error escribiendo en log de auditoria: {e}")

def validate_admin_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Valida el Bearer Token enviado en las cabeceras contra ADMIN_API_TOKEN."""
    if not ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_API_TOKEN no está configurado en el servidor"
        )
    if not credentials or credentials.credentials != ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Token de autorización inválido o faltante"
        )
    return credentials.credentials

# Inicialización Condicional de FastAPI para Deshabilitar Documentación en Producción
if ENV == "production":
    app = FastAPI(
        title="Plaza Dent AI Agent Service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None
    )
else:
    app = FastAPI(title="Plaza Dent AI Agent Service")

# Middleware para Agregar Cabeceras de Seguridad y Ocultar/Normalizar Servidor
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com;"
    )
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Server"] = "Hidden"
    return response

# Habilitar CORS para cuando desarrollemos el Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de WhatsApp
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "plazadent_secret_token")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

def send_whatsapp_message(to: str, text: str):
    """Envía un mensaje de WhatsApp real o simula el envío si no hay credenciales."""
    # Evitar usar las credenciales de plantilla/placeholder
    has_real_credentials = (
        WHATSAPP_TOKEN and 
        PHONE_NUMBER_ID and 
        "tu_token" not in WHATSAPP_TOKEN and 
        "tu_phone" not in PHONE_NUMBER_ID
    )
    if has_real_credentials:
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        try:
            r = requests.post(url, json=payload, headers=headers)
            r.raise_for_status()
            print(f"[WHATSAPP SENT] Real message sent to {to}")
            return True
        except Exception as e:
            print(f"[WHATSAPP ERROR] Failed to send message: {e}")
            if 'r' in locals():
                print(f"Response: {r.text}")
            return False
    else:
        # Modo simulación (Logs de consola) - Evitar caídas por emojis en Windows
        try:
            print(f"\n==================================================")
            print(f"[MOCK WHATSAPP SEND] Para: {to}")
            print(f"Mensaje: {text}")
            print(f"==================================================\n")
        except UnicodeEncodeError:
            clean_text = text.encode('ascii', 'ignore').decode('ascii')
            print(f"\n==================================================")
            print(f"[MOCK WHATSAPP SEND] Para: {to}")
            print(f"Mensaje (Sin Emojis): {clean_text}")
            print(f"==================================================\n")
        return True

async def outbox_worker_loop():
    """Bucle continuo en segundo plano para procesar la cola de mensajes salientes (outbox)."""
    print("Iniciando Worker de Outbox en segundo plano...")
    while True:
        try:
            pending = db.get_pending_messages()
            for msg in pending:
                success = send_whatsapp_message(msg["phone_number"], msg["content"])
                if success:
                    db.mark_message_status(msg["id"], "sent")
                    # Registrar respuesta del asistente en el historial del chat
                    db.add_chat_message(msg["phone_number"], "assistant", msg["content"])
                else:
                    db.mark_message_status(msg["id"], "failed")
        except Exception as e:
            print(f"[WORKER ERROR] Error en outbox loop: {e}")
            
        await asyncio.sleep(3) # Revisar cada 3 segundos

@app.on_event("startup")
async def startup_event():
    # Lanzar el worker como tarea de fondo asíncrona
    asyncio.create_task(outbox_worker_loop())

# --- ENDPOINTS DE WHATSAPP WEBHOOK ---

@app.get("/webhook")
def verify_webhook(request: Request):
    """Verificación de webhook requerida por Meta/Facebook."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook verificado con éxito!")
            return Response(content=challenge, media_type="text/plain")
        else:
            raise HTTPException(status_code=403, detail="Verification token mismatch")
    return "Servicio Webhook de Plaza Dent"

@app.post("/webhook")
async def webhook_listener(request: Request, background_tasks: BackgroundTasks):
    """Receptor de webhooks de mensajes entrantes de WhatsApp."""
    # 1. IP Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"ip:{client_ip}", max_requests=30, period=60)
    
    # 2. X-Hub-Signature-256 Verification
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    if not META_APP_SECRET:
        if ENV == "production":
            raise HTTPException(status_code=500, detail="META_APP_SECRET no está configurado en el servidor")
        else:
            print("[WARNING] META_APP_SECRET no está configurado. Saltando firma del webhook.")
    else:
        if not signature_header or not signature_header.startswith("sha256="):
            raise HTTPException(status_code=401, detail="Firma de webhook ausente o formato incorrecto")
        expected_sig = signature_header.split("sha256=")[1]
        computed_sig = hmac.new(
            META_APP_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(computed_sig, expected_sig):
            raise HTTPException(status_code=401, detail="Firma de webhook inválida")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return Response(content="INVALID_JSON", status_code=400)
    
    # Validar que sea un mensaje de WhatsApp
    if "object" in payload and payload["object"] == "whatsapp_business_account":
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    # Capturar número de teléfono y mensaje
                    phone_number = msg.get("from")
                    if phone_number:
                        check_rate_limit(f"phone:{phone_number}", max_requests=10, period=60)
                    msg_type = msg.get("type")
                    
                    user_text = ""
                    referral_treatment = None
                    
                    # Si viene de un anuncio, Meta Ads adjunta un payload de "referral"
                    if "referral" in msg:
                        ref = msg["referral"]
                        body = ref.get("body", "")
                        headline = ref.get("headline", "")
                        print(f"[META ADS REFERRAL] Headline: {headline}, Body: {body}")
                        # Intentar inferir el tratamiento desde el anuncio
                        if "protesis" in headline.lower() or "protesis" in body.lower():
                            referral_treatment = "protesis_acrilicas"
                        elif "limpieza" in headline.lower() or "limpieza" in body.lower():
                            referral_treatment = "limpieza_dental"
                        elif "juicio" in headline.lower() or "muela" in headline.lower():
                            referral_treatment = "extraccion_muelas_juicio"
                    
                    if msg_type == "text":
                        user_text = msg.get("text", {}).get("body", "")
                    elif msg_type == "button":
                        user_text = msg.get("button", {}).get("text", "")
                        
                    if user_text:
                        # Procesar en segundo plano para poder responder 200 OK inmediatamente a Meta
                        background_tasks.add_task(
                            process_incoming_message, 
                            phone_number, 
                            user_text, 
                            referral_treatment
                        )
                        
        return Response(content="EVENT_RECEIVED", status_code=200)
    return Response(content="NOT_A_WHATSAPP_EVENT", status_code=400)

# --- LÓGICA DE PROCESAMIENTO ---

async def process_incoming_message(phone_number: str, text: str, referral_treatment: str = None):
    """Gestiona el flujo conversacional delegando en el agente con herramientas."""
    print(f"\n[INCOMING] De: {phone_number} | Mensaje: {text}")
    
    # 1. Obtener o crear sesión
    session = db.get_or_create_session(phone_number, initial_treatment=referral_treatment)
    current_treatment = session["treatment_context"] or referral_treatment
    
    # Si detectamos que el usuario menciona explícitamente algún tratamiento, actualizamos el contexto
    text_lower = text.lower()
    if "protesis" in text_lower or "prótesis" in text_lower:
        current_treatment = "protesis_acrilicas"
    elif "limpieza" in text_lower:
        current_treatment = "limpieza_dental"
    elif "juicio" in text_lower or "muela" in text_lower or "extracción" in text_lower:
        current_treatment = "extraccion_muelas_juicio"
        
    if current_treatment != session["treatment_context"]:
        db.update_session(phone_number, treatment_context=current_treatment)
        session["treatment_context"] = current_treatment
        
    # Guardar mensaje del usuario en el historial
    db.add_chat_message(phone_number, "user", text)
    
    # Obtener historial de chat completo
    history = db.get_chat_history(phone_number)
    
    # Generar respuesta final con el agente de IA utilizando herramientas nativas
    response_text = agent.generate_response_with_tools(phone_number, history, session)
    
    # Encolar la respuesta saliente (delay de 2 segundos)
    db.queue_outgoing_message(phone_number, response_text, 2)


# --- ENDPOINTS DE SIMULACIÓN Y MONITOREO (API PARA EL FRONTEND) ---

@app.post("/api/login")
def login(request_data: LoginRequest):
    password = request_data.password
    if not password:
        raise HTTPException(status_code=400, detail="Contraseña requerida")
    if not ADMIN_API_TOKEN:
        raise HTTPException(status_code=500, detail="ADMIN_API_TOKEN no está configurado en el servidor")
    if password == ADMIN_API_TOKEN:
        return {"token": ADMIN_API_TOKEN}
    else:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

@app.post("/api/simulate-incoming")
async def simulate_incoming(request_data: SimulateIncomingRequest, request: Request, background_tasks: BackgroundTasks, token: str = Depends(validate_admin_token)):
    """
    Simula la llegada de un mensaje de WhatsApp.
    Útil para pruebas de desarrollo.
    Payload: { "phone_number": "56912345678", "message": "Hola, precio de limpieza", "referral": null }
    """
    # 1. IP Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(f"ip:{client_ip}", max_requests=10, period=60)
    
    phone_number = request_data.phone_number or "56912345678"
    # 2. Phone Rate Limiting
    check_rate_limit(f"phone:{phone_number}", max_requests=5, period=60)
    
    message = request_data.message
    referral = request_data.referral
    
    background_tasks.add_task(process_incoming_message, phone_number, message, referral)
    return {"status": "processing", "simulated_delay_seconds": "35-60s"}

@app.get("/api/sessions")
def get_sessions(token: str = Depends(validate_admin_token)):
    """Retorna todas las sesiones activas en la BD."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/history/{phone_number}")
def get_history(phone_number: str, token: str = Depends(validate_admin_token)):
    """Retorna el historial completo del chat para un paciente."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, timestamp FROM chat_history WHERE phone_number = ? ORDER BY id ASC",
        (phone_number,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/outbox")
def get_outbox(token: str = Depends(validate_admin_token)):
    """Retorna la cola de mensajes salientes (outbox)."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/schedule")
def get_schedule(token: str = Depends(validate_admin_token)):
    """Retorna el calendario interno de Dentidesk para monitorear."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dentidesk_schedule ORDER BY slot_start ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/book")
def book_slot_direct(request_data: BookSlotRequest, token: str = Depends(validate_admin_token)):
    """Permite al frontend registrar una cita en Dentidesk manualmente."""
    phone_number = request_data.phone_number
    patient_name = request_data.patient_name
    patient_rut = request_data.patient_rut
    patient_phone = request_data.patient_phone
    slot_str = request_data.slot_str
    treatment = request_data.treatment
    duration_minutes = request_data.duration_minutes
    
    success = dentidesk.book_slot(
        phone_number=phone_number or patient_phone,
        patient_name=patient_name,
        patient_rut=patient_rut,
        patient_phone=patient_phone,
        slot_str=slot_str,
        treatment=treatment,
        duration_minutes=duration_minutes
    )
    if not success:
        raise HTTPException(status_code=400, detail="El horario seleccionado no está disponible o ya está ocupado")
        
    return {"status": "booked_successfully"}

@app.post("/api/delete-booking")
def delete_booking(request_data: DeleteBookingRequest, token: str = Depends(validate_admin_token)):
    """Permite al frontend eliminar una cita en Dentidesk."""
    slot_str = request_data.slot_str
    success = dentidesk.delete_slot(slot_str)
    if not success:
        raise HTTPException(status_code=404, detail="No se encontró una cita en ese horario")
    return {"status": "deleted_successfully"}

@app.post("/api/clear-chat/{phone_number}")
def clear_chat(phone_number: str, request: Request, token: str = Depends(validate_admin_token)):
    """Limpia el historial de chat de un paciente y restablece su estado a greeting."""
    client_ip = request.client.host if request.client else "unknown"
    audit_log(f"CLEAR_CHAT: {phone_number}", client_ip)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    # Eliminar mensajes del chat
    cursor.execute("DELETE FROM chat_history WHERE phone_number = ?", (phone_number,))
    # Eliminar mensajes pendientes de la cola de salida para este número
    cursor.execute("DELETE FROM outbox WHERE phone_number = ? AND status = 'pending'", (phone_number,))
    # Restablecer el estado de la sesión
    cursor.execute(
        """
        UPDATE sessions SET 
            state = 'greeting', 
            selected_slot = NULL, 
            patient_name = NULL, 
            patient_rut = NULL, 
            patient_phone = NULL 
        WHERE phone_number = ?
        """, 
        (phone_number,)
    )
    conn.commit()
    conn.close()
    return {"status": "chat cleared successfully"}

@app.post("/api/reset")
def reset_system(request: Request, token: str = Depends(validate_admin_token)):
    """Limpia la base de datos para reiniciar pruebas."""
    client_ip = request.client.host if request.client else "unknown"
    audit_log("SYSTEM_RESET", client_ip)
    
    if ENV == "production":
        raise HTTPException(status_code=403, detail="El reinicio del sistema no está permitido en producción")
        
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history")
    cursor.execute("DELETE FROM outbox")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM dentidesk_schedule")
    conn.commit()
    conn.close()
    
    # Repoblar Dentidesk
    dentidesk.init_dentidesk_db()
    return {"status": "system reset successfully"}

# --- RUTAS PARA EL FRONTEND ESTÁTICO ---

@app.get("/")
def get_index():
    response = FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/style.css")
def get_css():
    response = FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "style.css"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/app.js")
def get_js():
    response = FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "app.js"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

