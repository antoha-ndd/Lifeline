from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import urllib.request
import urllib.error

from database import get_db
from auth import get_current_active_user
import models
import schemas

router = APIRouter(prefix="/api/settings", tags=["settings"])

TELEGRAM_TOKEN_KEY = "telegram_bot_token"
TELEGRAM_TEST_CHAT_ID_KEY = "telegram_test_chat_id"
TELEGRAM_DEFAULT_PROJECT_KEY = "telegram_default_project_id"
TELEGRAM_DEFAULT_STAGE_KEY = "telegram_default_stage_id"


def require_admin(current_user: models.User):
    if not current_user or (not current_user.is_admin and current_user.user_type != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access settings"
        )


def is_valid_telegram_chat_id(chat_id: str | None) -> bool:
    if chat_id is None:
        return True
    chat_id = str(chat_id).strip()
    if chat_id == "":
        return True
    if chat_id.startswith("-"):
        chat_id = chat_id[1:]
    return chat_id.isdigit()


def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
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


@router.get("/telegram-bot", response_model=schemas.TelegramBotSettings)
def get_telegram_bot_settings(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    require_admin(current_user)
    
    token_setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == TELEGRAM_TOKEN_KEY
    ).first()
    chat_id_setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == TELEGRAM_TEST_CHAT_ID_KEY
    ).first()
    project_setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == TELEGRAM_DEFAULT_PROJECT_KEY
    ).first()
    stage_setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == TELEGRAM_DEFAULT_STAGE_KEY
    ).first()
    
    return schemas.TelegramBotSettings(
        telegram_bot_token=token_setting.value if token_setting else None,
        telegram_test_chat_id=chat_id_setting.value if chat_id_setting else None,
        telegram_default_project_id=int(project_setting.value) if project_setting and project_setting.value else None,
        telegram_default_stage_id=int(stage_setting.value) if stage_setting and stage_setting.value else None
    )


def upsert_setting(db: Session, key: str, value) -> models.AppSetting:
    """Создать или обновить настройку"""
    setting = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
    str_value = str(value) if value is not None else None
    if not setting:
        setting = models.AppSetting(key=key, value=str_value)
        db.add(setting)
    else:
        setting.value = str_value
    return setting


@router.put("/telegram-bot", response_model=schemas.TelegramBotSettings)
def update_telegram_bot_settings(
    payload: schemas.TelegramBotSettings,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    require_admin(current_user)
    
    # Обновить токен
    upsert_setting(db, TELEGRAM_TOKEN_KEY, payload.telegram_bot_token)
    
    # Обновить chat id
    if payload.telegram_test_chat_id is not None:
        if not is_valid_telegram_chat_id(payload.telegram_test_chat_id):
            raise HTTPException(status_code=400, detail="Telegram chat id должен быть числом")
    upsert_setting(db, TELEGRAM_TEST_CHAT_ID_KEY, payload.telegram_test_chat_id)
    
    # Обновить проект по умолчанию
    if payload.telegram_default_project_id is not None:
        project = db.query(models.Project).filter(
            models.Project.id == payload.telegram_default_project_id
        ).first()
        if not project:
            raise HTTPException(status_code=400, detail="Проект не найден")
    upsert_setting(db, TELEGRAM_DEFAULT_PROJECT_KEY, payload.telegram_default_project_id)
    
    # Обновить этап по умолчанию
    if payload.telegram_default_stage_id is not None:
        stage = db.query(models.Stage).filter(
            models.Stage.id == payload.telegram_default_stage_id
        ).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Этап не найден")
    upsert_setting(db, TELEGRAM_DEFAULT_STAGE_KEY, payload.telegram_default_stage_id)
    
    db.commit()
    
    # Вернуть актуальные настройки
    return get_telegram_bot_settings(current_user, db)


@router.post("/telegram-bot/test")
def test_telegram_bot(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    require_admin(current_user)
    
    token_setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == TELEGRAM_TOKEN_KEY
    ).first()
    chat_id_setting = db.query(models.AppSetting).filter(
        models.AppSetting.key == TELEGRAM_TEST_CHAT_ID_KEY
    ).first()
    
    if not token_setting or not token_setting.value:
        raise HTTPException(status_code=400, detail="Токен Telegram бота не задан")
    
    if not chat_id_setting or not is_valid_telegram_chat_id(chat_id_setting.value):
        raise HTTPException(status_code=400, detail="Укажите числовой Telegram Chat ID в настройках приложения")
    
    ok = send_telegram_message(
        token_setting.value,
        chat_id_setting.value,
        "✅ Проверка Telegram бота: сообщение доставлено."
    )
    
    if not ok:
        raise HTTPException(status_code=400, detail="Не удалось отправить сообщение в Telegram")
    
    return {"message": "Test message sent"}

