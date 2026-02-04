from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from auth import get_current_active_user, get_password_hash

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=List[schemas.UserWithDetails])
def get_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список всех пользователей (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view users"
        )
    
    users = db.query(models.User).all()
    return users


@router.get("/{user_id}", response_model=schemas.User)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить информацию о пользователе"""
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=schemas.User)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Создать нового пользователя (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users"
        )
    
    # Check if username exists
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email exists
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate user_type
    user_type_str = user.user_type or "user"
    if user_type_str not in ["admin", "developer", "user"]:
        user_type_str = "user"
    
    # Validate organization and department if provided
    organization_id = None
    department_id = None
    
    if user.organization_id:
        org = db.query(models.Organization).filter(models.Organization.id == user.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        organization_id = user.organization_id
    
    if user.department_id:
        dept = db.query(models.Department).filter(models.Department.id == user.department_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        # Check that department belongs to organization if organization is set
        if organization_id and dept.organization_id != organization_id:
            raise HTTPException(status_code=400, detail="Department does not belong to the selected organization")
        department_id = user.department_id
    
    # Create user
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        telegram=user.telegram,
        telegram_notify_types=user.telegram_notify_types if user.telegram_notify_types is not None else models.DEFAULT_TELEGRAM_NOTIFY_TYPES.copy(),
        phone=user.phone,
        user_type=user_type_str,
        hashed_password=hashed_password,
        is_admin=(user_type_str == "admin"),  # Set is_admin based on user_type
        organization_id=organization_id,
        department_id=department_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Assign roles if provided
    if user.role_ids:
        roles = db.query(models.Role).filter(models.Role.id.in_(user.role_ids)).all()
        if len(roles) != len(user.role_ids):
            raise HTTPException(status_code=404, detail="One or more roles not found")
        db_user.roles = roles
        db.commit()
        db.refresh(db_user)
    
    return db_user


@router.put("/{user_id}", response_model=schemas.User)
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить информацию о пользователе"""
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only admins can change user_type, is_blocked
    if not current_user.is_admin:
        if user_update.user_type is not None or user_update.is_blocked is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can change user type or block status"
            )
    
    # Check email uniqueness if changing email
    if user_update.email and user_update.email != db_user.email:
        existing_user = db.query(models.User).filter(models.User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # Update fields
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
    
    # Update organization and department (only admins)
    if current_user.is_admin:
        if user_update.organization_id is not None:
            # Validate organization exists
            if user_update.organization_id:
                org = db.query(models.Organization).filter(models.Organization.id == user_update.organization_id).first()
                if not org:
                    raise HTTPException(status_code=404, detail="Organization not found")
            db_user.organization_id = user_update.organization_id if user_update.organization_id else None
        
        if user_update.department_id is not None:
            # Validate department exists and belongs to organization if organization is set
            if user_update.department_id:
                dept = db.query(models.Department).filter(models.Department.id == user_update.department_id).first()
                if not dept:
                    raise HTTPException(status_code=404, detail="Department not found")
                # If organization is set, check that department belongs to it
                if db_user.organization_id and dept.organization_id != db_user.organization_id:
                    raise HTTPException(status_code=400, detail="Department does not belong to the selected organization")
            db_user.department_id = user_update.department_id if user_update.department_id else None
        
        if user_update.role_ids is not None:
            # Validate all roles exist
            if user_update.role_ids:
                roles = db.query(models.Role).filter(models.Role.id.in_(user_update.role_ids)).all()
                if len(roles) != len(user_update.role_ids):
                    raise HTTPException(status_code=404, detail="One or more roles not found")
                db_user.roles = roles
            else:
                db_user.roles = []
    
    if user_update.is_blocked is not None:
        db_user.is_blocked = user_update.is_blocked
        # When blocking, also set is_active to False
        if user_update.is_blocked:
            db_user.is_active = False
        # When unblocking, set is_active to True
        else:
            db_user.is_active = True
    
    # Update user_type (only admins)
    if current_user.is_admin and user_update.user_type is not None:
        user_type_str = user_update.user_type
        if user_type_str not in ["admin", "developer", "user"]:
            user_type_str = "user"
        db_user.user_type = user_type_str
        db_user.is_admin = (user_type_str == "admin")  # Update is_admin
    
    db.commit()
    db.refresh(db_user)
    return db_user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удалить пользователя (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete users"
        )
    
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/block")
def block_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Заблокировать пользователя (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can block users"
        )
    
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot block your own account"
        )
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.is_blocked = True
    db_user.is_active = False  # Blocked users are automatically inactive
    db.commit()
    return {"message": "User blocked successfully"}


@router.post("/{user_id}/unblock")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Разблокировать пользователя (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can unblock users"
        )
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.is_blocked = False
    db_user.is_active = True  # Unblocked users are automatically active
    db.commit()
    return {"message": "User unblocked successfully"}


@router.get("/{user_id}/projects")
def get_user_projects(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список проектов с правами доступа пользователя (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view user projects"
        )
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all projects
    all_projects = db.query(models.Project).all()
    
    # Get user's permissions
    user_permissions = db.query(models.Permission).filter(
        models.Permission.user_id == user_id
    ).all()
    
    # Create a map of project_id -> permission_type
    permission_map = {p.project_id: p.permission_type for p in user_permissions}
    
    # Build result
    result = []
    for project in all_projects:
        permission_type = permission_map.get(project.id)
        
        result.append({
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "permission_type": permission_type  # None, "read", or "write"
        })
    
    return result


@router.put("/{user_id}/projects")
def update_user_projects(
    user_id: int,
    projects_data: List[dict] = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить права доступа пользователя на проекты (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update user projects"
        )
    
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Remove all existing permissions for this user
    db.query(models.Permission).filter(
        models.Permission.user_id == user_id
    ).delete()
    
    # Add new permissions
    for project_data in projects_data:
        project_id = project_data.get("project_id")
        permission_type = project_data.get("permission_type")
        
        if not project_id or not permission_type:
            continue
        
        # Validate permission type
        if permission_type not in ["read", "write"]:
            continue
        
        # Create permission
        db_permission = models.Permission(
            user_id=user_id,
            project_id=project_id,
            permission_type=permission_type
        )
        db.add(db_permission)
    
    db.commit()
    return {"message": "User projects updated successfully"}

