from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from auth import get_current_active_user, check_project_permission

router = APIRouter(prefix="/api/projects", tags=["projects"])


def check_settings_access(current_user: models.User):
    """Проверить, что пользователь имеет доступ к настройкам проекта (только администраторы)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can access project settings")


@router.get("/", response_model=List[schemas.ProjectWithOwner])
def get_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if current_user.is_admin:
        projects = db.query(models.Project).all()
    else:
        # Get projects where user has permission
        permitted_ids = db.query(models.Permission.project_id).filter(
            models.Permission.user_id == current_user.id
        ).all()
        permitted = db.query(models.Project).filter(
            models.Project.id.in_([p[0] for p in permitted_ids])
        ).all()
        projects = permitted
    return projects


@router.post("/", response_model=schemas.Project)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    # Only administrators can create projects
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create projects")
    
    db_project = models.Project(
        name=project.name,
        description=project.description
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    # Create default stages if provided
    if project.stages:
        for stage_data in project.stages:
            stage = models.Stage(
                project_id=db_project.id,
                name=stage_data.name,
                order=stage_data.order,
                color=stage_data.color
            )
            db.add(stage)
    else:
        # Create default stages
        default_stages = [
            ("Бэклог", 0, "#94a3b8"),
            ("В работе", 1, "#3b82f6"),
            ("На проверке", 2, "#f59e0b"),
            ("Готово", 3, "#22c55e")
        ]
        for name, order, color in default_stages:
            stage = models.Stage(
                project_id=db_project.id,
                name=name,
                order=order,
                color=color
            )
            db.add(stage)
    
    # Create field definitions if provided
    if project.field_definitions:
        for field_data in project.field_definitions:
            field = models.FieldDefinition(
                project_id=db_project.id,
                name=field_data.name,
                field_type=field_data.field_type,
                options=field_data.options,
                is_required=field_data.is_required,
                order=field_data.order
            )
            db.add(field)
    
    db.commit()
    db.refresh(db_project)
    return db_project


@router.get("/{project_id}", response_model=schemas.ProjectWithOwner)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Ensure stages are sorted by order
    project.stages = sorted(project.stages, key=lambda s: s.order)
    
    return project


@router.put("/{project_id}", response_model=schemas.Project)
def update_project(
    project_id: int,
    project_update: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    if project_update.name is not None:
        project.name = project_update.name
    if project_update.description is not None:
        project.description = project_update.description
    
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not current_user.is_admin and not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions to delete project")
    
    db.delete(project)
    db.commit()
    return {"message": "Project deleted"}


# Stages
@router.post("/{project_id}/stages", response_model=schemas.Stage)
def create_stage(
    project_id: int,
    stage: schemas.StageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_stage = models.Stage(
        project_id=project_id,
        name=stage.name,
        order=stage.order,
        color=stage.color,
        is_initial=stage.is_initial,
        is_final=stage.is_final
    )
    db.add(db_stage)
    db.commit()
    db.refresh(db_stage)
    return db_stage


@router.put("/{project_id}/stages/reorder")
def reorder_stages(
    project_id: int,
    stage_orders: List[schemas.StageOrder],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить порядок этапов"""
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    for stage_order in stage_orders:
        db.query(models.Stage).filter(
            models.Stage.id == stage_order.id,
            models.Stage.project_id == project_id
        ).update({"order": stage_order.order})
    
    db.commit()
    
    # Return updated stages
    stages = db.query(models.Stage).filter(
        models.Stage.project_id == project_id
    ).order_by(models.Stage.order).all()
    
    return [{"id": s.id, "name": s.name, "order": s.order, "color": s.color} for s in stages]


