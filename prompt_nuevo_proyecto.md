# Prompt de Replicación para Nuevo Proyecto de Agente e Interfaz

Copia y pega el siguiente prompt en tu nuevo chat o proyecto de IA. Asegúrate de rellenar los datos entre corchetes `[ ]` con los detalles de tu nueva empresa.

---

```text
Quiero construir un sistema web y agente de IA para mi empresa. 

Aquí están los detalles de personalización:
- Nombre de la empresa: [EJEMPLO: Centro Médico Vitalis]
- Nombre del agente de IA: [EJEMPLO: Sofía]
- Rol del agente: [EJEMPLO: Encargada del chat y reservas de Vitalis]
- Servicio externo a simular: [EJEMPLO: Agenda de ClinicCloud / Google Calendar]
- Canal de entrada: Conversaciones iniciadas por WhatsApp desde campañas de Meta Ads.
- Duración de citas: [EJEMPLO: 30 minutos para consultas generales, 60 minutos para tratamientos específicos]

ESPECIFICACIONES TÉCNICAS DEL PROYECTO:

1. ARQUITECTURA DEL BACKEND (Python):
   - Usa FastAPI como servidor web principal.
   - Usa SQLite como base de datos local (archivo local de base de datos) con tres tablas:
     * 'sessions': guarda el número de teléfono del paciente, el tratamiento/motivo de consulta, el estado de la conversación, el horario seleccionado y los datos del paciente (Nombre completo, RUT/DNI, Teléfono).
     * 'chat_history': guarda cronológicamente los mensajes de la conversación (role: 'user' o 'assistant', content, timestamp).
     * 'outbox': cola de mensajes programados para enviar.
   - Implementa un background task (worker asíncrono) continuo en FastAPI que revise la tabla 'outbox' y envíe las respuestas a los pacientes. Si no se configuran las credenciales oficiales de WhatsApp, el worker debe simular el envío imprimiendo en consola de forma segura (con manejo de try/except contra Unicode/emojis para que no caiga en Windows).
   - El delay/retraso de respuesta del agente de IA debe configurarse en: [EJEMPLO: 5 segundos].

2. CAPA DE INTEGRACIÓN DE IA (LangChain + OpenAI / GitHub Models):
   - Configura el backend usando LangChain ('langchain-openai' y 'langchain-core').
   - Lee variables de entorno (.env) para:
     * GITHUB_TOKEN (para GitHub Models) u OPENAI_API_KEY (para OpenAI directo).
     * OPENAI_API_BASE / GITHUB_BASE_URL (ej: 'https://models.inference.ai.azure.com' para GitHub Models).
     * OPENAI_MODEL (ej: 'gpt-4o' o 'gpt-4o-mini').
   - Diseña un System Prompt para el agente con el tono de la empresa, listado de tratamientos y precios:
     [INSERTE AQUÍ SU LISTADO DE TRATAMIENTOS Y PRECIOS]
   - Implementa funciones en la IA para:
     * Generar la respuesta conversacional.
     * Extraer los datos del paciente (Nombre, RUT/DNI y Teléfono) de una sola vez cuando se solicita la cita.
     * Identificar qué horario de la lista de libres seleccionó el paciente en su mensaje.

3. SIMULADOR DE AGENDA DE CITAS (MOCK SERVICE):
   - Crea un módulo simulador que represente la agenda de la clínica/empresa.
   - Genera dinámicamente horarios libres para los próximos 7 días laborales dentro de las horas de atención: [EJEMPLO: Lunes a Sábado de 09:00 a 18:00].
   - Agrega por defecto bloqueos o citas ocupadas simuladas (ej: "Reunión", "Hora reservada", almuerzos) para que la agenda sea realista.
   - Permite que las citas creadas por el chatbot queden registradas con estado "No confirmado".

4. INTERFAZ GRÁFICA DE USUARIO (HTML5 + Vanilla CSS + Vanilla JS):
   - Sirve el frontend directamente como estático en FastAPI.
   - Crea un clon visual premium del software de la agenda:
     * Una pantalla de login que imite el inicio del software real.
     * Al iniciar sesión, muestra un Dashboard con dos columnas:
       - Columna Izquierda (75% ancho): Una grilla/calendario semanal (Lunes a Domingo) con filas cada 30 minutos. Muestra celdas vacías y celdas ocupadas de color. Las citas deben ocupar visualmente el tamaño de su duración usando 'rowspan' (ej: una cita de 60m ocupa 2 celdas de alto).
       - Columna Derecha (25% ancho): Un simulador de WhatsApp. Permite seleccionar un número de paciente, simular que viene de una campaña de Meta Ads enviando un primer mensaje, ver la conversación en vivo, y ver un contador regresivo de la cola cuando el bot de IA está procesando la respuesta (ej. "Enviando en 5s...").
       - Al hacer clic en un espacio vacío del calendario, se debe abrir un Modal interactivo (idéntico al de creación de citas del software de agenda) para registrar a un paciente manualmente, permitiendo que la cita aparezca de inmediato en la agenda.
       - Incluye un botón "Limpiar" para vaciar la base de datos de prueba y reiniciar los tests.

Por favor, crea toda la estructura del proyecto en archivos limpios, configurando .env.template, requirements.txt, la base de datos, el simulador de agenda, la lógica de IA y la interfaz gráfica estática.
```
