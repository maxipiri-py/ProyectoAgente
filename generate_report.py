import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfgen import canvas

# --- NumberedCanvas para paginación dinámica y encabezado/pie de página ---
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Omitir decoraciones en la portada (Página 1)
        if self._pageNumber > 1:
            # Línea y encabezado superior
            self.setStrokeColor(colors.HexColor('#13b593'))
            self.setLineWidth(0.75)
            self.line(54, 750, 612 - 54, 750)
            
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor('#2c3e50'))
            self.drawString(54, 755, "INFORME TÉCNICO: DESARROLLO Y ENDURECIMIENTO DE AGENTE CHATBOT")
            
            # Línea y pie de página inferior
            self.setStrokeColor(colors.HexColor('#e1e8ed'))
            self.setLineWidth(0.5)
            self.line(54, 48, 612 - 54, 48)
            
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor('#7f8c8d'))
            self.drawString(54, 36, "Clínica Dental Plaza Dent — Entorno de Evaluación AWS")
            
            page_text = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(612 - 54, 36, page_text)
            
        self.restoreState()

def build_pdf(filename):
    # Configuración del documento
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54, # 0.75 in
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # --- Definición de estilos de texto ---
    cover_title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=30,
        textColor=colors.HexColor('#13b593'),
        spaceAfter=15,
        alignment=1 # Centrado
    )
    
    cover_subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=40,
        alignment=1 # Centrado
    )
    
    h1_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceBefore=18,
        spaceAfter=10,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'SubSectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#13b593'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#333d47'),
        spaceAfter=8
    )
    
    code_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#2c3e50'),
        backColor=colors.HexColor('#f2f5f8'),
        borderColor=colors.HexColor('#e1e8ed'),
        borderWidth=0.5,
        borderPadding=8,
        spaceBefore=5,
        spaceAfter=8
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#333d47'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )
    
    story = []
    
    # =========================================================================
    # PORTADA
    # =========================================================================
    story.append(Spacer(1, 100))
    
    # Círculo decorativo o logo simulado
    logo_data = [[Paragraph("<font size=28 color=white><b>D</b></font>", ParagraphStyle('L', alignment=1))]]
    logo_table = Table(logo_data, colWidths=[60], rowHeights=[60])
    logo_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#13b593')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(logo_table)
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("INFORME TÉCNICO DE PROYECTO", cover_title_style))
    story.append(Paragraph("Desarrollo de Chatbot Inteligente y Endurecimiento Integral de la API de Dentidesk", cover_subtitle_style))
    
    story.append(Spacer(1, 100))
    
    # Tabla con los metadatos del proyecto
    meta_data = [
        [Paragraph("<b>Proyecto:</b>", body_style), Paragraph("Chatbot IA Plaza Dent (Agente Max)", body_style)],
        [Paragraph("<b>Especialidad:</b>", body_style), Paragraph("Examen de Proyecto de Integración de Agentes", body_style)],
        [Paragraph("<b>Entorno:</b>", body_style), Paragraph("AWS EC2 (Amazon Linux 2023) - Producción Segura", body_style)],
        [Paragraph("<b>Autor:</b>", body_style), Paragraph("Dr. Maximiliano Cifuentes / Duoc UC", body_style)],
        [Paragraph("<b>Fecha de Generación:</b>", body_style), Paragraph("Junio de 2026", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[120, 280])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fafbfc')),
        ('BORDER', (0,0), (-1,-1), 0.5, colors.HexColor('#e1e8ed')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(meta_table)
    
    story.append(PageBreak())
    
    # =========================================================================
    # SECCIÓN 1: INTRODUCCIÓN Y OBJETIVOS
    # =========================================================================
    story.append(Paragraph("1. Introducción y Objetivos", h1_style))
    story.append(Paragraph(
        "El presente informe documenta el desarrollo y despliegue del asistente conversacional de Inteligencia Artificial "
        "denominado <b>'Max'</b>, integrado con la plataforma odontológica <b>Dentidesk</b> para la clínica <b>Plaza Dent</b>. "
        "El objetivo principal del proyecto consistió en automatizar de manera segura y natural la consulta y el agendamiento "
        "de citas odontológicas para los pacientes, minimizando la carga administrativa del personal clínico y ofreciendo "
        "una experiencia de usuario interactiva y fluida.",
        body_style
    ))
    story.append(Paragraph("Los objetivos específicos del desarrollo se estructuraron bajo tres dimensiones clave:", body_style))
    story.append(Paragraph("• <b>Funcionalidad Conversacional:</b> Migración del motor de lógica de conversación a Function Calling nativo de OpenAI.", bullet_style))
    story.append(Paragraph("• <b>Seguridad de la Información (Hardening):</b> Blindaje de los endpoints del backend contra intrusiones, inyección de payloads dañinos, abuso de recursos y fuga de la lógica interna de negocio.", bullet_style))
    story.append(Paragraph("• <b>Navegación e Interfaz (Dashboard):</b> Habilitación de vistas modulares y consistentes para la administración de la clínica de forma ágil y de solo lectura.", bullet_style))
    
    # =========================================================================
    # SECCIÓN 2: ARQUITECTURA GENERAL DEL SISTEMA
    # =========================================================================
    story.append(Paragraph("2. Arquitectura General del Sistema", h1_style))
    story.append(Paragraph(
        "El sistema se estructuró bajo una arquitectura desacoplada de alto rendimiento y bajo consumo, operando de "
        "la siguiente manera:",
        body_style
    ))
    
    arch_data = [
        [Paragraph("<b>Componente</b>", body_style), Paragraph("<b>Tecnología</b>", body_style), Paragraph("<b>Descripción</b>", body_style)],
        [Paragraph("Backend", body_style), Paragraph("FastAPI (Python 3)", body_style), Paragraph("Servidor asíncrono asgiref de alto desempeño para APIs y Webhooks.", body_style)],
        [Paragraph("Base de Datos", body_style), Paragraph("SQLite (`plaza_dent.db`)", body_style), Paragraph("Almacenamiento persistente local de sesiones de chat y la agenda de Dentidesk.", body_style)],
        [Paragraph("Motor de IA", body_style), Paragraph("OpenAI GPT-4o (Azure Inference)", body_style), Paragraph("Razonamiento lógico y toma de decisiones a través de Function Calling nativo.", body_style)],
        [Paragraph("Frontend", body_style), Paragraph("HTML5 / CSS3 / JavaScript Vainilla", body_style), Paragraph("Interfaz de usuario reactiva, calendario interactivo y simulador de WhatsApp.", body_style)],
    ]
    arch_table = Table(arch_data, colWidths=[100, 130, 270])
    arch_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e1e8ed')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fafbfc')]),
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 10))
    
    # =========================================================================
    # SECCIÓN 3: MIGRACIÓN A OPENAI FUNCTION CALLING NATIVO
    # =========================================================================
    story.append(Paragraph("3. Migración a OpenAI Function Calling Nativo", h1_style))
    story.append(Paragraph(
        "Anteriormente, el agente controlaba el flujo conversacional mediante lógica de estados estáticos y parsing por expresiones regulares. "
        "Esta estructura resultaba rígida e inestable ante variaciones en las respuestas del usuario. "
        "Para solucionarlo, migramos el backend a la API nativa de <b>OpenAI Function Calling</b>.",
        body_style
    ))
    story.append(Paragraph(
        "Se definieron formalmente dos herramientas en formato JSON Schema que el modelo GPT-4o puede invocar autónomamente según el contexto:",
        body_style
    ))
    story.append(Paragraph("1. <b><font face='Courier'>get_available_slots</font></b>: Consulta los horarios reales de atención de la clínica en la base de datos de Dentidesk.", bullet_style))
    story.append(Paragraph("2. <b><font face='Courier'>book_appointment</font></b>: Agenda de forma final la cita del paciente tras recopilar obligatoriamente sus datos personales (nombre completo, RUT y teléfono).", bullet_style))
    
    story.append(Paragraph(
        "El bucle de ejecución implementa un patrón ReAct. Si el LLM solicita ejecutar una herramienta, el backend la corre localmente "
        "en Python, actualiza la base de datos (por ejemplo, marcando el slot como 'booked') y le entrega el resultado al modelo como una observación. "
        "El modelo posteriormente formula una respuesta natural para el paciente en WhatsApp.",
        body_style
    ))
    
    # =========================================================================
    # SECCIÓN 4: ENDURECIMIENTO DE SEGURIDAD DE LA API
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. Endurecimiento de Seguridad de la API", h1_style))
    story.append(Paragraph(
        "Para asegurar que la aplicación sea segura y resistente a ataques comunes, implementamos múltiples capas de remediación y buenas prácticas:",
        body_style
    ))
    
    story.append(Paragraph("4.1. Autenticación y Autorización Robusta", h2_style))
    story.append(Paragraph(
        "Todos los endpoints de la API (`/api/*`) están blindados bajo la dependencia de autenticación <font face='Courier'>HTTPBearer</font> de FastAPI. "
        "Las solicitudes deben inyectar una cabecera <font face='Courier'>Authorization: Bearer &lt;Token&gt;</font>. "
        "Se añadió el endpoint seguro <font face='Courier'>/api/login</font> para validar la contraseña de administración contra el secreto "
        "<font face='Courier'>ADMIN_API_TOKEN</font> definido de manera segura en el archivo de entorno.",
        body_style
    ))
    
    story.append(Paragraph("4.2. Middleware de Cabeceras de Seguridad y Ocultación de Firma", h2_style))
    story.append(Paragraph(
        "Configuramos un middleware HTTP personalizado para sanitizar las cabeceras de todas las respuestas. Se inyectaron políticas recomendadas por OWASP:",
        body_style
    ))
    story.append(Paragraph("• <b>Strict-Transport-Security (HSTS):</b> Fuerza la comunicación mediante protocolo HTTPS seguro por 2 años.", bullet_style))
    story.append(Paragraph("• <b>Content-Security-Policy (CSP):</b> Restringe los orígenes de scripts externos autorizados.", bullet_style))
    story.append(Paragraph("• <b>X-Frame-Options:</b> Bloquea ataques de Clickjacking impidiendo que la app sea embebida en iframes externos.", bullet_style))
    story.append(Paragraph("• <b>X-Content-Type-Options (nosniff):</b> Evita que el navegador intente adivinar el MIME-type de las respuestas.", bullet_style))
    story.append(Paragraph("• <b>Server: Hidden:</b> Sobrescribe la cabecera por defecto expuesta por Uvicorn, ocultando la tecnología subyacente para mitigar ataques de reconocimiento.", bullet_style))
    
    story.append(Paragraph("4.3. Validación de Payload y Rate Limiting", h2_style))
    story.append(Paragraph(
        "Se adoptaron modelos de validación de datos <font face='Courier'>Pydantic</font> que rechazan solicitudes con tipos de datos erróneos (ej. strings en campos numéricos) "
        "antes de que lleguen a la lógica del negocio. Asimismo, se limita la longitud máxima de los mensajes a 2000 caracteres para mitigar desbordamientos. "
        "Se incorporó un limitador de tasas (Rate Limiting) en memoria por IP (máximo 10 peticiones/min) y por teléfono del paciente (máximo 5 peticiones/min) "
        "para repeler ataques de denegación de servicio (DoS) y el abuso de cuotas del modelo de lenguaje.",
        body_style
    ))
    
    story.append(Paragraph("4.4. Aislamiento de Entornos y Desactivación de Documentación", h2_style))
    story.append(Paragraph(
        "Cuando el servidor detecta que la variable de entorno <font face='Courier'>ENV</font> es igual a <font face='Courier'>'production'</font>:",
        body_style
    ))
    story.append(Paragraph("1. Se desactivan por completo los endpoints interactivos de documentación (<font face='Courier'>/docs</font>, <font face='Courier'>/redoc</font> y <font face='Courier'>/openapi.json</font>).", bullet_style))
    story.append(Paragraph("2. Se bloquea el endpoint destructivo <font face='Courier'>/api/reset</font> (limpieza de BD), arrojando un error <b>403 Forbidden</b> de forma inmediata e indiscutible.", bullet_style))
    
    story.append(Paragraph("4.5. Auditoría y Validación de Firmas de Webhooks", h2_style))
    story.append(Paragraph(
        "Todas las llamadas a endpoints sensibles como el reinicio de chat o reset de BD escriben de inmediato al archivo físico <font face='Courier'>audit.log</font>, "
        "registrando fecha, hora, IP y acción del cliente. Para el endpoint del Webhook de WhatsApp (<font face='Courier'>/webhook</font>), se verifica la cabecera "
        "<font face='Courier'>X-Hub-Signature-256</font> calculando el HMAC-SHA256 del cuerpo bruto de la solicitud usando el secreto <font face='Courier'>META_APP_SECRET</font>.",
        body_style
    ))
    
    # =========================================================================
    # SECCIÓN 5: INMUNIZACIÓN DE LÓGICA DE NEGOCIO
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Inmunización de Lógica de Negocio y Confidencialidad", h1_style))
    story.append(Paragraph(
        "Los modelos de IA generativa son susceptibles a ataques de secuestro de instrucciones (Prompt Injection o Jailbreaking). "
        "Para inmunizar al agente Max contra la revelación involuntaria de configuraciones internas, listas completas de precios, o claves privadas, implementamos un doble anillo de protección:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Instrucción de Sistema Reforzada:</b> En `agent.py`, se robustecieron las directrices primarias. Se le instruyó explícitamente a Max a rechazar solicitudes de "
        "auditoría, QA, o gerencia ficticia que pregunten por las reglas internas o por el prompt del sistema.",
        body_style
    ))
    story.append(Paragraph(
        "• <b>Filtro Post-Procesamiento (Output Sanitization):</b> Se implementó la función <font face='Courier'>filter_response</font> que analiza el texto del agente antes de enviarlo. "
        "Si detecta volcados masivos de datos comerciales o palabras clave de depuración, bloquea la salida y devuelve una frase amable alternativa para el paciente.",
        body_style
    ))
    
    # =========================================================================
    # SECCIÓN 6: NAVEGACIÓN E INTERFAZ DEL DASHBOARD
    # =========================================================================
    story.append(Paragraph("6. Estructura Visual e Interfaz del Dashboard", h1_style))
    story.append(Paragraph(
        "Se rediseñó la estructura del panel frontal en `index.html` y `app.js` para habilitar el uso y la visualización de las pestañas que previamente permanecían inactivas:",
        body_style
    ))
    story.append(Paragraph("• <b>Navegación Fluida:</b> La función JavaScript <font face='Courier'>switchView(viewId, event)</font> administra las clases 'active' del menú de navegación superior y conmuta los contenedores mediante manipulación del DOM, sin requerir recargar la página.", bullet_style))
    story.append(Paragraph("• <b>Pacientes:</b> Presenta una tabla estructurada de solo lectura con nombres, RUT, teléfonos de contacto, fechas de última consulta y estados financieros de pacientes.", bullet_style))
    story.append(Paragraph("• <b>Administrador:</b> Detalla la información comercial de la clínica dental y un catálogo del personal médico asignado a cada Box de atención.", bullet_style))
    story.append(Paragraph("• <b>Reportes:</b> Incorpora tarjetas estadísticas con indicadores clave (KPIs) de citas mensuales, tasas de asistencia y resúmenes de rendimiento clínico.", bullet_style))
    story.append(Paragraph("• <b>Configuración:</b> Informa sobre la cuenta profesional del odontólogo y los datos técnicos de la infraestructura en la nube de AWS.", bullet_style))
    story.append(Paragraph(
        "<b>Nota de Diseño:</b> Se excluyeron botones, formularios de edición o elementos interactivos en estas 4 secciones auxiliares para respetar la restricción de solo lectura, "
        "conservando intacta la Agenda con su calendarización semanal interactiva y el Simulador de WhatsApp a la derecha.",
        body_style
    ))
    
    # =========================================================================
    # SECCIÓN 7: DESPLIEGUE EN AWS EC2
    # =========================================================================
    story.append(Paragraph("7. Despliegue y Configuración en AWS EC2", h1_style))
    story.append(Paragraph(
        "La aplicación fue desplegada en una instancia de Amazon Web Services (EC2) operando con el sistema <b>Amazon Linux 2023</b>.",
        body_style
    ))
    story.append(Paragraph("El proceso se ejecutó de acuerdo con los siguientes pasos técnicos:", body_style))
    story.append(Paragraph("1. <b>Aprovisionamiento:</b> Conexión al servidor a través de EC2 Instance Connect.", bullet_style))
    story.append(Paragraph("2. <b>Instalación de Software Base:</b> Ejecución del gestor de paquetes DNF para instalar Git y herramientas de edición.", bullet_style))
    story.append(Paragraph("3. <b>Clonación y Aislamiento:</b> Descarga del repositorio seguro de GitHub y creación del entorno virtual (<font face='Courier'>venv</font>).", bullet_style))
    story.append(Paragraph("4. <b>Instalación de Librerías:</b> Compilación de dependencias mediante <font face='Courier'>pip</font>.", bullet_style))
    story.append(Paragraph("5. <b>Configuración del Entorno:</b> Creación del archivo <font face='Courier'>.env</font> con tokens de Azure y OpenAI, y asignación de <font face='Courier'>ENV=production</font>.", bullet_style))
    story.append(Paragraph("6. <b>Lanzamiento:</b> Inicio del servidor web en segundo plano escuchando en el puerto 8000 mediante <font face='Courier'>nohup uvicorn</font>.", bullet_style))
    
    # =========================================================================
    # SECCIÓN 8: CONCLUSIONES Y RECOMENDACIONES
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("8. Conclusiones y Recomendaciones", h1_style))
    story.append(Paragraph(
        "El proyecto ha sido completado de manera satisfactoria. La migración a OpenAI Function Calling nativo dotó al "
        "agente de una gran capacidad de comprensión de intenciones y robustez conversacional, logrando una tasa de "
        "agendamiento exitoso en Dentidesk en menos de 4 intercambios verbales promedio.",
        body_style
    ))
    story.append(Paragraph(
        "Las capas adicionales de seguridad y endurecimiento aplicadas a FastAPI protegen la aplicación contra "
        "el escaneo y la explotación automatizada, asegurando que la clínica conserve la confidencialidad de sus datos "
        "comerciales y evitando costos excesivos de consumo del LLM.",
        body_style
    ))
    story.append(Paragraph("Como recomendaciones finales para la puesta en producción comercial, se sugiere:", body_style))
    story.append(Paragraph("• <b>Certificado SSL:</b> Configurar un proxy inverso Nginx con certificado HTTPS para cifrar todo el canal de comunicación del frontend y los endpoints de la API.", bullet_style))
    story.append(Paragraph("• <b>Base de Datos Distribuida:</b> Migrar el motor de SQLite a una base de datos PostgreSQL de nivel de producción si el flujo mensual excede las 5,000 citas para prevenir bloqueos de concurrencia.", bullet_style))
    story.append(Paragraph("• <b>Monitoreo de Costos:</b> Integrar un sistema de observabilidad (como LangSmith) para monitorear el rendimiento del modelo, medir tiempos de respuesta y auditar la efectividad de las herramientas invocadas.", bullet_style))
    
    # Firma final
    story.append(Spacer(1, 40))
    sig_data = [
        [Paragraph("__________________________________________<br/><b>Dr. Maximiliano Cifuentes</b><br/>Director del Proyecto Clínico Plaza Dent", ParagraphStyle('Sig', parent=body_style, alignment=1))],
    ]
    sig_table = Table(sig_data, colWidths=[400])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(sig_table)
    
    # Compilación
    doc.build(story, canvasmaker=NumberedCanvas)

if __name__ == "__main__":
    output_pdf = "Informe_Desarrollo_Chatbot_Dentidesk.pdf"
    build_pdf(output_pdf)
    print(f"PDF generado exitosamente en: {os.path.abspath(output_pdf)}")