@router.put("/{project_id}/stages/{stage_id}", response_model=schemas.Stage)
def update_stage(
    project_id: int,
    stage_id: int,
    stage: schemas.StageUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_stage = db.query(models.Stage).filter(
        models.Stage.id == stage_id,
        models.Stage.project_id == project_id
    ).first()
    if not db_stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    if stage.name is not None:
        db_stage.name = stage.name
    if stage.order is not None:
        db_stage.order = stage.order
    if stage.color is not None:
        db_stage.color = stage.color
    if stage.is_initial is not None:
        db_stage.is_initial = stage.is_initial
    if stage.is_final is not None:
        db_stage.is_final = stage.is_final
    
    db.commit()
    db.refresh(db_stage)
    return db_stage


@router.delete("/{project_id}/stages/{stage_id}")
def delete_stage(
    project_id: int,
    stage_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_stage = db.query(models.Stage).filter(
        models.Stage.id == stage_id,
        models.Stage.project_id == project_id
    ).first()
    if not db_stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    # Check if there are tasks in this stage
    tasks_count = db.query(models.Task).filter(models.Task.stage_id == stage_id).count()
    if tasks_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete stage with tasks")
    
    # Delete related transitions
    db.query(models.StageTransition).filter(
        (models.StageTransition.from_stage_id == stage_id) | 
        (models.StageTransition.to_stage_id == stage_id)
    ).delete()
    
    db.delete(db_stage)
    db.commit()
    return {"message": "Stage deleted"}


# Stage Transitions (маршрутизация)
@router.get("/{project_id}/transitions")
def get_transitions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    # Чтение переходов доступно всем пользователям проекта (для канбана)
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    transitions = db.query(models.StageTransition).filter(
        models.StageTransition.project_id == project_id
    ).all()
    
    result = []
    for t in transitions:
        result.append({
            "id": t.id,
            "from_stage_id": t.from_stage_id,
            "to_stage_id": t.to_stage_id,
            "name": t.name,
            "from_stage_name": t.from_stage.name if t.from_stage else None,
            "to_stage_name": t.to_stage.name if t.to_stage else None
        })
    return result


@router.post("/{project_id}/transitions", response_model=schemas.StageTransition)
def create_transition(
    project_id: int,
    transition: schemas.StageTransitionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Verify both stages belong to this project
    from_stage = db.query(models.Stage).filter(
        models.Stage.id == transition.from_stage_id,
        models.Stage.project_id == project_id
    ).first()
    to_stage = db.query(models.Stage).filter(
        models.Stage.id == transition.to_stage_id,
        models.Stage.project_id == project_id
    ).first()
    
    if not from_stage or not to_stage:
        raise HTTPException(status_code=400, detail="Invalid stage IDs")
    
    # Check if transition already exists
    existing = db.query(models.StageTransition).filter(
        models.StageTransition.from_stage_id == transition.from_stage_id,
        models.StageTransition.to_stage_id == transition.to_stage_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Transition already exists")
    
    db_transition = models.StageTransition(
        project_id=project_id,
        from_stage_id=transition.from_stage_id,
        to_stage_id=transition.to_stage_id,
        name=transition.name
    )
    db.add(db_transition)
    db.commit()
    db.refresh(db_transition)
    return db_transition


@router.delete("/{project_id}/transitions/{transition_id}")
def delete_transition(
    project_id: int,
    transition_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db.query(models.StageTransition).filter(
        models.StageTransition.id == transition_id,
        models.StageTransition.project_id == project_id
    ).delete()
    db.commit()
    return {"message": "Transition deleted"}


@router.get("/{project_id}/stages/{stage_id}/allowed-transitions")
def get_allowed_transitions(
    project_id: int,
    stage_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список этапов, на которые можно перейти из текущего"""
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Администраторы могут перемещать задачи на любой этап
    if current_user.is_admin:
        stages = db.query(models.Stage).filter(
            models.Stage.project_id == project_id,
            models.Stage.id != stage_id
        ).all()
        return {
            "configured": False,  # Для админов переходы не ограничены
            "stages": [{"id": s.id, "name": s.name, "color": s.color} for s in stages]
        }
    
    transitions = db.query(models.StageTransition).filter(
        models.StageTransition.project_id == project_id,
        models.StageTransition.from_stage_id == stage_id
    ).all()
    
    # Проверяем, настроены ли переходы в проекте
    all_transitions = db.query(models.StageTransition).filter(
        models.StageTransition.project_id == project_id
    ).count()
    
    transitions_configured = all_transitions > 0
    
    if not transitions_configured:
        # Нет настроенных переходов - возвращаем все этапы
        stages = db.query(models.Stage).filter(
            models.Stage.project_id == project_id,
            models.Stage.id != stage_id
        ).all()
        return {
            "configured": False,
            "stages": [{"id": s.id, "name": s.name, "color": s.color} for s in stages]
        }
    
    result = []
    for t in transitions:
        if t.to_stage:
            result.append({
                "id": t.to_stage.id,
                "name": t.to_stage.name,
                "color": t.to_stage.color,
                "transition_name": t.name
            })
    return {
        "configured": True,
        "stages": result
    }


# Field Groups (группы полей)
@router.get("/{project_id}/field-groups")
def get_field_groups(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    groups = db.query(models.FieldGroup).filter(
        models.FieldGroup.project_id == project_id
    ).order_by(models.FieldGroup.order).all()
    
    result = []
    for g in groups:
        fields = db.query(models.FieldDefinition).filter(
            models.FieldDefinition.group_id == g.id
        ).order_by(models.FieldDefinition.order).all()
        result.append({
            "id": g.id,
            "name": g.name,
            "order": g.order,
            "is_collapsed": g.is_collapsed,
            "fields": [{
                "id": f.id,
                "name": f.name,
                "field_type": f.field_type,
                "options": f.options,
                "is_required": f.is_required,
                "order": f.order
            } for f in fields]
        })
    
    # Add ungrouped fields
    ungrouped = db.query(models.FieldDefinition).filter(
        models.FieldDefinition.project_id == project_id,
        models.FieldDefinition.group_id == None
    ).order_by(models.FieldDefinition.order).all()
    
    if ungrouped:
        result.insert(0, {
            "id": None,
            "name": "Основные поля",
            "order": -1,
            "is_collapsed": False,
            "fields": [{
                "id": f.id,
                "name": f.name,
                "field_type": f.field_type,
                "options": f.options,
                "is_required": f.is_required,
                "order": f.order
            } for f in ungrouped]
        })
    
    return result


@router.post("/{project_id}/field-groups", response_model=schemas.FieldGroup)
def create_field_group(
    project_id: int,
    group: schemas.FieldGroupCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_group = models.FieldGroup(
        project_id=project_id,
        name=group.name,
        order=group.order,
        is_collapsed=group.is_collapsed
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


@router.put("/{project_id}/field-groups/{group_id}", response_model=schemas.FieldGroup)
def update_field_group(
    project_id: int,
    group_id: int,
    group: schemas.FieldGroupCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_group = db.query(models.FieldGroup).filter(
        models.FieldGroup.id == group_id,
        models.FieldGroup.project_id == project_id
    ).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Field group not found")
    
    db_group.name = group.name
    db_group.order = group.order
    db_group.is_collapsed = group.is_collapsed
    db.commit()
    db.refresh(db_group)
    return db_group


@router.delete("/{project_id}/field-groups/{group_id}")
def delete_field_group(
    project_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Set fields in this group to ungrouped
    db.query(models.FieldDefinition).filter(
        models.FieldDefinition.group_id == group_id
    ).update({"group_id": None})
    
    db.query(models.FieldGroup).filter(
        models.FieldGroup.id == group_id,
        models.FieldGroup.project_id == project_id
    ).delete()
    db.commit()
    return {"message": "Field group deleted"}


# Field definitions
@router.post("/{project_id}/fields", response_model=schemas.FieldDefinition)
def create_field(
    project_id: int,
    field: schemas.FieldDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_field = models.FieldDefinition(
        project_id=project_id,
        group_id=field.group_id,
        name=field.name,
        field_type=field.field_type,
        options=field.options,
        is_required=field.is_required,
        order=field.order
    )
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    return db_field


@router.put("/{project_id}/fields/{field_id}", response_model=schemas.FieldDefinition)
def update_field(
    project_id: int,
    field_id: int,
    field: schemas.FieldDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_field = db.query(models.FieldDefinition).filter(
        models.FieldDefinition.id == field_id,
        models.FieldDefinition.project_id == project_id
    ).first()
    if not db_field:
        raise HTTPException(status_code=404, detail="Field not found")
    
    db_field.name = field.name
    db_field.field_type = field.field_type
    db_field.options = field.options
    db_field.is_required = field.is_required
    db_field.order = field.order
    db_field.group_id = field.group_id
    db.commit()
    db.refresh(db_field)
    return db_field


@router.delete("/{project_id}/fields/{field_id}")
def delete_field(
    project_id: int,
    field_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    if not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_field = db.query(models.FieldDefinition).filter(
        models.FieldDefinition.id == field_id,
        models.FieldDefinition.project_id == project_id
    ).first()
    if not db_field:
        raise HTTPException(status_code=404, detail="Field not found")
    
    # Delete all field values associated with this field definition
    db.query(models.FieldValue).filter(
        models.FieldValue.field_definition_id == field_id
    ).delete()
    
    db.delete(db_field)
    db.commit()
    return {"message": "Field deleted"}


# Permissions
@router.post("/{project_id}/permissions")
def add_project_permission(
    project_id: int,
    permission: schemas.PermissionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not current_user.is_admin and not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions to manage permissions")
    
    # Remove existing permission
    db.query(models.Permission).filter(
        models.Permission.user_id == permission.user_id,
        models.Permission.project_id == project_id
    ).delete()
    
    db_permission = models.Permission(
        user_id=permission.user_id,
        project_id=project_id,
        permission_type=permission.permission_type
    )
    db.add(db_permission)
    db.commit()
    return {"message": "Permission added"}


@router.get("/{project_id}/permissions")
def get_project_permissions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    # Чтение прав доступно всем пользователям проекта (нужно для определения своих прав)
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    permissions = db.query(models.Permission).filter(
        models.Permission.project_id == project_id
    ).all()
    
    result = []
    for p in permissions:
        user = db.query(models.User).filter(models.User.id == p.user_id).first()
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "username": user.username if user else None,
            "permission_type": p.permission_type
        })
    return result


@router.delete("/{project_id}/permissions/{permission_id}")
def delete_project_permission(
    project_id: int,
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    check_settings_access(current_user)
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not current_user.is_admin and not check_project_permission(db, current_user, project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions to manage permissions")
    
    db.query(models.Permission).filter(models.Permission.id == permission_id).delete()
    db.commit()
    return {"message": "Permission deleted"}

