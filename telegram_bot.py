#!/usr/bin/env python3
"""
Telegram бот для создания заявок (задач) в системе Lifeline.
Использует long polling (без webhooks).
Запускается автоматически вместе с приложением в отдельном потоке.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from database import SessionLocal
import models

# Флаг для остановки бота
_bot_running = False
_bot_thread: Optional[threading.Thread] = None


# Состояния диалога
STATE_IDLE = "idle"
STATE_WAITING_TITLE = "waiting_title"
STATE_WAITING_DESCRIPTION = "waiting_description"
STATE_WAITING_PHOTOS = "waiting_photos"
STATE_CONFIRM = "confirm"

# Файл для хранения состояний (переживает перезапуск)
STATES_FILE = os.path.join(os.path.dirname(__file__), ".telegram_states.json")

def _load_states() -> Dict[int, Dict[str, Any]]:
    """Загрузить состояния из файла"""
    try:
        if os.path.exists(STATES_FILE):
            with open(STATES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Конвертировать ключи обратно в int
                return {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f"[TG Bot] Error loading states: {e}")
    return {}

def _save_states(states: Dict[int, Dict[str, Any]]):
    """Сохранить состояния в файл"""
    try:
        with open(STATES_FILE, "w", encoding="utf-8") as f:
            # Конвертировать ключи в str для JSON
            json.dump({str(k): v for k, v in states.items()}, f, ensure_ascii=False)
    except Exception as e:
        print(f"[TG Bot] Error saving states: {e}")

# Хранилище состояний пользователей
user_states: Dict[int, Dict[str, Any]] = _load_states()


def get_db() -> Session:
    return SessionLocal()


def get_setting(db: Session, key: str) -> Optional[str]:
    setting = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    return setting.value if setting else None


def get_bot_token() -> Optional[str]:
    db = get_db()
    try:
        return get_setting(db, "telegram_bot_token")
    finally:
        db.close()


def get_default_project_id() -> Optional[int]:
    db = get_db()
    try:
        val = get_setting(db, "telegram_default_project_id")
        return int(val) if val else None
    finally:
        db.close()


def get_default_stage_id() -> Optional[int]:
    db = get_db()
    try:
        val = get_setting(db, "telegram_default_stage_id")
        return int(val) if val else None
    finally:
        db.close()


def telegram_api(token: str, method: str, data: dict = None, timeout: int = 30) -> Optional[dict]:
    """Вызов Telegram Bot API"""
    url = f"https://api.telegram.org/bot{token}/{method}"
    
    if data:
        payload = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
    else:
        request = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result if result.get("ok") else None
    except Exception as e:
        print(f"Telegram API error: {e}")
        return None


def send_message(token: str, chat_id: int, text: str, reply_markup: dict = None) -> bool:
    """Отправить сообщение"""
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    result = telegram_api(token, "sendMessage", data)
    if not result:
        print(f"[TG Bot] Failed to send message to {chat_id}")
    return result is not None


def download_file(token: str, file_id: str) -> Optional[bytes]:
    """Скачать файл из Telegram"""
    result = telegram_api(token, "getFile", {"file_id": file_id})
    if not result or "result" not in result:
        return None
    
    file_path = result["result"].get("file_path")
    if not file_path:
        return None
    
    url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read()
    except Exception as e:
        print(f"Download file error: {e}")
        return None


def get_user_state(chat_id: int) -> Dict[str, Any]:
    """Получить состояние пользователя"""
    global user_states
    if chat_id not in user_states:
        user_states[chat_id] = {
            "state": STATE_IDLE,
            "title": None,
            "description": None,
            "photos": []
        }
        _save_states(user_states)
    return user_states[chat_id]


def reset_user_state(chat_id: int):
    """Сбросить состояние пользователя"""
    global user_states
    user_states[chat_id] = {
        "state": STATE_IDLE,
        "title": None,
        "description": None,
        "photos": []
    }
    _save_states(user_states)


def update_user_state(chat_id: int):
    """Сохранить изменённое состояние"""
    global user_states
    _save_states(user_states)


def create_task_from_telegram(
    title: str,
    description: str,
    photos: list,
    telegram_user_id: int,
    telegram_username: str = None
) -> Optional[int]:
    """Создать задачу в БД"""
    db = get_db()
    try:
        project_id = get_default_project_id()
        stage_id = get_default_stage_id()
        
        if not project_id:
            # Найти первый проект
            project = db.query(models.Project).first()
            if not project:
                print("No projects found")
                return None
            project_id = project.id
        
        if not stage_id:
            # Найти начальный этап проекта
            stage = db.query(models.Stage).filter(
                models.Stage.project_id == project_id
            ).order_by(models.Stage.order).first()
            if not stage:
                print("No stages found")
                return None
            stage_id = stage.id
        
        # Найти пользователя по Telegram username
        author_id = None
        if telegram_username:
            # Ищем по полю telegram (может содержать @username или просто username)
            user = db.query(models.User).filter(
                (models.User.telegram == telegram_username) |
                (models.User.telegram == f"@{telegram_username}")
            ).first()
            if user:
                author_id = user.id
                print(f"[TG Bot] Found user by telegram @{telegram_username}: {user.username} (id={user.id})")
        
        # Добавить информацию о Telegram пользователе в описание (если автор не найден)
        full_description = description or ""
        if not author_id:
            tg_info = f"\n\n---\nЗаявка из Telegram"
            if telegram_username:
                tg_info += f" от @{telegram_username}"
            tg_info += f" (ID: {telegram_user_id})"
            full_description += tg_info
        
        # Создать задачу
        task = models.Task(
            project_id=project_id,
            stage_id=stage_id,
            title=title,
            description=full_description,
            priority=1,  # Обычный приоритет
            author_id=author_id
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Сохранить фотографии как вложения
        uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        
        for photo_data in photos:
            file_content = photo_data.get("content")
            if not file_content:
                continue
            
            # Генерировать имя файла
            ext = ".jpg"
            stored_filename = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(uploads_dir, stored_filename)
            
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            attachment = models.TaskAttachment(
                task_id=task.id,
                filename=f"telegram_photo_{photo_data.get('index', 0)}.jpg",
                stored_filename=stored_filename,
                file_size=len(file_content),
                mime_type="image/jpeg",
                uploaded_by=author_id
            )
            db.add(attachment)
        
        # Добавить запись в историю
        history = models.TaskHistory(
            task_id=task.id,
            user_id=author_id,
            action="created",
            description=f"Задача создана через Telegram бот" + (f" (@{telegram_username})" if telegram_username else "")
        )
        db.add(history)
        
        db.commit()
        
        return task.id
        
    except Exception as e:
        print(f"Error creating task: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def handle_start(token: str, chat_id: int, user: dict):
    """Обработка команды /start"""
    username = user.get("first_name", "Пользователь")
    
    text = f"""👋 Привет, <b>{username}</b>!

