// ================= VARIABLES GLOBALES DE ESTADO =================
let currentActivePhone = "";
let activeSessions = [];
let pendingOutboxMessages = [];
let calendarSchedule = [];

// Calendario Configuración
let currentWeekStart = (() => {
    const today = new Date();
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(today.setDate(diff));
    monday.setHours(0, 0, 0, 0);
    return monday;
})();
let calendarDates = [];


const TIME_SLOTS = [
    "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
    "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30", "17:00", "17:30", "18:00"
];

// ================= INICIALIZACIÓN AL CARGAR LA PÁGINA =================
document.addEventListener("DOMContentLoaded", () => {
    updateCalendarDates();
    initModalSelectors();
    
    // Iniciar polling continuo cada 3 segundos
    setInterval(pollSystemData, 3000);
});

// Inicializar selectores dinámicos en el modal (días, meses, horas)
function initModalSelectors() {
    const daySelect = document.getElementById("book-date-day");
    const monthSelect = document.getElementById("book-date-month");
    const yearSelect = document.getElementById("book-date-year");
    const hourSelect = document.getElementById("book-time-hour");
    
    // Días 1-31
    for (let d = 1; d <= 31; d++) {
        const opt = document.createElement("option");
        opt.value = d < 10 ? `0${d}` : `${d}`;
        opt.textContent = d;
        daySelect.appendChild(opt);
    }
    
    // Meses
    const meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    meses.forEach((m, idx) => {
        const opt = document.createElement("option");
        opt.value = idx + 1 < 10 ? `0${idx + 1}` : `${idx + 1}`;
        opt.textContent = m;
        monthSelect.appendChild(opt);
    });
    
    // Años
    for (let y = 2026; y <= 2028; y++) {
        const opt = document.createElement("option");
        opt.value = y;
        opt.textContent = y;
        yearSelect.appendChild(opt);
    }
    
    // Horas (08 a 18)
    for (let h = 8; h <= 18; h++) {
        const opt = document.createElement("option");
        opt.value = h < 10 ? `0${h}` : `${h}`;
        opt.textContent = h < 10 ? `0${h}` : `${h}`;
        hourSelect.appendChild(opt);
    }
}

// ================= MANEJO DE VISTAS Y AUTENTICACIÓN SIMULADA =================
function handleLogin(event) {
    event.preventDefault();
    
    // Simular login exitoso
    document.getElementById("login-screen").classList.remove("active");
    document.getElementById("dashboard-screen").classList.add("active");
    
    // Cargar datos iniciales
    pollSystemData();
}

// Ocultar/mostrar contraseña en el login
document.querySelector(".toggle-password").addEventListener("click", function() {
    const passInput = document.getElementById("password");
    const icon = this.querySelector("i");
    if (passInput.type === "password") {
        passInput.type = "text";
        icon.classList.remove("fa-eye");
        icon.classList.add("fa-eye-slash");
    } else {
        passInput.type = "password";
        icon.classList.remove("fa-eye-slash");
        icon.classList.add("fa-eye");
    }
});

// ================= SISTEMA DE POLLING (SINK DE DATOS DE API) =================
async function pollSystemData() {
    // Solo si el dashboard está visible
    if (!document.getElementById("dashboard-screen").classList.contains("active")) {
        return;
    }
    
    try {
        // Cargar sesiones activas
        const resSessions = await fetch("/api/sessions");
        activeSessions = await resSessions.json();
        updateActiveChatsDropdown();

        // Cargar mensajes pendientes de outbox
        const resOutbox = await fetch("/api/outbox");
        pendingOutboxMessages = await resOutbox.json();
        renderOutboxStatus();

        // Si hay una sesión activa, cargar su chat
        if (currentActivePhone) {
            loadChatHistory(currentActivePhone);
        }

        // Cargar agenda de Dentidesk
        const resSchedule = await fetch("/api/schedule");
        calendarSchedule = await resSchedule.json();
        renderWeeklyCalendar();
        
    } catch (e) {
        console.error("Error polling data: ", e);
    }
}

