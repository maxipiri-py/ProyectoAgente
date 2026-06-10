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
    # Crear bloqueos para esta semana
    # Asumimos que hoy es 2026-06-09 (según el tiempo local del sistema)
    base_date = datetime(2026, 6, 8) # Lunes 8/6
    
    # Bloqueos fijos (naranja de la imagen)
    # Lunes 12:30 - 13:30 (Colegio), 14:30 - 16:00 (Citacion apoderado)
    # Martes 12:30 - 13:30 (Colegio)
    # Miércoles 12:30 - 13:30 (Colegio)
    # Jueves 12:30 - 13:30 (Colegio)
    # Viernes 12:30 - 13:30 (Colegio)
    
    blocked_events = [
        # Lunes 8
        ("2026-06-08 12:30", 60, "blocked", "Colegio"),
        ("2026-06-08 14:30", 90, "blocked", "Citacion apoderado"),
        ("2026-06-08 11:30", 30, "patient", "Oscar Ignacio"),
        
        # Martes 9
        ("2026-06-09 09:30", 30, "patient", "marcelo gumera"),
        ("2026-06-09 10:00", 105, "patient", "Erick Carlos Retamal Ruiz"),
        ("2026-06-09 12:00", 30, "blocked", "Karla"),
        ("2026-06-09 12:30", 60, "blocked", "Colegio"),
        ("2026-06-09 14:00", 75, "patient", "Gladys Beatriz Aguero Haro"),
        ("2026-06-09 15:30", 45, "patient", "Nelly Loncomilla ygor"),
        ("2026-06-09 17:00", 60, "blocked", "Karla / mile"),
        
        # Miércoles 10
        ("2026-06-10 10:00", 45, "patient", "Eudy Alberto González"),
        ("2026-06-10 11:00", 65, "patient", "Felipe Ignacio Jara Galindo"),
        ("2026-06-10 12:30", 60, "blocked", "Colegio"),
        ("2026-06-10 15:00", 70, "blocked", "Mile"),
        ("2026-06-10 17:00", 120, "blocked", "javier toledo"),
        
        # Jueves 11
        ("2026-06-11 10:30", 45, "patient", "maria angelica lizana"),
        ("2026-06-11 11:30", 60, "patient", "Margarita valenzuela seguel"),
        ("2026-06-11 12:30", 60, "blocked", "Colegio"),
        ("2026-06-11 14:30", 30, "blocked", "Karla"),
        ("2026-06-11 16:30", 45, "patient", "marcelo gumera"),
        
        # Viernes 12
        ("2026-06-12 09:30", 165, "patient", "Rosa Rodriguez Carcamo"),
        ("2026-06-12 12:30", 60, "blocked", "Cole"),
        ("2026-06-12 15:30", 45, "patient", "Sabina Castillo Gutiérrez"),
        ("2026-06-12 16:30", 45, "patient", "Luis Alberto guerr"),
        ("2026-06-12 17:30", 30, "patient", "Yesica Barria"),
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