Я бот для создания заявок в системе <b>Lifeline</b>.

<b>Доступные команды:</b>
/newticket - Создать новую заявку
/mytickets - Мои заявки
/history - История по заявке (например: /history 123)
/cancel - Отменить текущее действие

Чтобы создать заявку, отправьте команду /newticket"""
    
    send_message(token, chat_id, text)


def handle_newticket(token: str, chat_id: int):
    """Начать создание заявки"""
    state = get_user_state(chat_id)
    state["state"] = STATE_WAITING_TITLE
    state["title"] = None
    state["description"] = None
    state["photos"] = []
    state["photo_ids"] = []  # Храним только file_id для JSON
    update_user_state(chat_id)
    
    text = """📝 <b>Создание новой заявки</b>

<b>Шаг 1 из 3:</b> Введите тему заявки (краткое описание проблемы):"""
    
    send_message(token, chat_id, text)


def handle_cancel(token: str, chat_id: int):
    """Отменить создание заявки"""
    reset_user_state(chat_id)
    send_message(token, chat_id, "❌ Создание заявки отменено.\n\nДля создания новой заявки отправьте /newticket")


def show_help(token: str, chat_id: int):
    """Показать справку по командам"""
    text = """🤖 <b>Доступные команды:</b>

/newticket - Создать новую заявку
/mytickets - Мои заявки
/history 123 - История по заявке
/help - Показать это сообщение
/cancel - Отменить текущее действие

