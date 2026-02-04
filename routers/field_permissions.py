from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from auth import get_current_active_user
import models
import schemas

router = APIRouter(prefix="/api/field-permissions", tags=["field-permissions"])


@router.get("/project/{project_id}", response_model=List[schemas.FieldStageRolePermissionWithDetails])
def get_field_permissions(
    project_id: int,
    field_definition_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    role_id: Optional[int] = None,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Получить все правила доступа к полям для проекта"""
    # Проверка доступа к проекту
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Только администраторы могут просматривать правила доступа
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can view field permissions")
    
    query = db.query(models.FieldStageRolePermission).join(
        models.FieldDefinition
    ).filter(
        models.FieldDefinition.project_id == project_id
    )
    
    if field_definition_id:
        query = query.filter(models.FieldStageRolePermission.field_definition_id == field_definition_id)
    if stage_id:
        query = query.filter(models.FieldStageRolePermission.stage_id == stage_id)
    if role_id:
        query = query.filter(models.FieldStageRolePermission.role_id == role_id)
    
    permissions = query.all()
    
    # Загружаем связанные объекты
    result = []
    for perm in permissions:
        perm_dict = {
            "id": perm.id,
            "field_definition_id": perm.field_definition_id,
            "stage_id": perm.stage_id,
            "role_id": perm.role_id,
            "field_definition": db.query(models.FieldDefinition).filter(
                models.FieldDefinition.id == perm.field_definition_id
            ).first(),
            "stage": db.query(models.Stage).filter(
                models.Stage.id == perm.stage_id
            ).first() if perm.stage_id else None,
            "role": db.query(models.Role).filter(
                models.Role.id == perm.role_id
            ).first() if perm.role_id else None
        }
        result.append(schemas.FieldStageRolePermissionWithDetails(**perm_dict))
    
    return result


@router.get("/task/{task_id}/check", response_model=dict)
def check_field_permissions(
    task_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Проверить права доступа к полям для текущего пользователя в задаче"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Администраторы имеют доступ ко всем полям
    if current_user.is_admin:
        fields = db.query(models.FieldDefinition).filter(
            models.FieldDefinition.project_id == task.project_id
        ).all()
        return {field.id: True for field in fields}
    
    # Получаем роли пользователя напрямую из таблицы связей (избегаем lazy-load)
    user_roles = [
        r[0] for r in db.query(models.user_roles.c.role_id).filter(
            models.user_roles.c.user_id == current_user.id
        ).all()
    ]
    
    # Если роли не назначены, пробуем сопоставить роль по типу пользователя
    if not user_roles and current_user.user_type:
        role_name_candidates = []
        if current_user.user_type == "developer":
            role_name_candidates = ["исполнитель", "executor", "developer"]
        elif current_user.user_type == "user":
            role_name_candidates = ["пользователь", "user"]
        elif current_user.user_type == "admin":
            role_name_candidates = ["администратор", "admin"]
        
        if role_name_candidates:
            role = db.query(models.Role).filter(
                or_(*[models.Role.name.ilike(name) for name in role_name_candidates])
            ).first()
            if role:
                user_roles.append(role.id)
    
    # Получаем все правила доступа для полей проекта
    # Правило может быть для конкретного этапа или для всех этапов (stage_id = None)
    # Правило может быть для конкретной роли или для всех ролей (role_id = None)
    # Правила с role_id = None (все роли) работают даже для пользователей без ролей
    from sqlalchemy import or_
    
    # Строим условие для ролей
    role_condition = models.FieldStageRolePermission.role_id.is_(None)  # Всегда проверяем правила для всех ролей
    if user_roles:
        # Если у пользователя есть роли, также проверяем правила с конкретными ролями
        role_condition = or_(
            models.FieldStageRolePermission.role_id.in_(user_roles),
            models.FieldStageRolePermission.role_id.is_(None)
        )
    
    field_permissions = db.query(models.FieldStageRolePermission).join(
        models.FieldDefinition
    ).filter(
        models.FieldDefinition.project_id == task.project_id,
        or_(
            models.FieldStageRolePermission.stage_id == task.stage_id,
            models.FieldStageRolePermission.stage_id.is_(None)
        ),
        role_condition
    ).all()
    
    # Создаем словарь: field_id -> can_edit
    # Если правило существует, значит поле доступно для редактирования
    result = {}
    for perm in field_permissions:
        result[perm.field_definition_id] = True
    
    return result


@router.post("/", response_model=schemas.FieldStageRolePermission)
def create_field_permission(
    permission: schemas.FieldStageRolePermissionCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать правило доступа к полю"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create field permissions")
    
    # Проверяем существование полей, этапа и роли
    field = db.query(models.FieldDefinition).filter(
        models.FieldDefinition.id == permission.field_definition_id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field definition not found")
    
    # Если указан stage_id, проверяем его существование и принадлежность к проекту
    if permission.stage_id is not None:
        stage = db.query(models.Stage).filter(models.Stage.id == permission.stage_id).first()
        if not stage:
            raise HTTPException(status_code=404, detail="Stage not found")
        
        # Проверяем, что этап принадлежит тому же проекту, что и поле
        if stage.project_id != field.project_id:
            raise HTTPException(status_code=400, detail="Stage and field must belong to the same project")
    
    # Если указан role_id, проверяем его существование
    if permission.role_id is not None:
        role = db.query(models.Role).filter(models.Role.id == permission.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
    
    # Проверяем, нет ли уже такого правила
    from sqlalchemy import and_
    existing = db.query(models.FieldStageRolePermission).filter(
        and_(
            models.FieldStageRolePermission.field_definition_id == permission.field_definition_id,
            models.FieldStageRolePermission.stage_id == permission.stage_id,
            models.FieldStageRolePermission.role_id == permission.role_id
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    db_permission = models.FieldStageRolePermission(
        field_definition_id=permission.field_definition_id,
        stage_id=permission.stage_id,
        role_id=permission.role_id
    )
    db.add(db_permission)
    db.commit()
    db.refresh(db_permission)
    return db_permission


@router.put("/{permission_id}", response_model=schemas.FieldStageRolePermission)
def update_field_permission(
    permission_id: int,
    permission_update: schemas.FieldStageRolePermissionUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Обновить правило доступа к полю"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can update field permissions")
    
    db_permission = db.query(models.FieldStageRolePermission).filter(
        models.FieldStageRolePermission.id == permission_id
    ).first()
    
    if not db_permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # Обновление не требуется, так как наличие правила уже означает право на редактирование
    db.commit()
    db.refresh(db_permission)
    return db_permission


@router.delete("/{permission_id}")
def delete_field_permission(
    permission_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Удалить правило доступа к полю"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can delete field permissions")
    
    db_permission = db.query(models.FieldStageRolePermission).filter(
        models.FieldStageRolePermission.id == permission_id
    ).first()
    
    if not db_permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    db.delete(db_permission)
    db.commit()
    return {"message": "Permission deleted"}


@router.post("/bulk", response_model=List[schemas.FieldStageRolePermission])
def create_bulk_field_permissions(
    permissions: List[schemas.FieldStageRolePermissionCreate],
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Создать несколько правил доступа к полям"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create field permissions")
    
    result = []
    for permission in permissions:
        # Проверяем существование полей, этапа и роли
        field = db.query(models.FieldDefinition).filter(
            models.FieldDefinition.id == permission.field_definition_id
        ).first()
        if not field:
            continue
        
        stage = db.query(models.Stage).filter(models.Stage.id == permission.stage_id).first()
        if not stage:
            continue
        
        role = db.query(models.Role).filter(models.Role.id == permission.role_id).first()
        if not role:
            continue
        
        # Проверяем, что этап принадлежит тому же проекту, что и поле
        if stage.project_id != field.project_id:
            continue
        
        # Проверяем, нет ли уже такого правила
        existing = db.query(models.FieldStageRolePermission).filter(
            models.FieldStageRolePermission.field_definition_id == permission.field_definition_id,
            models.FieldStageRolePermission.stage_id == permission.stage_id,
            models.FieldStageRolePermission.role_id == permission.role_id
        ).first()
        
        if existing:
            continue
        
        db_permission = models.FieldStageRolePermission(
            field_definition_id=permission.field_definition_id,
            stage_id=permission.stage_id,
            role_id=permission.role_id,
        )
        db.add(db_permission)
        result.append(db_permission)
    
    db.commit()
    for perm in result:
        db.refresh(perm)
    
    return result

