# database.py
import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            service TEXT,
            price INTEGER,
            datetime TEXT,
            answers TEXT,
            extract_url TEXT,
            extract_msg_id INTEGER,
            screenshot_url TEXT,
            screenshot_msg_id INTEGER,
            status TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_user_data(user_id, field, value):
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    exists = cur.fetchone()
    
    if not exists:
        cur.execute('''
            INSERT INTO users (user_id, created_at, status)
            VALUES (?, ?, ?)
        ''', (user_id, datetime.now().isoformat(), "in_progress"))
    
    cur.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    data = cur.fetchone()
    conn.close()
    
    if data:
        columns = ["user_id", "service", "price", "datetime", 
                   "answers", "extract_url", "extract_msg_id", 
                   "screenshot_url", "screenshot_msg_id", "status", "created_at"]
        return dict(zip(columns, data))
    return None

def clear_user_data(user_id):
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_active_requests():
    conn = sqlite3.connect("appointments.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id, status FROM users WHERE status IN ('pending', 'confirmed') ORDER BY created_at DESC")
    data = cur.fetchall()
    conn.close()
    return data

init_db()