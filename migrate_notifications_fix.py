#!/usr/bin/env python3
"""
Миграция для исправления таблицы notifications - добавление недостающих столбцов.
"""

import sqlite3
import os

DB_PATH = "taskmanager.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем текущую структуру таблицы
        cursor.execute("PRAGMA table_info(notifications)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Текущие столбцы: {columns}")
        
        # Добавляем недостающие столбцы
        columns_to_add = []
        
        if 'notification_type' not in columns:
            columns_to_add.append(("notification_type", "VARCHAR(50) NOT NULL DEFAULT 'task_updated'"))
        
        if 'title' not in columns:
            columns_to_add.append(("title", "VARCHAR(255) NOT NULL DEFAULT 'Уведомление'"))
        
        if 'message' not in columns:
            columns_to_add.append(("message", "TEXT"))
        
        if 'is_read' not in columns:
            columns_to_add.append(("is_read", "BOOLEAN DEFAULT 0"))
        
        if 'created_at' not in columns:
            columns_to_add.append(("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"))
        
        if 'user_id' not in columns:
            columns_to_add.append(("user_id", "INTEGER NOT NULL DEFAULT 0"))
        
        if 'task_id' not in columns:
            columns_to_add.append(("task_id", "INTEGER"))
        
        if not columns_to_add:
            print("Все столбцы уже существуют. Пропускаем миграцию.")
            return
        
        for col_name, col_def in columns_to_add:
            print(f"Добавляем столбец {col_name}...")
            cursor.execute(f"ALTER TABLE notifications ADD COLUMN {col_name} {col_def}")
        
        conn.commit()
        print("Миграция успешно завершена!")
        
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при миграции: {e}")
        
        # Если таблица существует но с неправильной структурой - пересоздаём её
        print("Пересоздаём таблицу notifications...")
        cursor.execute("DROP TABLE IF EXISTS notifications")
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at)")
        conn.commit()
        print("Таблица notifications пересоздана успешно!")
        
    finally:
        conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"База данных {DB_PATH} не найдена.")
    else:
        migrate()

