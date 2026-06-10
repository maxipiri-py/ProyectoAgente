import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Asegurar que el directorio actual esté en el path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Cargar variables de entorno
load_dotenv()

# Validar API key antes de correr
if not os.getenv("GEMINI_API_KEY"):
    print("=====================================================================")
    print("WARNING: No has configurado GEMINI_API_KEY en tu archivo .env.")
    print("Por favor crea un archivo llamado '.env' basado en '.env.template'")
    print("y coloca tu API key para poder conversar con el agente de IA.")
    print("=====================================================================")

# Importar dependencias del proyecto
try:
    import database as db
    import dentidesk
    import agent
    from main import process_incoming_message
except ImportError as e:
    print(f"Error al importar módulos del proyecto: {e}")
    sys.exit(1)

async def simulate_outbox_processing():
    """Busca mensajes pendientes en el outbox y los procesa inmediatamente (simula time-travel)."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM outbox WHERE status = 'pending'")
    pending = cursor.fetchall()
    conn.close()
    
    if not pending:
        return False
        
    print("\n--- [PROCESANDO MENSAJES SALIENTES DE LA COLA (OUTBOX)] ---")
    for msg in pending:
        # Mostrar el mensaje saliente simulando que pasó el tiempo de retraso
        print(f"\n[Max (Assistant) - Enviado]: \"{msg['content']}\"")
        
        # Marcar como enviado e insertar en el historial de chat
        db.mark_message_status(msg["id"], "sent")
        db.add_chat_message(msg["phone_number"], "assistant", msg["content"])
        
        # Si la respuesta era de agendamiento seleccionado, actualizar la información en consola
        session = db.get_or_create_session(msg["phone_number"])
        if session["state"] == "scheduling_selected":
            print(f"-> [ESTADO]: El bot solicitó Nombre, RUT y Teléfono para la fecha: {session['selected_slot']}")
        elif session["state"] == "booked":
            print(f"-> [ESTADO]: Cita AGENDADA en Dentidesk para: {session['patient_name']} ({session['selected_slot']})")
            
    print("-----------------------------------------------------------\n")
    return True

async def main():
    print("=====================================================================")
    print("        SIMULADOR INTERACTIVO DE PLAZA DENT (CHATBOT MAX)           ")
    print("=====================================================================")
    print("Este script te permite chatear directamente con el Agente de IA 'Max'.")
    print("Podrás ver cómo cambian los estados del paciente y cómo se acumulan")
    print("los mensajes salientes con retraso humano en el outbox de la base de datos.")
    print("=====================================================================\n")
    
    # Reiniciar base de datos para la prueba
    db.init_db()
    dentidesk.init_dentidesk_db()
    
    phone_number = "56912345678"
    
    # Menú para elegir anuncio
    print("Selecciona cómo se inicia el chat desde Meta Ads:")
    print("1) Anuncio de Prótesis Dentales Acrílicas (Mensaje predefinido)")
    print("2) Anuncio de Limpieza Dental + Evaluación (Mensaje predefinido)")
    print("3) Anuncio de Extracción Muelas del Juicio (Mensaje predefinido)")
    print("4) Chat libre sin anuncio previo")
    
    choice = input("\nElige una opción (1-4): ").strip()
    
    referral_treatment = None
    initial_msg = ""
    if choice == "1":
        referral_treatment = "protesis_acrilicas"
        initial_msg = "Hola, vi su anuncio sobre la promo de prótesis dentales acrílicas y me interesa."
    elif choice == "2":
        referral_treatment = "limpieza_dental"
        initial_msg = "Hola, me interesa la promoción de limpieza dental y evaluación por $19.990."
    elif choice == "3":
        referral_treatment = "extraccion_muelas_juicio"
        initial_msg = "Hola, me gustaría cotizar la extracción de muelas del juicio."
    else:
        initial_msg = "Hola, buenas tardes."
        
    print(f"\n[Paciente - Entrada]: \"{initial_msg}\"")
    
    # Procesar primer mensaje
    await process_incoming_message(phone_number, initial_msg, referral_treatment)
    
    # Simular la cola inmediatamente
    await simulate_outbox_processing()
    
    while True:
        # Consultar estado de sesión actual
        session = db.get_or_create_session(phone_number)
        print(f"[Estado actual de sesión: '{session['state']}'] | [Tratamiento: '{session['treatment_context']}']")
        if session['selected_slot']:
            print(f"[Horario seleccionado: '{session['selected_slot']}']")
            
        user_input = input("Paciente (escribe aquí, o 'salir' para terminar): ").strip()
        
        if user_input.lower() in ["salir", "exit", "quit"]:
            print("Cerrando simulador interactivo...")
            break
            
        if not user_input:
            continue
            
        # Enviar mensaje
        await process_incoming_message(phone_number, user_input)
        
        # Obtener los mensajes encolados pendientes
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outbox WHERE status = 'pending'")
        pending = cursor.fetchall()
        conn.close()
        
        if pending:
            print(f"\n[SISTEMA]: Se ha programado {len(pending)} mensaje(s) en el outbox con retraso humano.")
            for p in pending:
                print(f"  - Programado para: {p['send_at']} (retraso simulado)")
            
            # Ofrecer simular envío inmediato
            sim = input("¿Deseas simular el paso del tiempo y enviar las respuestas de Max ahora? (S/n): ").strip().lower()
            if sim != "n":
                await simulate_outbox_processing()
        else:
            print("\n[SISTEMA]: No se programaron mensajes en el outbox.")

if __name__ == "__main__":
    asyncio.run(main())