// ================= SIMULADOR DE CHATS Y MENSAJES (WHATSAPP) =================

// Iniciar una conversación simulada desde un anuncio
async function startSimulatedChat() {
    const adType = document.getElementById("sim-ad-type").value;
    const phone = document.getElementById("sim-phone").value.trim();
    
    if (!phone) {
        alert("Ingresa un número de teléfono válido.");
        return;
    }
    
    let message = "Hola, buenas tardes.";
    if (adType === "protesis_acrilicas") {
        message = "Hola, vi su anuncio sobre la promo de prótesis dentales acrílicas y me interesa.";
    } else if (adType === "limpieza_dental") {
        message = "Hola, me interesa la promoción de limpieza dental y evaluación por $19.990.";
    } else if (adType === "extraccion_muelas_juicio") {
        message = "Hola, me gustaría cotizar la extracción de muelas del juicio.";
    }
    
    try {
        const res = await fetch("/api/simulate-incoming", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: jsonPayload = JSON.stringify({
                phone_number: phone,
                message: message,
                referral: adType !== "libre" ? adType : null
            })
        });
        
        if (res.ok) {
            currentActivePhone = phone;
            pollSystemData();
        }
    } catch (e) {
        console.error("Error starting chat: ", e);
    }
}

// Cambiar de chat activo
function switchChatSession(phone) {
    currentActivePhone = phone;
    if (phone) {
        loadChatHistory(phone);
    } else {
        renderPlaceholderChat();
    }
}

// Cargar historial del chat seleccionado
async function loadChatHistory(phone) {
    try {
        const res = await fetch(`/api/history/${phone}`);
        const history = await res.json();
        
        const session = activeSessions.find(s => s.phone_number === phone);
        const stateStr = session ? session.state.toUpperCase() : "DESCONOCIDO";
        
        document.getElementById("chat-current-title").textContent = `Chat: +${phone}`;
        const stateBadge = document.getElementById("chat-current-state");
        stateBadge.textContent = `Estado: ${stateStr}`;
        
        // Estilizar badge según estado
        stateBadge.className = "state-badge";
        if (session) {
            stateBadge.classList.add(`state-${session.state}`);
        }
        
        // Mostrar botón de vaciar chat
        document.getElementById("btn-clear-chat").style.display = "inline-flex";
        
        const box = document.getElementById("chat-messages-box");
        box.innerHTML = "";
        
        if (history.length === 0) {
            box.innerHTML = `<div class="chat-placeholder"><p>No hay mensajes en este chat.</p></div>`;
            return;
        }
        
        history.forEach(msg => {
            const bubble = document.createElement("div");
            bubble.className = `chat-bubble ${msg.role}`;
            
            const textSpan = document.createElement("span");
            textSpan.textContent = msg.content;
            bubble.appendChild(textSpan);
            
            const timeSpan = document.createElement("span");
            timeSpan.className = "chat-bubble-time";
            const dt = new Date(msg.timestamp);
            timeSpan.textContent = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            bubble.appendChild(timeSpan);
            
            box.appendChild(bubble);
        });
        
        // Desplazarse al final
        box.scrollTop = box.scrollHeight;
        
    } catch (e) {
        console.error("Error loading history: ", e);
    }
}

// Renderizar placeholder cuando no hay chat
function renderPlaceholderChat() {
    document.getElementById("chat-current-title").textContent = "Ningún chat seleccionado";
    document.getElementById("chat-current-state").textContent = "Estado: -";
    document.getElementById("chat-current-state").className = "state-badge";
    
    // Ocultar botón de vaciar chat
    document.getElementById("btn-clear-chat").style.display = "none";
    
    document.getElementById("chat-messages-box").innerHTML = `
        <div class="chat-placeholder">
            <i class="fa-regular fa-comments"></i>
            <p>Inicia un chat o selecciona un paciente activo para ver la simulación de la conversación en tiempo real.</p>
        </div>
    `;
}

