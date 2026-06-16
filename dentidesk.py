import sqlite3
import os
from datetime import datetime, timedelta
from database import DB_FILE, get_connection

def init_dentidesk_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla que representa el calendario interno de Dentidesk
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dentidesk_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slot_start TEXT UNIQUE, -- Formato: 'YYYY-MM-DD HH:MM'
        duration_minutes INTEGER,
        event_type TEXT, -- 'blocked' (e.g. Colegio) o 'patient'
        title TEXT,
        patient_rut TEXT,
        patient_phone TEXT
    )
    """)
    conn.commit()
    
    # Si la tabla está vacía, poblarla con bloqueos de prueba similares a la imagen de la clínica
    cursor.execute("SELECT COUNT(*) FROM dentidesk_schedule")
    if cursor.fetchone()[0] == 0:
        populate_mock_schedule(cursor)
        conn.commit()
        
    conn.close()

def populate_mock_schedule(cursor):
    # Calcular el lunes de la semana actual
    import datetime
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    
    # Formatear fechas relativas en formato 'YYYY-MM-DD'
    d_lun = monday.strftime("%Y-%m-%d")
    d_mar = (monday + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    d_mie = (monday + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    d_jue = (monday + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    d_vie = (monday + datetime.timedelta(days=4)).strftime("%Y-%m-%d")
    
    blocked_events = [
        # Lunes
        (f"{d_lun} 12:30", 60, "blocked", "Colegio"),
        (f"{d_lun} 14:30", 90, "blocked", "Citacion apoderado"),
        (f"{d_lun} 11:30", 30, "patient", "Oscar Ignacio"),
        
        # Martes
        (f"{d_mar} 09:30", 30, "patient", "marcelo gumera"),
        (f"{d_mar} 10:00", 105, "patient", "Erick Carlos Retamal Ruiz"),
        (f"{d_mar} 12:00", 30, "blocked", "Karla"),
        (f"{d_mar} 12:30", 60, "blocked", "Colegio"),
        (f"{d_mar} 14:00", 75, "patient", "Gladys Beatriz Aguero Haro"),
        (f"{d_mar} 15:30", 45, "patient", "Nelly Loncomilla ygor"),
        (f"{d_mar} 17:00", 60, "blocked", "Karla / mile"),
        
        # Miércoles
        (f"{d_mie} 10:00", 45, "patient", "Eudy Alberto González"),
        (f"{d_mie} 11:00", 65, "patient", "Felipe Ignacio Jara Galindo"),
        (f"{d_mie} 12:30", 60, "blocked", "Colegio"),
        (f"{d_mie} 15:00", 70, "blocked", "Mile"),
        (f"{d_mie} 17:00", 120, "blocked", "javier toledo"),
        
        # Jueves
        (f"{d_jue} 10:30", 45, "patient", "maria angelica lizana"),
        (f"{d_jue} 11:30", 60, "patient", "Margarita valenzuela seguel"),
        (f"{d_jue} 12:30", 60, "blocked", "Colegio"),
        (f"{d_jue} 14:30", 30, "blocked", "Karla"),
        (f"{d_jue} 16:30", 45, "patient", "marcelo gumera"),
        
        # Viernes
        (f"{d_vie} 09:30", 165, "patient", "Rosa Rodriguez Carcamo"),
        (f"{d_vie} 12:30", 60, "blocked", "Cole"),
        (f"{d_vie} 15:30", 45, "patient", "Sabina Castillo Gutiérrez"),
        (f"{d_vie} 16:30", 45, "patient", "Luis Alberto guerr"),
        (f"{d_vie} 17:30", 30, "patient", "Yesica Barria"),
    ]
    
    for slot_start, dur, ev_type, title in blocked_events:
        try:
            cursor.execute(
                "INSERT INTO dentidesk_schedule (slot_start, duration_minutes, event_type, title) VALUES (?, ?, ?, ?)",
                (slot_start, dur, ev_type, title)
            )
        except sqlite3.IntegrityError:
            pass

def get_available_slots(duration_minutes: int, days_ahead: int = 7) -> dict:
    """
    Retorna un diccionario agrupado por fecha con las horas de inicio libres.
    Las horas de atención son de 08:30 a 18:00 de Lunes a Sábado.
    Las citas deben caber en la agenda sin superponerse con eventos existentes.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener todas las citas y bloqueos de la BD
    cursor.execute("SELECT slot_start, duration_minutes FROM dentidesk_schedule")
    occupied_db = cursor.fetchall()
    conn.close()
    
    # Mapear ocupaciones: (start_datetime, end_datetime)
    occupied_ranges = []
    for row in occupied_db:
        start = datetime.strptime(row["slot_start"], "%Y-%m-%d %H:%M")
        end = start + timedelta(minutes=row["duration_minutes"])
        occupied_ranges.append((start, end))
        
    available_by_date = {}
    
    # Empezar a buscar desde hoy
    today = datetime.now()
    # Redondear la hora actual al siguiente bloque de 30 minutos
    if today.minute > 30:
        current_search_time = today.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif today.minute > 0:
        current_search_time = today.replace(minute=30, second=0, microsecond=0)
    else:
        current_search_time = today.replace(minute=0, second=0, microsecond=0)
        
    for d in range(days_ahead):
        day_date = (current_search_time + timedelta(days=d)).date()
        
        # No atendemos Domingos (día 6 de la semana en Python isoweekday es 7, Lunes=1, Sábado=6, Domingo=7)
        if day_date.isoweekday() == 7:
            continue
            
        date_str = day_date.strftime("%Y-%m-%d")
        available_by_date[date_str] = []
        
        # Horario de atención: 08:30 a 18:00
        start_work = datetime.combine(day_date, datetime.strptime("08:30", "%H:%M").time())
        end_work = datetime.combine(day_date, datetime.strptime("18:00", "%H:%M").time())
        
        # Si es el día de hoy, no ofrecer horas en el pasado
        if day_date == today.date():
            start_search = max(start_work, current_search_time)
        else:
            start_search = start_work
            
        # Proponer ranuras cada 30 minutos
        temp_time = start_search
        while temp_time + timedelta(minutes=duration_minutes) <= end_work:
            proposed_start = temp_time
            proposed_end = temp_time + timedelta(minutes=duration_minutes)
            
            # Verificar si se superpone con algún rango ocupado
            overlap = False
            for occ_start, occ_end in occupied_ranges:
                # Hay traslape si max(start1, start2) < min(end1, end2)
                if max(proposed_start, occ_start) < min(proposed_end, occ_end):
                    overlap = True
                    break
            
            if not overlap:
                available_by_date[date_str].append(proposed_start.strftime("%H:%M"))
                
            temp_time += timedelta(minutes=30)
            
        # Limpiar fechas vacías
        if not available_by_date[date_str]:
            del available_by_date[date_str]
            
    return available_by_date

def book_slot(phone_number: str, patient_name: str, patient_rut: str, patient_phone: str, slot_str: str, treatment: str, duration_minutes: int) -> bool:
    """
    Registra la cita en el simulador de Dentidesk.
    slot_str debe venir en formato 'YYYY-MM-DD HH:MM'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO dentidesk_schedule 
            (slot_start, duration_minutes, event_type, title, patient_rut, patient_phone) 
            VALUES (?, ?, 'patient', ?, ?, ?)
            """,
            (slot_str, duration_minutes, f"Cita: {patient_name} ({treatment})", patient_rut, patient_phone)
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

# Inicializar BD Dentidesk al importar
init_dentidesk_db()
