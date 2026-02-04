#!/usr/bin/env python3
"""
Миграция для создания таблицы notifications.
"""

import sqlite3
import os

DB_PATH = "taskmanager.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли таблица
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='notifications'
        """)
        
        if cursor.fetchone():
            print("Таблица notifications уже существует. Пропускаем миграцию.")
            return
        
        print("Создаём таблицу notifications...")
        
        cursor.execute("""
            CREATE TABLE notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER,
                notification_type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        # Создаём индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX idx_notifications_user_id ON notifications(user_id)
        """)
        cursor.execute("""
            CREATE INDEX idx_notifications_is_read ON notifications(is_read)
        """)
        cursor.execute("""
            CREATE INDEX idx_notifications_created_at ON notifications(created_at)
        """)
        
        conn.commit()
        print("Миграция успешно завершена!")
        
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при миграции: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"База данных {DB_PATH} не найдена.")
    else:
        migrate()

