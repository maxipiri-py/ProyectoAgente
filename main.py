import os
import json
import random
import asyncio
import requests
from datetime import datetime
from fastapi import FastAPI, Request, Response, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from dotenv import load_dotenv

import database as db
import dentidesk
import agent

load_dotenv()

app = FastAPI(title="Plaza Dent AI Agent Service")

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
    payload = await request.json()
    
    # Validar que sea un mensaje de WhatsApp
    if "object" in payload and payload["object"] == "whatsapp_business_account":
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    # Capturar número de teléfono y mensaje
                    phone_number = msg.get("from")
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

@app.post("/api/simulate-incoming")
async def simulate_incoming(data: dict, background_tasks: BackgroundTasks):
    """
    Simula la llegada de un mensaje de WhatsApp.
    Útil para pruebas de desarrollo.
    Payload: { "phone_number": "56912345678", "message": "Hola, precio de limpieza", "referral": null }
    """
    phone_number = data.get("phone_number", "56912345678")
    message = data.get("message", "")
    referral = data.get("referral")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message content required")
        
    background_tasks.add_task(process_incoming_message, phone_number, message, referral)
    return {"status": "processing", "simulated_delay_seconds": "35-60s"}

@app.get("/api/sessions")
def get_sessions():
    """Retorna todas las sesiones activas en la BD."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/history/{phone_number}")
def get_history(phone_number: str):
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
def get_outbox():
    """Retorna la cola de mensajes salientes (outbox)."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM outbox ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/schedule")
def get_schedule():
    """Retorna el calendario interno de Dentidesk para monitorear."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dentidesk_schedule ORDER BY slot_start ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/book")
def book_slot_direct(data: dict):
    """Permite al frontend registrar una cita en Dentidesk manualmente."""
    phone_number = data.get("phone_number")
    patient_name = data.get("patient_name")
    patient_rut = data.get("patient_rut")
    patient_phone = data.get("patient_phone")
    slot_str = data.get("slot_str")
    treatment = data.get("treatment")
    duration_minutes = int(data.get("duration_minutes", 30))
    
    if not (patient_name and patient_rut and slot_str):
        raise HTTPException(status_code=400, detail="Faltan datos obligatorios para el agendamiento")
        
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
def delete_booking(data: dict):
    """Permite al frontend eliminar una cita en Dentidesk."""
    slot_str = data.get("slot_str")
    if not slot_str:
        raise HTTPException(status_code=400, detail="Falta el horario de la cita a eliminar")
    success = dentidesk.delete_slot(slot_str)
    if not success:
        raise HTTPException(status_code=404, detail="No se encontró una cita en ese horario")
    return {"status": "deleted_successfully"}

@app.post("/api/clear-chat/{phone_number}")
def clear_chat(phone_number: str):
    """Limpia el historial de chat de un paciente y restablece su estado a greeting."""
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
def reset_system():
    """Limpia la base de datos para reiniciar pruebas."""
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

