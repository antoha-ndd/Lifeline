from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os
import json
import urllib.request
import urllib.error

from database import get_db
from auth import get_current_active_user
import models
import schemas

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

NOTIFICATION_TYPE_LABELS = {
    "task_assigned": "Назначение задачи",
    "task_updated": "Изменение задачи",
    "stage_changed": "Смена этапа",
    "comment_added": "Новый комментарий",
    "attachment_added": "Новый файл"
}


def should_send_telegram(user: models.User, notification_type: str) -> bool:
    """Проверить настройки пользователя для Telegram-уведомлений"""
    if not user:
        return False
    notify_types = user.telegram_notify_types or []
    return notification_type in notify_types


def get_telegram_bot_token(db: Session) -> str | None:
    setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == "telegram_bot_token"
    ).first()
    if setting and setting.value:
        return setting.value
    return os.getenv("TELEGRAM_BOT_TOKEN")


def get_telegram_chat_id(db: Session) -> str | None:
    setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == "telegram_test_chat_id"
    ).first()
    if setting and setting.value:
        return setting.value
    return None


def send_telegram_message(token: str | None, chat_id: str, text: str) -> bool:
    """Отправить сообщение в Telegram через Bot API"""
    if not token or not chat_id or not text:
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }
    
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return False


def create_notification(
    db: Session,
    user_id: int,
    task_id: int,
    notification_type: str,
    title: str,
    message: str = None,
    actor_user_id: int | None = None
):
    """Создать уведомление для пользователя"""
    actor_name = None
    if actor_user_id:
        actor = db.query(models.User).filter(models.User.id == actor_user_id).first()
        if actor:
            actor_name = actor.full_name or actor.username
    
    details_parts = []
    if task_id:
        details_parts.append(f"Задача #{task_id}")
    if actor_name:
        details_parts.append(f"Автор действия: {actor_name}")
    details_text = "; ".join(details_parts) if details_parts else None
    
    if details_text:
        if message:
            message = f"{details_text}.\n{message}"
        else:
            message = details_text
    
    notification = models.Notification(
        user_id=user_id,
        task_id=task_id,
        notification_type=notification_type,
        title=title,
        message=message
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    
    # Send Telegram message if user enabled it
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user and should_send_telegram(user, notification_type):
        message_parts = [title]
        if message:
            message_parts.append(message)
        token = get_telegram_bot_token(db)
        chat_id = get_telegram_chat_id(db)
        send_telegram_message(token, chat_id, "\n".join(message_parts))
    
    return notification


@router.get("/", response_model=List[schemas.NotificationWithTask])
def get_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить уведомления текущего пользователя"""
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    
    notifications = query.order_by(
        models.Notification.created_at.desc()
    ).limit(limit).all()
    
    result = []
    for n in notifications:
        task_title = None
        project_id = None
        if n.task_id:
            task = db.query(models.Task).filter(models.Task.id == n.task_id).first()
            if task:
                task_title = task.title
                project_id = task.project_id
        
        result.append(schemas.NotificationWithTask(
            id=n.id,
            user_id=n.user_id,
            task_id=n.task_id,
            notification_type=n.notification_type,
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at,
            task_title=task_title,
            project_id=project_id
        ))
    
    return result


@router.get("/types")
def get_notification_types():
    """Получить список типов уведомлений для настройки"""
    return [
        {"type": ntype, "label": label}
        for ntype, label in NOTIFICATION_TYPE_LABELS.items()
    ]


@router.get("/unread-count")
def get_unread_count(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить количество непрочитанных уведомлений"""
    count = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).count()
    
    return {"count": count}


@router.post("/{notification_id}/read")
def mark_as_read(
    notification_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отметить уведомление как прочитанное"""
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    db.commit()
    
    return {"message": "Marked as read"}


@router.post("/read-all")
def mark_all_as_read(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Отметить все уведомления как прочитанные"""
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    
    return {"message": "All notifications marked as read"}


@router.delete("/delete-all")
def delete_all_notifications(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить все уведомления пользователя"""
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).delete()
    db.commit()
    
    return {"message": "All notifications deleted"}


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить уведомление"""
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    
    return {"message": "Notification deleted"}

