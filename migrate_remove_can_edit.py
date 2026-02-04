"""
Миграция для удаления колонки can_edit из таблицы field_stage_role_permissions
Теперь наличие правила означает право на редактирование
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
        # Проверяем, существует ли таблица field_stage_role_permissions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='field_stage_role_permissions'")
        if cursor.fetchone() is None:
            print("Таблица field_stage_role_permissions не существует, миграция не требуется")
            return
        
        # Проверяем, существует ли колонка can_edit
        cursor.execute("PRAGMA table_info(field_stage_role_permissions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'can_edit' in columns:
            print("Удаление колонки can_edit из таблицы field_stage_role_permissions...")
            # SQLite не поддерживает DROP COLUMN напрямую, нужно пересоздать таблицу
            cursor.execute("""
                CREATE TABLE field_stage_role_permissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_definition_id INTEGER NOT NULL,
                    stage_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    FOREIGN KEY (field_definition_id) REFERENCES field_definitions(id),
                    FOREIGN KEY (stage_id) REFERENCES stages(id),
                    FOREIGN KEY (role_id) REFERENCES roles(id)
                )
            """)
            
            # Копируем данные без can_edit
            cursor.execute("""
                INSERT INTO field_stage_role_permissions_new (id, field_definition_id, stage_id, role_id)
                SELECT id, field_definition_id, stage_id, role_id
                FROM field_stage_role_permissions
            """)
            
            # Удаляем старую таблицу и переименовываем новую
            cursor.execute("DROP TABLE field_stage_role_permissions")
            cursor.execute("ALTER TABLE field_stage_role_permissions_new RENAME TO field_stage_role_permissions")
            
            # Восстанавливаем индексы
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_field_stage_role_permissions_field_definition_id ON field_stage_role_permissions(field_definition_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_field_stage_role_permissions_stage_id ON field_stage_role_permissions(stage_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_field_stage_role_permissions_role_id ON field_stage_role_permissions(role_id)")
            
            print("Колонка can_edit удалена")
        else:
            print("Колонка can_edit уже удалена")
        
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

