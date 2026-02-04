"""
Миграция для перехода от одной роли к множественным ролям
Создает таблицу user_roles для связи many-to-many
Переносит данные из role_id в user_roles
Удаляет колонку role_id из таблицы users
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
        # Проверяем, существует ли таблица user_roles
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_roles'")
        if cursor.fetchone() is None:
            print("Создание таблицы user_roles...")
            cursor.execute("""
                CREATE TABLE user_roles (
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, role_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_roles_user_id ON user_roles(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_roles_role_id ON user_roles(role_id)")
            print("Таблица user_roles создана")
        else:
            print("Таблица user_roles уже существует")
        
        # Проверяем, существует ли колонка role_id в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'role_id' in columns:
            print("Перенос данных из role_id в user_roles...")
            # Переносим данные из role_id в user_roles
            cursor.execute("""
                INSERT INTO user_roles (user_id, role_id)
                SELECT id, role_id
                FROM users
                WHERE role_id IS NOT NULL
            """)
            
            print("Удаление колонки role_id из таблицы users...")
            # SQLite не поддерживает DROP COLUMN напрямую, нужно пересоздать таблицу
            cursor.execute("""
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) UNIQUE,
                    email VARCHAR(100) UNIQUE,
                    hashed_password VARCHAR(255),
                    full_name VARCHAR(100),
                    telegram VARCHAR(100),
                    phone VARCHAR(20),
                    user_type VARCHAR(20) DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    is_admin BOOLEAN DEFAULT 0,
                    is_blocked BOOLEAN DEFAULT 0,
                    organization_id INTEGER,
                    department_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations(id),
                    FOREIGN KEY (department_id) REFERENCES departments(id)
                )
            """)
            
            # Копируем данные без role_id
            cursor.execute("""
                INSERT INTO users_new (id, username, email, hashed_password, full_name, telegram, phone, 
                                      user_type, is_active, is_admin, is_blocked, organization_id, department_id, created_at)
                SELECT id, username, email, hashed_password, full_name, telegram, phone, 
                       user_type, is_active, is_admin, is_blocked, organization_id, department_id, created_at
                FROM users
            """)
            
            # Удаляем старую таблицу и переименовываем новую
            cursor.execute("DROP TABLE users")
            cursor.execute("ALTER TABLE users_new RENAME TO users")
            
            # Восстанавливаем индексы
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users(username)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_organization_id ON users(organization_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_users_department_id ON users(department_id)")
            
            print("Колонка role_id удалена")
        else:
            print("Колонка role_id уже удалена")
        
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

