import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv

# Importar de LangChain
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
except ImportError:
    # Fallback si aún no están instalados al importar por primera vez
    ChatOpenAI = None
    SystemMessage = None
    HumanMessage = None
    AIMessage = None

# Cargar variables de entorno
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("GITHUB_TOKEN")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or os.getenv("GITHUB_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


# Inicializar cliente de ChatOpenAI
llm = None
if ChatOpenAI and OPENAI_API_KEY:
    try:
        if OPENAI_API_BASE:
            # GitHub Models u otro endpoint compatible
            llm = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_API_BASE,
                temperature=0.7
            )
        else:
            # OpenAI Directo
            llm = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=0.7
            )
    except Exception as e:
        print(f"Error inicializando ChatOpenAI: {e}")

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
6. Si un paciente pregunta por un tratamiento que no está en la lista de promociones o cuyos precios varían, explíale de forma amable que requiere una evaluación clínica presencial (la cual incluye limpieza, diagnóstico y presupuesto por $19.990) para poder entregarle un presupuesto preciso.
7. Cuando te pidan valores de extracción de muelas del juicio, es fundamental que preguntes amablemente si el paciente tiene una radiografía (Rx). Si no la tiene, indícale que es necesaria para evaluar la complejidad (media $100.000 o alta $150.000, ambas realizadas por el cirujano buco maxilofacial).
8. Cuando un paciente muestre interés en agendar, indícale que verás las horas disponibles y muéstrale las opciones provistas en el contexto.
9. NUNCA le digas al paciente que su cita ya está reservada o confirmada si aún no te ha entregado su nombre completo, RUT y teléfono de contacto. Si el paciente selecciona un horario, debes pedirle de inmediato estos datos en un único mensaje de la siguiente manera exacta: "perfecto, para agendar su cita necesitaré su nombre completo, rut y numero de contacto por favor."

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
    text += f"- {pa.get('nombre')}: ${pa.get('precio'):,} CLP. {pa.get('detalles')} {pa.get('notes') if 'notes' in pa else pa.get('notas')}\n"
    
    # Limpieza
    ld = promos.get("limpieza_dental", {})
    text += f"- {ld.get('nombre')}: ${ld.get('precio'):,} CLP. {ld.get('detalles')} {ld.get('notes') if 'notes' in ld else ld.get('notas')}\n"
    
    # Extracción Muelas de Juicio
    em = promos.get("extraccion_muelas_juicio", {})
    text += f"- {em.get('nombre')}: {em.get('detalles')}\n"
    for tipo, datos in em.get("tipos", {}).items():
        text += f"  * {datos.get('descripcion')}: ${datos.get('precio'):,} CLP.\n"
    
    return text

def ensure_llm():
    """Garantiza la inicialización tardía por si no se cargaron las dependencias al inicio."""
    global llm
    if llm is None and ChatOpenAI and OPENAI_API_KEY:
        try:
            if OPENAI_API_BASE:
                llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE, temperature=0.7)
            else:
                llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0.7)
        except Exception as e:
            print(f"Error inicializando ChatOpenAI tardío: {e}")
    return llm

def generate_response(phone_number: str, chat_history: list, session_state: str, available_slots: str = None) -> str:
    """Genera la respuesta del asistente Max usando LangChain y OpenAI/GitHub Models."""
    client = ensure_llm()
    if not client:
        return "Hola, lo siento, en este momento tengo un problema de conexión con mi sistema de atención. Por favor intenta escribirnos nuevamente en unos minutos."
        
    treatments_text = get_treatments_text()
    current_time_str = datetime.now().strftime("%A %d de %B de %Y a las %H:%M")
    
    system_prompt = SYSTEM_INSTRUCTION.format(
        treatments_text=treatments_text,
        current_time=current_time_str
    )
    
    if available_slots:
        system_prompt += f"\n\nHORARIOS DISPONIBLES EN AGENDA (Ofrécelos amablemente):\n{available_slots}"
        
    # Construir historial de mensajes para LangChain
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
            
    try:
        response = client.invoke(messages)
        return response.content.strip()
    except Exception as e:
        print(f"Error generando respuesta de LangChain: {e}")
        return "Hola, qué gusto saludarte. Dame un momento por favor para revisar la información en el sistema."

def extract_patient_details(user_message: str) -> dict:
    """Usa LangChain para extraer: nombre completo, rut y teléfono del mensaje del usuario."""
    client = ensure_llm()
    if not client:
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
        response = client.invoke([HumanMessage(content=prompt)])
        text = response.content.strip()
        
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
        # Regex fallback
        rut_match = re.search(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])\b", user_message)
        rut = rut_match.group(1) if rut_match else None
        
        phone_match = re.search(r"\b(\+?56)?\s*(9\s*\d{8}|\d{8})\b", user_message)
        phone = phone_match.group(0) if phone_match else None
        
        return {"name": None, "rut": rut, "phone": phone}

def extract_selected_slot(user_message: str, all_slots: list) -> str:
    """Evalúa qué slot de la lista de disponibles seleccionó el paciente en su mensaje."""
    client = ensure_llm()
    if not client:
        return None
        
    prompt = f"""
    El paciente respondió: "{user_message}"
    De la siguiente lista de horarios disponibles en la agenda, determina cuál seleccionó el paciente.
    Formatos aceptados en la lista: 'YYYY-MM-DD HH:MM'.
    
    Lista de horarios disponibles:
    {json.dumps(all_slots)}
    
    Responde únicamente con la fecha y hora exacta de la lista en formato 'YYYY-MM-DD HH:MM', o escribe 'none' si el paciente no seleccionó ningún horario o quiere otra fecha. No agregues texto adicional.
    """
    
    try:
        response = client.invoke([HumanMessage(content=prompt)])
        res_text = response.content.strip()
        
        # Limpiar posibles bloques de código markdown
        res_text = re.sub(r"```[a-zA-Z]*\s*", "", res_text)
        res_text = re.sub(r"```\s*$", "", res_text)
        res_text = res_text.strip()
        
        if res_text != "none" and res_text in all_slots:
            return res_text
    except Exception as e:
        print(f"Error extrayendo slot seleccionado con LangChain: {e}")
    return None
