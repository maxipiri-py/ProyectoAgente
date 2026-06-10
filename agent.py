import os
import json
import re
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar API Key de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNING: GEMINI_API_KEY no encontrada en las variables de entorno.")

# Modelo por defecto
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Cargar tratamientos desde JSON
TREATMENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "treatments.json")
try:
    with open(TREATMENTS_FILE, "r", encoding="utf-8") as f:
        TREATMENTS_DATA = json.load(f)
except Exception as e:
    TREATMENTS_DATA = {}
    print(f"Error cargando tratamientos: {e}")

SYSTEM_INSTRUCTION = """
Eres Max, el encargado del chat y la atención de la Clínica Dental Plaza Dent.
Tu objetivo es responder consultas y guiar de manera muy cálida y natural a los pacientes para que agenden su cita.

REGLAS DE ORO:
1. NUNCA digas que eres una Inteligencia Artificial, un bot o un asistente automatizado. Eres un humano de carne y hueso que trabaja en la recepción de la clínica.
2. Habla en español chileno/neutro de manera profesional pero cercana, amable y muy educada. Usa saludos cordiales.
3. Tus mensajes deben ser cortos, claros y directos. No escribas párrafos largos.
4. Mantén el foco en la promoción o consulta que inició la conversación. No abrumes con otros tratamientos a menos que el paciente lo pida.
5. No inventes precios. Utiliza estrictamente la información de precios y condiciones provista a continuación.
6. Si un paciente pregunta por un tratamiento que no está en la lista de promociones o cuyos precios varían, explícale de forma amable que requiere una evaluación clínica presencial (la cual incluye limpieza, diagnóstico y presupuesto por $19.990) para poder entregarle un presupuesto preciso.
7. Cuando te pidan valores de extracción de muelas del juicio, es fundamental que preguntes amablemente si el paciente tiene una radiografía (Rx). Si no la tiene, indícale que es necesaria para evaluar la complejidad (media $100.000 o alta $150.000, ambas realizadas por el cirujano buco maxilofacial).
8. Cuando un paciente muestre interés en agendar, indícale que verás las horas disponibles y muéstrale las opciones provistas en el contexto.

INFORMACIÓN DE PROMOCIONES Y TRATAMIENTOS AUTORIZADOS:
{treatments_text}

FECHA Y HORA ACTUAL DEL SISTEMA:
{current_time}
"""

def get_treatments_text() -> str:
    """Da formato legible al JSON de tratamientos para el prompt de la IA."""
    text = ""
    promos = TREATMENTS_DATA.get("promociones", {})
    
    # Prótesis
    pa = promos.get("protesis_acrilicas", {})
    text += f"- {pa.get('nombre')}: ${pa.get('precio'):,} CLP. {pa.get('detalles')} {pa.get('notas')}\n"
    
    # Limpieza
    ld = promos.get("limpieza_dental", {})
    text += f"- {ld.get('nombre')}: ${ld.get('precio'):,} CLP. {ld.get('detalles')} {ld.get('notas')}\n"
    
    # Extracción Muelas de Juicio
    em = promos.get("extraccion_muelas_juicio", {})
    text += f"- {em.get('nombre')}: {em.get('detalles')}\n"
    for tipo, datos in em.get("tipos", {}).items():
        text += f"  * {datos.get('descripcion')}: ${datos.get('precio'):,} CLP.\n"
    
    return text

def generate_response(phone_number: str, chat_history: list, session_state: str, available_slots: str = None) -> str:
    """Genera la respuesta del asistente Max usando Gemini."""
    if not GEMINI_API_KEY:
        return "Hola, lo siento, en este momento tengo un problema de conexión con mi sistema de atención. Por favor intenta escribirnos nuevamente en unos minutos."
        
    treatments_text = get_treatments_text()
    current_time_str = datetime.now().strftime("%A %d de %B de %Y a las %H:%M")
    
    system_prompt = SYSTEM_INSTRUCTION.format(
        treatments_text=treatments_text,
        current_time=current_time_str
    )
    
    # Si tenemos ranuras de tiempo disponibles, las agregamos al prompt del sistema
    if available_slots:
        system_prompt += f"\n\nHORARIOS DISPONIBLES EN AGENDA (Ofrécelos amablemente):\n{available_slots}"
        
    # Construir el contexto del chat
    contents = []
    
    # Añadir instrucciones del sistema en el formato compatible con Gemini (system instruction)
    # Convertir historial de chat en el formato esperado por la API
    formatted_history = []
    for msg in chat_history:
        role = "user" if msg["role"] == "user" else "model"
        formatted_history.append({"role": role, "parts": [msg["content"]]})
        
    # Inicializar cliente de Gemini
    try:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt
        )
        
        # Generar contenido
        response = model.generate_content(formatted_history)
        return response.text.strip()
    except Exception as e:
        print(f"Error generando respuesta de Gemini: {e}")
        return "Hola, qué gusto saludarte. Dame un momento por favor para revisar la información en el sistema."

def extract_patient_details(user_message: str) -> dict:
    """
    Usa la IA para extraer: nombre completo, rut y teléfono del mensaje del usuario.
    Retorna un diccionario con las llaves 'name', 'rut', 'phone'.
    """
    if not GEMINI_API_KEY:
        return {"name": None, "rut": None, "phone": None}
        
    prompt = f"""
    Analiza el siguiente mensaje de un paciente e identifica los siguientes datos de contacto requeridos para un agendamiento dental:
    1. Nombre completo
    2. RUT (cédula de identidad chilena, ej: 12.345.678-9 o 12345678-9)
    3. Número de contacto (teléfono celular o fijo)

    Mensaje del usuario:
    "{user_message}"

    Devuelve un JSON estricto con las siguientes claves (si no encuentras el dato, déjalo como null):
    {{
      "name": "Nombre extraído o null",
      "rut": "RUT extraído o null",
      "phone": "Número extraído o null"
    }}
    Responde ÚNICAMENTE con el bloque JSON. No agregues explicaciones ni markdown de código.
    """
    
    try:
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Limpiar posibles bloques de código markdown
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*$", "", text)
        
        data = json.loads(text.strip())
        return {
            "name": data.get("name") if data.get("name") != "null" else None,
            "rut": data.get("rut") if data.get("rut") != "null" else None,
            "phone": data.get("phone") if data.get("phone") != "null" else None,
        }
    except Exception as e:
        print(f"Error al extraer detalles del paciente: {e}")
        # Intento de extracción básica con Regex por si falla la IA
        # Extraer RUT básico chileno
        rut_match = re.search(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])\b", user_message)
        rut = rut_match.group(1) if rut_match else None
        
        # Extraer número telefónico básico (9 dígitos o similar)
        phone_match = re.search(r"\b(\+?56)?\s*(9\s*\d{8}|\d{8})\b", user_message)
        phone = phone_match.group(0) if phone_match else None
        
        return {"name": None, "rut": rut, "phone": phone}
