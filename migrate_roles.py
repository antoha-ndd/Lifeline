"""
Миграция для добавления справочника ролей
Добавляет колонку role_id в таблицу users и создает таблицу roles
"""
import sqlite3
import os

DB_PATH = "taskmanager.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"База данных {DB_PATH} не найдена")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли таблица roles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='roles'")
        if cursor.fetchone() is None:
            print("Создание таблицы roles...")
            cursor.execute("""
                CREATE TABLE roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL UNIQUE,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX ix_roles_name ON roles(name)")
            print("Таблица roles создана")
        else:
            print("Таблица roles уже существует")
        
        # Проверяем, существует ли колонка role_id в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'role_id' not in columns:
            print("Добавление колонки role_id в таблицу users...")
            cursor.execute("ALTER TABLE users ADD COLUMN role_id INTEGER")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_role_id ON users(role_id)")
            # SQLite не поддерживает ADD CONSTRAINT FOREIGN KEY после создания таблицы
            # Внешний ключ будет проверяться на уровне приложения через SQLAlchemy
            print("Колонка role_id добавлена")
        else:
            print("Колонка role_id уже существует")
        
        conn.commit()
        print("Миграция успешно завершена!")
        
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при миграции: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

