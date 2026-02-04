from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from auth import get_current_active_user

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("/", response_model=List[schemas.Role])
def get_roles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список всех ролей (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view roles"
        )
    
    roles = db.query(models.Role).all()
    return roles


@router.get("/{role_id}", response_model=schemas.Role)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить информацию о роли (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view roles"
        )
    
    role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.post("/", response_model=schemas.Role)
def create_role(
    role: schemas.RoleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Создать новую роль (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create roles"
        )
    
    # Check if role with same name exists
    db_role = db.query(models.Role).filter(models.Role.name == role.name).first()
    if db_role:
        raise HTTPException(status_code=400, detail="Role with this name already exists")
    
    db_role = models.Role(
        name=role.name,
        description=role.description
    )
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role


@router.put("/{role_id}", response_model=schemas.Role)
def update_role(
    role_id: int,
    role_update: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить роль (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update roles"
        )
    
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check name uniqueness if changing name
    if role_update.name and role_update.name != db_role.name:
        existing_role = db.query(models.Role).filter(models.Role.name == role_update.name).first()
        if existing_role:
            raise HTTPException(status_code=400, detail="Role with this name already exists")
    
    if role_update.name is not None:
        db_role.name = role_update.name
    if role_update.description is not None:
        db_role.description = role_update.description
    
    db.commit()
    db.refresh(db_role)
    return db_role


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удалить роль (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete roles"
        )
    
    db_role = db.query(models.Role).filter(models.Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if any users have this role
    users_with_role = db.query(models.User).filter(models.User.role_id == role_id).count()
    if users_with_role > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role: {users_with_role} user(s) have this role"
        )
    
    db.delete(db_role)
    db.commit()
    return {"message": "Role deleted successfully"}