// Enviar un mensaje simulado de paciente
async function sendSimulatedPatientMessage() {
    const input = document.getElementById("patient-message-input");
    const msg = input.value.trim();
    if (!msg || !currentActivePhone) return;
    
    try {
        const res = await fetch("/api/simulate-incoming", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                phone_number: currentActivePhone,
                message: msg
            })
        });
        
        if (res.ok) {
            input.value = "";
            pollSystemData();
        }
    } catch (e) {
        console.error("Error sending message: ", e);
    }
}

function handleChatInputKey(event) {
    if (event.key === "Enter") {
        sendSimulatedPatientMessage();
    }
}

// Actualizar el dropdown de chats activos
function updateActiveChatsDropdown() {
    const dropdown = document.getElementById("active-chats-dropdown");
    const currentValue = dropdown.value;
    
    dropdown.innerHTML = `<option value="">Selecciona un chat activo...</option>`;
    
    activeSessions.forEach(session => {
        const opt = document.createElement("option");
        opt.value = session.phone_number;
        
        const treatmentName = session.treatment_context ? session.treatment_context.replace("_", " ") : "general";
        opt.textContent = `+${session.phone_number} (Promo: ${treatmentName} - Estado: ${session.state})`;
        dropdown.appendChild(opt);
    });
    
    dropdown.value = currentValue;
}

// Renderizar estado de mensajes en cola (outbox) con cuenta regresiva
function renderOutboxStatus() {
    const container = document.getElementById("outbox-status-container");
    container.innerHTML = "";
    
    // Filtrar los mensajes pendientes de la sesión activa
    const pendingMsg = pendingOutboxMessages.filter(m => m.status === "pending" && m.phone_number === currentActivePhone);
    
    pendingMsg.forEach(msg => {
        const div = document.createElement("div");
        div.className = "outbox-pending-item";
        
        // Calcular segundos restantes
        const sendAt = new Date(msg.send_at);
        const now = new Date();
        const diffSec = Math.max(0, Math.round((sendAt - now) / 1000));
        
        div.innerHTML = `
            <span><i class="fa-solid fa-ellipsis-stroke"></i> Max está redactando una respuesta...</span>
            <strong>Enviando en ${diffSec}s</strong>
        `;
        container.appendChild(div);
    });
}

