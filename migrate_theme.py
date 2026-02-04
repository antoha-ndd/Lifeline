"""
Миграция для добавления поля theme в таблицу users
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('taskmanager.db')
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'theme' not in columns:
        print("Adding 'theme' column to users table...")
        cursor.execute("ALTER TABLE users ADD COLUMN theme VARCHAR(20) DEFAULT 'dark'")
        conn.commit()
        print("Column 'theme' added successfully!")
    else:
        print("Column 'theme' already exists.")
    
    conn.close()

if __name__ == "__main__":
    migrate()

