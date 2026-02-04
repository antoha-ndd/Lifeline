#!/usr/bin/env python3
"""
Миграция для добавления настроек Telegram-уведомлений пользователю.
"""

import sqlite3
import os
import json

DB_PATH = "taskmanager.db"

DEFAULT_NOTIFY_TYPES = [
    "task_assigned",
    "task_updated",
    "stage_changed",
    "comment_added",
    "attachment_added"
]


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        if not column_exists(cursor, "users", "telegram_chat_id"):
            cursor.execute("ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR(100)")
        
        if not column_exists(cursor, "users", "telegram_notify_types"):
            cursor.execute("ALTER TABLE users ADD COLUMN telegram_notify_types TEXT")
            cursor.execute(
                "UPDATE users SET telegram_notify_types = ? WHERE telegram_notify_types IS NULL",
                (json.dumps(DEFAULT_NOTIFY_TYPES),)
            )
        
        conn.commit()
        print("Миграция Telegram-уведомлений завершена.")
    except Exception as e:
        conn.rollback()
        print(f"Ошибка миграции: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"База данных {DB_PATH} не найдена.")
    else:
        migrate()

