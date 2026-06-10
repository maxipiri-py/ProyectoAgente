import sqlite3
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plaza_dent.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de sesiones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        phone_number TEXT PRIMARY KEY,
        treatment_context TEXT,
        selected_slot TEXT,
        state TEXT DEFAULT 'greeting',
        patient_name TEXT,
        patient_rut TEXT,
        patient_phone TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    
    # Tabla de historial de chat
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT,
        role TEXT,
        content TEXT,
        timestamp TEXT,
        FOREIGN KEY (phone_number) REFERENCES sessions(phone_number)
    )
    """)
    
    # Tabla de cola de mensajes salientes (outbox)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone_number TEXT,
        content TEXT,
        send_at TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)
    
    conn.commit()
    conn.close()

def get_or_create_session(phone_number: str, initial_treatment: str = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM sessions WHERE phone_number = ?", (phone_number,))
    row = cursor.fetchone()
    
    now_str = datetime.now().isoformat()
    
    if not row:
        cursor.execute(
            """
            INSERT INTO sessions (phone_number, treatment_context, state, created_at, updated_at)
            VALUES (?, ?, 'greeting', ?, ?)
            """,
            (phone_number, initial_treatment, now_str, now_str)
        )
        conn.commit()
        cursor.execute("SELECT * FROM sessions WHERE phone_number = ?", (phone_number,))
        row = cursor.fetchone()
        
    session_dict = dict(row)
    conn.close()
    return session_dict

def update_session(phone_number: str, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    
    kwargs['updated_at'] = datetime.now().isoformat()
    fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [phone_number]
    
    cursor.execute(f"UPDATE sessions SET {fields} WHERE phone_number = ?", values)
    conn.commit()
    conn.close()

def add_chat_message(phone_number: str, role: str, content: str):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO chat_history (phone_number, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (phone_number, role, content, now_str)
    )
    conn.commit()
    conn.close()

def get_chat_history(phone_number: str, limit: int = 20) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT role, content FROM chat_history WHERE phone_number = ? ORDER BY id DESC LIMIT ?",
        (phone_number, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    
    # Retornar en orden cronológico
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def queue_outgoing_message(phone_number: str, content: str, delay_seconds: int):
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    send_at_epoch = now.timestamp() + delay_seconds
    send_at_str = datetime.fromtimestamp(send_at_epoch).isoformat()
    
    cursor.execute(
        "INSERT INTO outbox (phone_number, content, send_at, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (phone_number, content, send_at_str, now.isoformat())
    )
    conn.commit()
    conn.close()

def get_pending_messages() -> list:
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    
    cursor.execute(
        "SELECT * FROM outbox WHERE status = 'pending' AND send_at <= ?",
        (now_str,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_message_status(message_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE outbox SET status = ? WHERE id = ?",
        (status, message_id)
    )
    conn.commit()
    conn.close()

# Inicializar al importar
init_db()
