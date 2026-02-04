"""
Миграция для конвертации прав 'view' в 'read'
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('taskmanager.db')
    cursor = conn.cursor()
    
    # Update permissions table
    cursor.execute("UPDATE permissions SET permission_type = 'read' WHERE permission_type = 'view'")
    updated_permissions = cursor.rowcount
    
    # Update task_permissions table
    cursor.execute("UPDATE task_permissions SET permission_type = 'read' WHERE permission_type = 'view'")
    updated_task_permissions = cursor.rowcount
    
    # Update field_permissions table
    cursor.execute("UPDATE field_permissions SET permission_type = 'read' WHERE permission_type = 'view'")
    updated_field_permissions = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    print(f"Updated {updated_permissions} project permissions")
    print(f"Updated {updated_task_permissions} task permissions")
    print(f"Updated {updated_field_permissions} field permissions")
    print("Migration completed!")

if __name__ == "__main__":
    migrate()