💡 <i>Чтобы создать заявку, отправьте</i> /newticket"""
    
    send_message(token, chat_id, text)


def find_user_by_telegram(db, telegram_username: str):
    """Найти пользователя по Telegram username"""
    if not telegram_username:
        return None
    # Ищем по полю telegram (может содержать @username или просто username)
    user = db.query(models.User).filter(
        (models.User.telegram == telegram_username) |
        (models.User.telegram == f"@{telegram_username}")
    ).first()
    return user


def handle_mytickets(token: str, chat_id: int, user: dict):
    """Показать список заявок пользователя"""
    telegram_username = user.get("username")
    
    if not telegram_username:
        send_message(token, chat_id, "⚠️ У вас не установлен username в Telegram. Установите его в настройках Telegram.")
        return
    
    db = get_db()
    try:
        # Найти пользователя по telegram
        db_user = find_user_by_telegram(db, telegram_username)
        
        if not db_user:
            send_message(token, chat_id, f"⚠️ Пользователь с Telegram @{telegram_username} не найден в системе.\n\nУкажите ваш Telegram username в профиле системы.")
            return
        
        # Получить задачи пользователя (не в архиве)
        tasks = db.query(models.Task).join(models.Stage).filter(
            models.Task.author_id == db_user.id,
            models.Task.is_archived == False
        ).order_by(models.Task.created_at.desc()).limit(20).all()
        
        if not tasks:
            send_message(token, chat_id, "📋 У вас нет активных заявок.\n\nДля создания заявки: /newticket")
            return
        
        text = f"📋 <b>Ваши заявки</b> ({len(tasks)}):\n\n"
        
        # Inline кнопки для просмотра истории
        buttons = []
        
        for task in tasks:
            stage_name = task.stage.name if task.stage else "Без этапа"
            # Эмодзи для статуса
            if task.stage and task.stage.is_final:
                status_emoji = "✅"
            else:
                status_emoji = "🔄"
            
            # Исполнитель
            assignee_name = ""
            if task.assignee:
                assignee_name = task.assignee.full_name or task.assignee.username
            
            text += f"{status_emoji} <b>#{task.id}</b> {task.title[:40]}\n"
            text += f"   Статус: <i>{stage_name}</i>\n"
            if assignee_name:
                text += f"   👤 Исполнитель: {assignee_name}\n"
            else:
                text += f"   👤 Исполнитель: <i>не назначен</i>\n"
            text += "\n"
            
            # Добавить кнопку (максимум 10 кнопок)
            if len(buttons) < 10:
                buttons.append([{"text": f"📖 #{task.id}", "callback_data": f"history_{task.id}"}])
        
        text += "👆 Нажмите на номер заявки для просмотра истории"
        
        keyboard = {"inline_keyboard": buttons} if buttons else None
        send_message(token, chat_id, text, keyboard)
        
    finally:
        db.close()


def handle_history(token: str, chat_id: int, task_id: int, user: dict):
    """Показать историю заявки"""
    telegram_username = user.get("username")
    
    db = get_db()
    try:
        # Найти задачу
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        
        if not task:
            send_message(token, chat_id, f"❌ Заявка #{task_id} не найдена.")
            return
        
        # Проверить доступ (автор или telegram username совпадает)
        db_user = find_user_by_telegram(db, telegram_username) if telegram_username else None
        
        if db_user and task.author_id == db_user.id:
            # Пользователь - автор задачи, доступ разрешён
            pass
        else:
            send_message(token, chat_id, f"⚠️ У вас нет доступа к заявке #{task_id}.")
            return
        
        # Получить историю
        history = db.query(models.TaskHistory).filter(
            models.TaskHistory.task_id == task_id
        ).order_by(models.TaskHistory.created_at.desc()).limit(15).all()
        
        stage_name = task.stage.name if task.stage else "Без этапа"
        
        text = f"📖 <b>Заявка #{task_id}</b>\n"
        text += f"<b>{task.title}</b>\n"
        text += f"Статус: <i>{stage_name}</i>\n\n"
        
        if history:
            text += "<b>История изменений:</b>\n\n"
            for h in history:
                # Форматировать дату
                date_str = h.created_at.strftime("%d.%m.%Y %H:%M") if h.created_at else ""
                
                # Действие
                action_map = {
                    "created": "🆕 Создана",
                    "updated": "✏️ Изменена",
                    "stage_changed": "📦 Этап изменён",
                    "comment_added": "💬 Комментарий",
                    "attachment_added": "📎 Файл добавлен",
                    "assigned": "👤 Назначена"
                }
                action_text = action_map.get(h.action, h.action)
                
                # Автор изменения
                author_name = ""
                if h.user_id:
                    author = db.query(models.User).filter(models.User.id == h.user_id).first()
                    if author:
                        author_name = f" ({author.full_name or author.username})"
                
                text += f"<code>{date_str}</code>\n"
                text += f"{action_text}{author_name}\n"
                if h.description:
                    text += f"<i>{h.description[:100]}</i>\n"
                text += "\n"
        else:
            text += "<i>История пуста</i>"
        
        send_message(token, chat_id, text)
        
    finally:
        db.close()


def handle_text_message(token: str, chat_id: int, text: str, user: dict):
    """Обработка текстового сообщения"""
    state = get_user_state(chat_id)
    current_state = state["state"]
    
    print(f"[TG Bot] chat_id={chat_id}, state={current_state}, text={text[:50]}")
    
    if current_state == STATE_WAITING_TITLE:
        if len(text) < 3:
            send_message(token, chat_id, "⚠️ Тема слишком короткая. Введите минимум 3 символа:")
            return
        
        state["title"] = text
        state["state"] = STATE_WAITING_DESCRIPTION
        update_user_state(chat_id)
        print(f"[TG Bot] chat_id={chat_id} -> STATE_WAITING_DESCRIPTION")
        
        msg = f"""✅ Тема: <b>{text}</b>