// ================= RENDERIZADO DE LA AGENDA (WEEKLY CALENDAR) =================
function renderWeeklyCalendar() {
    const tbody = document.getElementById("calendar-body");
    tbody.innerHTML = "";
    
    // Crear matriz de ocupación [filas][columnas]
    const numRows = TIME_SLOTS.length;
    const numCols = calendarDates.length;
    
    const occupiedMatrix = Array(numRows).fill(null).map(() => Array(numCols).fill(null));
    
    // Rellenar matriz de ocupación basada en los agendamientos de Dentidesk
    calendarSchedule.forEach(item => {
        // Formato slot_start: 'YYYY-MM-DD HH:MM'
        const parts = item.slot_start.split(" ");
        const dateStr = parts[0];
        const timeStr = parts[1];
        
        const colIdx = calendarDates.indexOf(dateStr);
        const rowIdx = TIME_SLOTS.indexOf(timeStr);
        
        if (colIdx !== -1 && rowIdx !== -1) {
            const spanRows = Math.ceil(item.duration_minutes / 30);
            
            // Colocar información en la celda de inicio
            occupiedMatrix[rowIdx][colIdx] = {
                item: item,
                span: spanRows
            };
            
            // Marcar celdas cubiertas por el rowspan como 'spanned'
            for (let r = 1; r < spanRows; r++) {
                if (rowIdx + r < numRows) {
                    occupiedMatrix[rowIdx + r][colIdx] = "spanned";
                }
            }
        }
    });
    
    // Dibujar grilla fila por fila
    for (let r = 0; r < numRows; r++) {
        const tr = document.createElement("tr");
        
        // Celda de hora (columna 1)
        const tdTime = document.createElement("td");
        tdTime.className = "time-cell";
        tdTime.textContent = TIME_SLOTS[r];
        tr.appendChild(tdTime);
        
        // Celdas de días (columnas 2 a 8)
        for (let c = 0; c < numCols; c++) {
            const cellState = occupiedMatrix[r][c];
            
            if (cellState === "spanned") {
                // No dibujar celda porque está cubierta por un rowspan
                continue;
            }
            
            const td = document.createElement("td");
            const date = calendarDates[c];
            const time = TIME_SLOTS[r];
            
            if (cellState) {
                // Hay una cita agendada
                const appointment = cellState.item;
                td.rowSpan = cellState.span;
                
                const card = document.createElement("div");
                card.className = `appointment-card ${appointment.event_type}`;
                
                // Si es un paciente y no está confirmado, agregar clase para borde rojo
                if (appointment.event_type === "patient") {
                    card.classList.add("no-confirmado");
                }
                
                // Contenido de la tarjeta
                const titleDiv = document.createElement("div");
                titleDiv.className = "appointment-title";
                titleDiv.textContent = appointment.title;
                card.appendChild(titleDiv);
                
                const metaDiv = document.createElement("div");
                metaDiv.className = "appointment-meta";
                
                // Iconos de estado
                let statusHtml = "";
                if (appointment.event_type === "blocked") {
                    statusHtml = `<span class="status-icon"><i class="fa-solid fa-lock"></i></span> Bloqueado`;
                } else {
                    // Cita de Paciente
                    statusHtml = `<span class="status-icon no-conf"><i class="fa-solid fa-circle-minus"></i></span> No confirmado`;
                }
                
                metaDiv.innerHTML = `${statusHtml} (${appointment.duration_minutes} min)`;
                card.appendChild(metaDiv);
                
                td.appendChild(card);
            } else {
                // Celda vacía interactiva
                const emptyDiv = document.createElement("div");
                emptyDiv.className = "slot-empty";
                emptyDiv.onclick = () => openBookingModal(date, time);
                td.appendChild(emptyDiv);
            }
            
            tr.appendChild(td);
        }
        
        tbody.appendChild(tr);
    }
}

// ================= MANEJO DEL MODAL DE AGENDAMIENTO =================
function openBookingModal(dateStr, timeStr) {
    const modal = document.getElementById("booking-modal");
    modal.classList.add("active");
    
    // Configurar campos del formulario según la fecha y hora seleccionada
    const parts = dateStr.split("-"); // YYYY-MM-DD
    document.getElementById("book-date-year").value = parts[0];
    document.getElementById("book-date-month").value = parts[1];
    document.getElementById("book-date-day").value = parts[2];
    
    const timeParts = timeStr.split(":"); // HH:MM
    document.getElementById("book-time-hour").value = timeParts[0];
    document.getElementById("book-time-minute").value = timeParts[1];
    
    // Duración por defecto según el motivo seleccionado
    updateModalDuration();
    
    // Limpiar campos
    document.getElementById("book-nombres").value = "";
    document.getElementById("book-apellidos").value = "";
    document.getElementById("book-rut").value = "";
    document.getElementById("book-email").value = "";
    document.getElementById("book-phone").value = "";
    document.getElementById("book-notes").value = "";
    document.getElementById("book-status").value = "No confirmado";
}

function closeBookingModal() {
    document.getElementById("booking-modal").classList.remove("active");
}

// Ajustar duración por defecto según tratamiento
document.getElementById("book-treatment").addEventListener("change", updateModalDuration);

function updateModalDuration() {
    const treatment = document.getElementById("book-treatment").value;
    const durInput = document.getElementById("book-duration");
    
    if (treatment === "limpieza_dental") {
        durInput.value = 30; // 30 mins para evaluaciones
    } else {
        durInput.value = 60; // 1 hora para prótesis y muelas
    }
}

