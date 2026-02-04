from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas

SECRET_KEY = "1222"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    if user.is_blocked:
        return False
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if current_user.is_blocked:
        raise HTTPException(status_code=403, detail="User is blocked")
    return current_user


def check_project_permission(
    db: Session,
    user: models.User,
    project_id: int,
    required_permission: str
) -> bool:
    if user.is_admin:
        return True
    
    permission = db.query(models.Permission).filter(
        models.Permission.user_id == user.id,
        models.Permission.project_id == project_id
    ).first()
    
    if not permission:
        return False
    
    # write includes read
    if permission.permission_type == "write":
        return True
    # read permission
    if permission.permission_type == "read" and required_permission == "read":
        return True
    
    return False


def check_task_permission(
    db: Session,
    user: models.User,
    task_id: int,
    required_permission: str
) -> bool:
    if user.is_admin:
        return True
    
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        return False
    
    # Check project permission first
    if check_project_permission(db, user, task.project_id, required_permission):
        return True
    
    # Check task-specific permission
    permission = db.query(models.TaskPermission).filter(
        models.TaskPermission.user_id == user.id,
        models.TaskPermission.task_id == task_id
    ).first()
    
    if not permission:
        return False
    
    if permission.permission_type == "write":
        return True
    if permission.permission_type == "read" and required_permission == "read":
        return True
    
    return False


def check_field_permission(
    db: Session,
    user: models.User,
    field_id: int,
    required_permission: str
) -> bool:
    if user.is_admin:
        return True
    
    field = db.query(models.FieldDefinition).filter(models.FieldDefinition.id == field_id).first()
    if not field:
        return False
    
    # Check project permission first
    if check_project_permission(db, user, field.project_id, required_permission):
        return True
    
    # Check field-specific permission
    permission = db.query(models.FieldPermission).filter(
        models.FieldPermission.user_id == user.id,
        models.FieldPermission.field_definition_id == field_id
    ).first()
    
    if not permission:
        return False
    
    if permission.permission_type == "write":
        return True
    if permission.permission_type == "read" and required_permission == "read":
        return True
    
    return False

