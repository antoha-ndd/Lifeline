#!/usr/bin/env python3
"""
Миграция для изменения поля role_id в таблице field_stage_role_permissions,
чтобы оно могло быть NULL (для правил, действующих для всех ролей).
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
            WHERE type='table' AND name='field_stage_role_permissions'
        """)
        
        if not cursor.fetchone():
            print("Таблица field_stage_role_permissions не найдена. Пропускаем миграцию.")
            return
        
        # Проверяем текущую структуру таблицы
        cursor.execute("PRAGMA table_info(field_stage_role_permissions)")
        columns = cursor.fetchall()
        
        role_id_column = None
        for col in columns:
            if col[1] == 'role_id':
                role_id_column = col
                break
        
        if not role_id_column:
            print("Колонка role_id не найдена. Пропускаем миграцию.")
            return
        
        # Если колонка уже nullable (notnull = 0), миграция не нужна
        if role_id_column[3] == 0:
            print("Колонка role_id уже nullable. Миграция не требуется.")
            return
        
        print("Начинаем миграцию role_id в nullable...")
        
        # SQLite не поддерживает ALTER COLUMN напрямую, поэтому нужно:
        # 1. Создать новую таблицу с нужной структурой
        # 2. Скопировать данные
        # 3. Удалить старую таблицу
        # 4. Переименовать новую таблицу
        
        # Создаем новую таблицу с nullable role_id
        cursor.execute("""
            CREATE TABLE field_stage_role_permissions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_definition_id INTEGER NOT NULL,
                stage_id INTEGER,
                role_id INTEGER,
                FOREIGN KEY (field_definition_id) REFERENCES field_definitions(id),
                FOREIGN KEY (stage_id) REFERENCES stages(id),
                FOREIGN KEY (role_id) REFERENCES roles(id)
            )
        """)
        
        # Копируем данные
        cursor.execute("""
            INSERT INTO field_stage_role_permissions_new 
            (id, field_definition_id, stage_id, role_id)
            SELECT id, field_definition_id, stage_id, role_id
            FROM field_stage_role_permissions
        """)
        
        # Удаляем старую таблицу
        cursor.execute("DROP TABLE field_stage_role_permissions")
        
        # Переименовываем новую таблицу
        cursor.execute("""
            ALTER TABLE field_stage_role_permissions_new 
            RENAME TO field_stage_role_permissions
        """)
        
        # Восстанавливаем индексы, если они были
        # (SQLite автоматически создаст индексы для внешних ключей)
        
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