// Guardar cita desde el modal
async function saveBooking(event) {
    event.preventDefault();
    
    const nombres = document.getElementById("book-nombres").value.trim();
    const apellidos = document.getElementById("book-apellidos").value.trim();
    const rut = document.getElementById("book-rut").value.trim();
    const email = document.getElementById("book-email").value.trim();
    const phone = document.getElementById("book-phone").value.trim();
    const doctor = document.getElementById("book-doctor").value;
    const treatment = document.getElementById("book-treatment").value;
    const duration = document.getElementById("book-duration").value;
    const notes = document.getElementById("book-notes").value.trim();
    
    // Recuperar fecha y hora
    const year = document.getElementById("book-date-year").value;
    const month = document.getElementById("book-date-month").value;
    const day = document.getElementById("book-date-day").value;
    const hour = document.getElementById("book-time-hour").value;
    const minute = document.getElementById("book-time-minute").value;
    
    const slotStr = `${year}-${month}-${day} ${hour}:${minute}`;
    
    try {
        const res = await fetch("/api/book", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                patient_name: `${nombres} ${apellidos}`,
                patient_rut: rut,
                patient_phone: phone,
                slot_str: slotStr,
                treatment: treatment,
                duration_minutes: parseInt(duration),
                notes: notes
            })
        });
        
        if (res.ok) {
            closeBookingModal();
            pollSystemData();
        } else {
            const errData = await res.json();
            alert(`Error: ${errData.detail}`);
        }
    } catch (e) {
        console.error("Error saving booking: ", e);
    }
}

async function resetSystem() {
    const conf = confirm("¿Estás seguro de que deseas limpiar la base de datos? Esto borrará todos los chats activos, el outbox y los registros simulados de Dentidesk.");
    if (!conf) return;
    
    try {
        const res = await fetch("/api/reset", { method: "POST" });
        if (res.ok) {
            currentActivePhone = "";
            renderPlaceholderChat();
            pollSystemData();
            alert("Sistema reiniciado con éxito.");
        }
    } catch (e) {
        console.error("Error resetting system: ", e);
    }
}

// ================= NAVEGACIÓN Y OPERACIONES DE CHAT =================

function updateCalendarDates() {
    calendarDates = [];
    for (let i = 0; i < 7; i++) {
        const d = new Date(currentWeekStart);
        d.setDate(currentWeekStart.getDate() + i);
        
        // Formato YYYY-MM-DD en hora local
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        calendarDates.push(`${y}-${m}-${day}`);
    }
    
    // Actualizar el título de la semana: "8 — 14 de Jun. de 2026"
    const startD = new Date(currentWeekStart);
    const endD = new Date(currentWeekStart);
    endD.setDate(startD.getDate() + 6);
    
    const meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const titleText = `${startD.getDate()} — ${endD.getDate()} de ${meses[startD.getMonth()]}. de ${startD.getFullYear()}`;
    document.getElementById("calendar-week-title").textContent = titleText;
    
    // Actualizar cabecera de la tabla
    const headerRow = document.getElementById("calendar-header-row");
    const diasSemana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
    let headerHtml = `<th class="col-time">Hora</th>`;
    
    calendarDates.forEach((dateStr, idx) => {
        // Parsear fecha manteniendo hora local
        const parts = dateStr.split("-");
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        headerHtml += `<th>${diasSemana[idx]}. ${d.getDate()}/${d.getMonth() + 1}</th>`;
    });
    headerRow.innerHTML = headerHtml;
}

function changeWeek(offset) {
    currentWeekStart.setDate(currentWeekStart.getDate() + (offset * 7));
    updateCalendarDates();
    pollSystemData();
}

async function clearActiveChat() {
    if (!currentActivePhone) return;
    const conf = confirm(`¿Estás seguro de que deseas vaciar el historial de chat del número +${currentActivePhone} y reiniciar su estado de agendamiento?`);
    if (!conf) return;
    
    try {
        const res = await fetch(`/api/clear-chat/${currentActivePhone}`, { method: "POST" });
        if (res.ok) {
            loadChatHistory(currentActivePhone);
            pollSystemData();
        }
    } catch (e) {
        console.error("Error clearing chat: ", e);
    }
}

