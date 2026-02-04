from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from database import get_db
import models
import schemas
from auth import (
    authenticate_user, create_access_token, get_password_hash,
    get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if username exists
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserWithDetails)
def get_me(current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    # Reload user with relationships to get organization and department
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    return db_user


@router.put("/me", response_model=schemas.UserWithDetails)
def update_me(
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить свой профиль (любой пользователь может редактировать свою контактную информацию и пароль)"""
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Users can only update their own contact info and password
    # They cannot change: username, user_type, is_active, is_blocked, organization_id, department_id
    
    # Check email uniqueness if changing email
    if user_update.email and user_update.email != db_user.email:
        existing_user = db.query(models.User).filter(models.User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # Update allowed fields
    if user_update.email is not None:
        db_user.email = user_update.email
    if user_update.full_name is not None:
        db_user.full_name = user_update.full_name
    if user_update.telegram is not None:
        db_user.telegram = user_update.telegram
    if user_update.telegram_notify_types is not None:
        db_user.telegram_notify_types = user_update.telegram_notify_types
    if user_update.phone is not None:
        db_user.phone = user_update.phone
    if user_update.password is not None:
        db_user.hashed_password = get_password_hash(user_update.password)
    if user_update.theme is not None:
        db_user.theme = user_update.theme
    
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/users", response_model=list[schemas.User])
def get_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    return db.query(models.User).filter(models.User.is_active == True).all()

