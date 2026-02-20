"""
Миграция для добавления поля is_archived в таблицу projects
"""
import sqlite3


def migrate():
    conn = sqlite3.connect('taskmanager.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(projects)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'is_archived' not in columns:
        print("Adding 'is_archived' column to projects table...")
        cursor.execute("ALTER TABLE projects ADD COLUMN is_archived BOOLEAN DEFAULT 0")
        conn.commit()
        print("Column 'is_archived' added successfully!")
    else:
        print("Column 'is_archived' already exists.")

    conn.close()


if __name__ == "__main__":
    migrate()

