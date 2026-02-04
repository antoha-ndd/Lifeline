from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

from database import engine, SessionLocal
import models
from auth import get_password_hash
from routers import auth, projects, tasks, attachments, users, organizations, departments, roles, field_permissions, notifications, task_links, settings
import telegram_bot

# Create tables
models.Base.metadata.create_all(bind=engine)

# Create uploads directory
import os
os.makedirs("uploads", exist_ok=True)

app = FastAPI(title="Lifeline", version="1.0.0")

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(attachments.router)
app.include_router(users.router)
app.include_router(organizations.router)
app.include_router(departments.router)
app.include_router(roles.router)
app.include_router(field_permissions.router)
app.include_router(notifications.router)
app.include_router(task_links.router)
app.include_router(settings.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/login")
async def login_page():
    return FileResponse("static/login.html")


@app.get("/register")
async def register_page():
    return FileResponse("static/register.html")


@app.get("/projects")
async def projects_page():
    return FileResponse("static/projects.html")


@app.get("/project/{project_id}")
async def project_page(project_id: int):
    return FileResponse("static/project.html")


@app.get("/kanban/{project_id}")
async def kanban_page(project_id: int):
    return FileResponse("static/kanban.html")


@app.get("/history/{project_id}")
async def history_page(project_id: int):
    return FileResponse("static/history.html")


@app.get("/users")
async def users_page():
    return FileResponse("static/users.html")


@app.get("/profile")
async def profile_page():
    return FileResponse("static/profile.html")


@app.get("/settings")
async def settings_page():
    return FileResponse("static/settings.html")


@app.get("/organizations")
async def organizations_page():
    return FileResponse("static/organizations.html")


@app.get("/departments")
async def departments_page():
    return FileResponse("static/departments.html")


@app.get("/links/{task_id}")
async def links_map_page(task_id: int):
    return FileResponse("static/links-map.html")


@app.on_event("startup")
async def startup_event():
    """Create default admin user, test data and start Telegram bot"""
    # Start Telegram bot in background thread
    telegram_bot.start_bot_thread()
    
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin:
            # Create admin user
            admin = models.User(
                username="admin",
                email="admin@example.com",
                full_name="Administrator",
                hashed_password=get_password_hash("admin123"),
                user_type="admin",
                is_admin=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            
            # Create test user
            user1 = models.User(
                username="user1",
                email="user1@example.com",
                full_name="Test User",
                hashed_password=get_password_hash("user123"),
                user_type="user"
            )
            db.add(user1)
            db.commit()
            db.refresh(user1)
            
            # Create demo project
            project = models.Project(
                name="Демо проект",
                description="Пример проекта для демонстрации возможностей системы"
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            
            # Create stages
            stages_data = [
                ("Бэклог", 0, "#94a3b8"),
                ("В работе", 1, "#3b82f6"),
                ("На проверке", 2, "#f59e0b"),
                ("Готово", 3, "#22c55e")
            ]
            stages = []
            for name, order, color in stages_data:
                stage = models.Stage(
                    project_id=project.id,
                    name=name,
                    order=order,
                    color=color
                )
                db.add(stage)
                stages.append(stage)
            db.commit()
            for s in stages:
                db.refresh(s)
            
            # Create custom fields
            fields_data = [
                ("Приоритет", "select", {"options": ["Низкий", "Средний", "Высокий", "Критичный"]}),
                ("Оценка времени", "number", None),
                ("Тип задачи", "select", {"options": ["Баг", "Фича", "Улучшение", "Документация"]}),
                ("Метки", "multiselect", {"options": ["Frontend", "Backend", "Дизайн", "Тестирование"]}),
            ]
            for name, ftype, options in fields_data:
                field = models.FieldDefinition(
                    project_id=project.id,
                    name=name,
                    field_type=ftype,
                    options=options
                )
                db.add(field)
            db.commit()
            
            # Create demo tasks
            tasks_data = [
                ("Настроить базу данных", "Создать структуру БД и миграции", stages[3].id, 2),
                ("Создать API авторизации", "JWT токены, регистрация, логин", stages[3].id, 2),
                ("Дизайн интерфейса", "Создать макеты основных страниц", stages[2].id, 1),
                ("Разработка Kanban доски", "Реализовать drag-and-drop", stages[1].id, 3),
                ("Фильтрация задач", "Добавить фильтры по полям", stages[1].id, 1),
                ("Документация API", "Написать документацию endpoints", stages[0].id, 0),
                ("Тестирование", "Написать unit тесты", stages[0].id, 0),
                ("Деплой на сервер", "Настроить CI/CD", stages[0].id, 1),
            ]
            for title, desc, stage_id, priority in tasks_data:
                task = models.Task(
                    project_id=project.id,
                    stage_id=stage_id,
                    title=title,
                    description=desc,
                    priority=priority,
                    assignee_id=admin.id if priority > 1 else user1.id
                )
                db.add(task)
            db.commit()
            
            # Give user1 permission to project
            permission = models.Permission(
                user_id=user1.id,
                project_id=project.id,
                permission_type="write"
            )
            db.add(permission)
            db.commit()
            
            print("✓ Demo data created successfully")
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop Telegram bot on shutdown"""
    telegram_bot.stop_bot_thread()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