<b>Шаг 2 из 3:</b> Введите подробное описание проблемы:"""
        send_message(token, chat_id, msg)
        
    elif current_state == STATE_WAITING_DESCRIPTION:
        state["description"] = text
        state["state"] = STATE_WAITING_PHOTOS
        update_user_state(chat_id)
        
        msg = f"""✅ Описание сохранено.

<b>Шаг 3 из 3:</b> Отправьте скриншоты (фото) для заявки.

Когда закончите, нажмите кнопку <b>"Готово"</b> или отправьте /done"""
        
        keyboard = {
            "inline_keyboard": [
                [{"text": "✅ Готово - создать заявку", "callback_data": "done"}],
                [{"text": "❌ Отмена", "callback_data": "cancel"}]
            ]
        }
        send_message(token, chat_id, msg, keyboard)
        
    elif current_state == STATE_WAITING_PHOTOS:
        if text.lower() in ["/done", "готово", "done"]:
            finalize_ticket(token, chat_id, user)
        else:
            send_message(token, chat_id, "📷 Отправьте фото или нажмите <b>Готово</b> для создания заявки.")
    
    elif current_state == STATE_CONFIRM:
        if text.lower() in ["да", "yes", "подтвердить"]:
            finalize_ticket(token, chat_id, user)
        else:
            send_message(token, chat_id, "Нажмите кнопку для подтверждения или /cancel для отмены.")
    
    else:
        # Состояние IDLE - показать справку
        show_help(token, chat_id)


def handle_photo(token: str, chat_id: int, photo_list: list):
    """Обработка фото"""
    state = get_user_state(chat_id)
    
    if state["state"] != STATE_WAITING_PHOTOS:
        send_message(token, chat_id, "Фото можно отправлять только при создании заявки.\nОтправьте /newticket")
        return
    
    # Берём фото наибольшего размера
    if not photo_list:
        return
    
    best_photo = max(photo_list, key=lambda p: p.get("file_size", 0))
    file_id = best_photo.get("file_id")
    
    if not file_id:
        return
    
    # Сохраняем только file_id (content скачаем при финализации)
    if "photo_ids" not in state:
        state["photo_ids"] = []
    state["photo_ids"].append(file_id)
    update_user_state(chat_id)
    
    count = len(state["photo_ids"])
    keyboard = {
        "inline_keyboard": [
            [{"text": f"✅ Готово ({count} фото)", "callback_data": "done"}],
            [{"text": "❌ Отмена", "callback_data": "cancel"}]
        ]
    }
    send_message(token, chat_id, f"📷 Фото #{count} добавлено. Отправьте ещё или нажмите <b>Готово</b>.", keyboard)


def handle_callback(token: str, chat_id: int, callback_data: str, callback_query_id: str, user: dict):
    """Обработка callback от inline кнопок"""
    # Ответить на callback чтобы убрать "часики"
    telegram_api(token, "answerCallbackQuery", {"callback_query_id": callback_query_id})
    
    if callback_data == "done":
        finalize_ticket(token, chat_id, user)
    elif callback_data == "cancel":
        handle_cancel(token, chat_id)
    elif callback_data.startswith("history_"):
        # Показать историю задачи
        try:
            task_id = int(callback_data.replace("history_", ""))
            handle_history(token, chat_id, task_id, user)
        except ValueError:
            pass


def finalize_ticket(token: str, chat_id: int, user: dict):
    """Завершить создание заявки"""
    state = get_user_state(chat_id)
    
    if not state["title"]:
        send_message(token, chat_id, "⚠️ Тема заявки не указана. Начните заново: /newticket")
        reset_user_state(chat_id)
        return
    
    # Скачать фото по file_id
    photo_ids = state.get("photo_ids", [])
    photos = []
    for idx, file_id in enumerate(photo_ids):
        content = download_file(token, file_id)
        if content:
            photos.append({
                "file_id": file_id,
                "content": content,
                "index": idx + 1
            })
    state["photos"] = photos
    
    # Показать превью
    photos_count = len(photos)
    preview = f"""📋 <b>Предпросмотр заявки:</b>

