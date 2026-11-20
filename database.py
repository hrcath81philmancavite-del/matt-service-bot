import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                 name TEXT, 
                 contact_number TEXT,
                 is_active INTEGER DEFAULT 1,
                 joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 message TEXT,
                 is_from_user INTEGER,
                 timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS troubleshooting_records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER,
                 machine_model TEXT,
                 problem_description TEXT,
                 solution_given TEXT,
                 status TEXT,
                 final_outcome TEXT,
                 notes TEXT,
                 timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

def add_user(user_id, name, number=""):
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, name, contact_number) VALUES (?, ?, ?)",
              (user_id, name, number))
    conn.commit()
    conn.close()

def is_user_authorized(user_id):
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id = ? AND is_active = 1", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_message(user_id, message, is_from_user):
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (user_id, message, is_from_user) VALUES (?, ?, ?)",
              (user_id, message, is_from_user))
    conn.commit()
    conn.close()

def save_record(user_id, model, problem, solution, status="pending"):
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    c.execute('''INSERT INTO troubleshooting_records 
                 (user_id, machine_model, problem_description, solution_given, status)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, model, problem, solution, status))
    record_id = c.lastrowid
    conn.commit()
    conn.close()
    return record_id

def update_outcome(record_id, outcome, notes):
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    c.execute("UPDATE troubleshooting_records SET final_outcome = ?, notes = ?, status = 'completed' WHERE id = ?",
              (outcome, notes, record_id))
    conn.commit()
    conn.close()

def get_user_history(user_id, limit=10):
    conn = sqlite3.connect('xerox_bot.db')
    c = conn.cursor()
    c.execute("SELECT message, is_from_user, timestamp FROM chat_history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
              (user_id, limit))
    results = c.fetchall()
    conn.close()
    return results

if __name__ == "__main__":
    init_db()