<b>Тема:</b> {state['title']}

<b>Описание:</b>
{state['description'] or '(не указано)'}

<b>Скриншотов:</b> {photos_count}

Создаю заявку..."""
    
    send_message(token, chat_id, preview)
    
    # Создать задачу
    task_id = create_task_from_telegram(
        title=state["title"],
        description=state["description"],
        photos=state["photos"],
        telegram_user_id=chat_id,
        telegram_username=user.get("username")
    )
    
    if task_id:
        msg = f"""✅ <b>Заявка успешно создана!</b>

Номер заявки: <b>#{task_id}</b>

Спасибо за обращение! Мы свяжемся с вами в ближайшее время.

Для создания новой заявки: /newticket"""
        send_message(token, chat_id, msg)
    else:
        send_message(token, chat_id, "❌ Ошибка при создании заявки. Попробуйте позже или обратитесь к администратору.")
    
    reset_user_state(chat_id)


def process_update(token: str, update: dict):
    """Обработка одного update от Telegram"""
    print(f"[TG Bot] Received update: {update.get('update_id')}")
    
    # Обработка callback_query (нажатие inline кнопок)
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = cq["message"]["chat"]["id"]
        callback_data = cq.get("data", "")
        callback_query_id = cq["id"]
        user = cq.get("from", {})
        handle_callback(token, chat_id, callback_data, callback_query_id, user)
        return
    
    message = update.get("message")
    if not message:
        return
    
    chat_id = message["chat"]["id"]
    user = message.get("from", {})
    text = message.get("text", "")
    
    # Команды
    if text.startswith("/start"):
        handle_start(token, chat_id, user)
    elif text.startswith("/newticket") or text.startswith("/заявка"):
        handle_newticket(token, chat_id)
    elif text.startswith("/mytickets") or text.startswith("/мои"):
        handle_mytickets(token, chat_id, user)
    elif text.startswith("/history") or text.startswith("/история"):
        # Извлечь номер задачи из команды
        parts = text.split()
        if len(parts) >= 2:
            try:
                task_id = int(parts[1].replace("#", ""))
                handle_history(token, chat_id, task_id, user)
            except ValueError:
                send_message(token, chat_id, "⚠️ Укажите номер заявки.\nПример: /history 123")
        else:
            send_message(token, chat_id, "⚠️ Укажите номер заявки.\nПример: /history 123")
    elif text.startswith("/cancel") or text.startswith("/отмена"):
        handle_cancel(token, chat_id)
    elif text.startswith("/help") or text.startswith("/помощь"):
        show_help(token, chat_id)
    elif text.startswith("/done"):
        state = get_user_state(chat_id)
        if state["state"] == STATE_WAITING_PHOTOS:
            finalize_ticket(token, chat_id, user)
        else:
            send_message(token, chat_id, "Нечего завершать. Отправьте /newticket для создания заявки.")
    elif "photo" in message:
        handle_photo(token, chat_id, message["photo"])
    elif text:
        handle_text_message(token, chat_id, text, user)


def run_polling():
    """Запуск бота в режиме long polling"""
    global _bot_running
    
    print("=" * 50)
    print("Telegram Bot для Lifeline")
    print("=" * 50)
    
    token = get_bot_token()
    if not token:
        print("⚠️  Telegram бот: токен не задан в настройках. Бот не запущен.")
        print("   Укажите токен на странице /settings")
        return
    
    print(f"Токен бота: {token[:10]}...")
    
    # Проверить бота
    me = telegram_api(token, "getMe")
    if not me:
        print("⚠️  Telegram бот: не удалось подключиться к API. Проверьте токен.")
        return
    
    bot_info = me.get("result", {})
    print(f"✓ Telegram бот запущен: @{bot_info.get('username', 'unknown')}")
    
    # Очистить очередь обновлений (избежать конфликта 409)
    try:
        telegram_api(token, "getUpdates", {"offset": -1, "timeout": 0}, timeout=5)
    except:
        pass
    
    print("-" * 50)
    
    offset = 0
    _bot_running = True
    error_count = 0
    
    while _bot_running:
        try:
            # Проверяем токен каждую итерацию (может измениться в настройках)
            current_token = get_bot_token()
            if not current_token:
                print("⚠️  Telegram бот: токен удалён из настроек. Остановка...")
                break
            
            result = telegram_api(current_token, "getUpdates", {
                "offset": offset,
                "timeout": 10,
                "allowed_updates": ["message", "callback_query"]
            }, timeout=15)
            
            if result and "result" in result:
                updates = result["result"]
                error_count = 0  # Сбросить счётчик ошибок при успешном получении
                if updates:
                    print(f"[TG Bot] Got {len(updates)} update(s)")
                for update in updates:
                    offset = update["update_id"] + 1
                    try:
                        process_update(current_token, update)
                    except Exception as e:
                        print(f"Telegram bot error processing update: {e}")
                        import traceback
                        traceback.print_exc()
            
        except KeyboardInterrupt:
            print("\nTelegram бот остановлен.")
            break
        except urllib.error.HTTPError as e:
            if e.code == 409:
                # Conflict - другой экземпляр бота уже работает
                error_count += 1
                if error_count >= 3:
                    print("⚠️  Telegram бот: конфликт (409). Возможно запущен другой экземпляр. Остановка...")
                    break
                time.sleep(2)
            elif _bot_running:
                print(f"Telegram bot HTTP error: {e}")
                time.sleep(5)
        except Exception as e:
            if _bot_running:
                print(f"Telegram bot polling error: {e}")
                time.sleep(5)
    
    _bot_running = False
    print("Telegram бот завершил работу.")


_lock_file = None

def start_bot_thread():
    """Запустить бота в отдельном потоке"""
    global _bot_thread, _bot_running, _lock_file
    
    if _bot_thread and _bot_thread.is_alive():
        print("Telegram бот уже запущен в этом процессе.")
        return
    
    # Файл-блокировка чтобы только один процесс запускал бота
    lock_path = os.path.join(os.path.dirname(__file__), ".telegram_bot.lock")
    try:
        # Пытаемся создать lock-файл эксклюзивно
        _lock_file = open(lock_path, "w")
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError, ImportError):
        print("Telegram бот: уже запущен в другом процессе (пропуск)")
        if _lock_file:
            _lock_file.close()
            _lock_file = None
        return
    
    _bot_running = True
    _bot_thread = threading.Thread(target=run_polling, daemon=True)
    _bot_thread.start()


def stop_bot_thread():
    """Остановить бота"""
    global _bot_running, _lock_file
    _bot_running = False
    
    # Освободить блокировку
    if _lock_file:
        try:
            _lock_file.close()
        except:
            pass
        _lock_file = None
    
    print("Telegram бот: остановка...")


def is_bot_running() -> bool:
    """Проверить работает ли бот"""
    return _bot_running and _bot_thread is not None and _bot_thread.is_alive()


if __name__ == "__main__":
    run_polling()

