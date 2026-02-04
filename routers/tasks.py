from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from typing import List, Optional
from datetime import datetime, date

from database import get_db
import models
import schemas
from auth import get_current_active_user, check_project_permission, check_task_permission

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def add_task_history(
    db: Session,
    task_id: int,
    user_id: int,
    action: str,
    description: str,
    old_value: any = None,
    new_value: any = None
):
    """Добавить запись в историю задачи"""
    history = models.TaskHistory(
        task_id=task_id,
        user_id=user_id,
        action=action,
        description=description,
        old_value=old_value,
        new_value=new_value
    )
    db.add(history)


def get_user_display_name(db: Session, user_id: int) -> str:
    """Получить отображаемое имя пользователя"""
    if not user_id:
        return "Не назначен"
    user = db.query(models.User).filter(models.User.id == user_id).first()
    return user.full_name or user.username if user else f"Пользователь #{user_id}"


def get_stage_name(db: Session, stage_id: int) -> str:
    """Получить название этапа"""
    if not stage_id:
        return "Не указан"
    stage = db.query(models.Stage).filter(models.Stage.id == stage_id).first()
    return stage.name if stage else f"Этап #{stage_id}"


@router.get("/", response_model=List[schemas.TaskWithDetails])
def get_tasks(
    project_id: int,
    stage_id: Optional[int] = None,
    author_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    group_by: Optional[str] = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    query = db.query(models.Task).filter(models.Task.project_id == project_id)
    
    # Regular users (user_type == 'user') can only see tasks where they are the author
    if current_user.user_type == 'user' and not current_user.is_admin:
        query = query.filter(models.Task.author_id == current_user.id)
    
    # Filter archived tasks
    if not include_archived:
        query = query.filter(models.Task.is_archived == False)
    
    # Apply filters
    if stage_id is not None:
        query = query.filter(models.Task.stage_id == stage_id)
    if author_id is not None:
        query = query.filter(models.Task.author_id == author_id)
    if assignee_id is not None:
        query = query.filter(models.Task.assignee_id == assignee_id)
    if search:
        query = query.filter(
            or_(
                models.Task.title.ilike(f"%{search}%"),
                models.Task.description.ilike(f"%{search}%")
            )
        )
    
    # Apply sorting
    sort_column = getattr(models.Task, sort_by, models.Task.created_at)
    if sort_dir == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    
    tasks = query.all()
    today = date.today()
    for task in tasks:
        try:
            task.is_overdue = bool(task.due_date and task.due_date.date() < today)
        except Exception:
            task.is_overdue = False
    return tasks


@router.get("/kanban/{project_id}")
def get_kanban_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    stages = db.query(models.Stage).filter(
        models.Stage.project_id == project_id
    ).order_by(models.Stage.order).all()
    
    result = []
    for stage in stages:
        task_query = db.query(models.Task).filter(
            models.Task.stage_id == stage.id,
            models.Task.is_archived == False
        )
        
        # Regular users (user_type == 'user') can only see tasks where they are the author
        if current_user.user_type == 'user' and not current_user.is_admin:
            task_query = task_query.filter(models.Task.author_id == current_user.id)
        
        tasks = task_query.order_by(models.Task.priority.desc(), models.Task.created_at.desc()).all()
        
        task_list = []
        for task in tasks:
            assignee = None
            if task.assignee_id:
                user = db.query(models.User).filter(models.User.id == task.assignee_id).first()
                if user:
                    assignee = {"id": user.id, "username": user.username, "full_name": user.full_name}
            
            author = None
            if task.author_id:
                user = db.query(models.User).filter(models.User.id == task.author_id).first()
                if user:
                    author = {"id": user.id, "username": user.username, "full_name": user.full_name}
            
            # Get field values
            field_values = []
            for fv in task.field_values:
                field_def = db.query(models.FieldDefinition).filter(
                    models.FieldDefinition.id == fv.field_definition_id
                ).first()
                if field_def:
                    field_values.append({
                        "field_id": field_def.id,
                        "field_name": field_def.name,
                        "field_type": field_def.field_type,
                        "value": fv.value
                    })
            
            task_list.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "author_id": task.author_id,
                "author": author,
                "assignee_id": task.assignee_id,
                "assignee": assignee,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "is_overdue": bool(task.due_date and task.due_date.date() < date.today()),
                "created_at": task.created_at.isoformat(),
                "field_values": field_values
            })
        
        result.append({
            "id": stage.id,
            "name": stage.name,
            "order": stage.order,
            "color": stage.color,
            "tasks": task_list
        })
    
    return result


@router.post("/", response_model=schemas.Task)
def create_task(
    task: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    if not check_project_permission(db, current_user, task.project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    stage_id = task.stage_id
    # Users (user_type == 'user') can create tasks only in the initial stage
    if current_user.user_type == "user" and not current_user.is_admin:
        initial_stage = db.query(models.Stage).filter(
            models.Stage.project_id == task.project_id,
            models.Stage.is_initial == True
        ).order_by(models.Stage.order).first()
        if not initial_stage:
            initial_stage = db.query(models.Stage).filter(
                models.Stage.project_id == task.project_id
            ).order_by(models.Stage.order).first()
        if not initial_stage:
            raise HTTPException(status_code=400, detail="Initial stage not found for this project")
        stage_id = initial_stage.id
    else:
        # Verify stage belongs to project
        stage = db.query(models.Stage).filter(
            models.Stage.id == task.stage_id,
            models.Stage.project_id == task.project_id
        ).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Invalid stage for this project")
    
    db_task = models.Task(
        project_id=task.project_id,
        stage_id=stage_id,
        title=task.title,
        description=task.description,
        author_id=current_user.id,
        assignee_id=task.assignee_id,
        priority=task.priority,
        start_date=task.start_date,
        due_date=task.due_date
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    # Add field values
    if task.field_values:
        for fv in task.field_values:
            field_value = models.FieldValue(
                task_id=db_task.id,
                field_definition_id=fv.field_definition_id,
                value=fv.value
            )
            db.add(field_value)
        db.commit()
        db.refresh(db_task)
    
    # Add history entry for task creation
    add_task_history(
        db, db_task.id, current_user.id, 
        "created", 
        f"Задача создана"
    )
    db.commit()
    
    return db_task


@router.get("/{task_id}", response_model=schemas.TaskWithDetails)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return task


@router.get("/project/{project_id}/history")
def get_project_history(
    project_id: int,
    task_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить историю изменений всех задач проекта с фильтрами"""
    if not check_project_permission(db, current_user, project_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Get all tasks in the project
    tasks = db.query(models.Task).filter(models.Task.project_id == project_id).all()
    task_ids = [task.id for task in tasks]
    
    if not task_ids:
        return []
    
    # Build query with filters
    query = db.query(models.TaskHistory).filter(
        models.TaskHistory.task_id.in_(task_ids)
    )
    
    if task_id is not None:
        query = query.filter(models.TaskHistory.task_id == task_id)
    
    if user_id is not None:
        query = query.filter(models.TaskHistory.user_id == user_id)
    
    if action is not None:
        query = query.filter(models.TaskHistory.action == action)
    
    # Order and limit
    history = query.order_by(models.TaskHistory.created_at.desc()).limit(limit).all()
    
    result = []
    for h in history:
        user = db.query(models.User).filter(models.User.id == h.user_id).first()
        task = db.query(models.Task).filter(models.Task.id == h.task_id).first()
        result.append({
            "id": h.id,
            "task_id": h.task_id,
            "task_title": task.title if task else f"Задача #{h.task_id}",
            "action": h.action,
            "description": h.description,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "created_at": h.created_at.isoformat(),
            "user_id": h.user_id,
            "user_name": user.username if user else "Unknown",
            "user_full_name": user.full_name if user else None
        })
    
    return result


@router.get("/{task_id}/history")
def get_task_history(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить историю изменений задачи"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    history = db.query(models.TaskHistory).filter(
        models.TaskHistory.task_id == task_id
    ).order_by(models.TaskHistory.created_at.desc()).all()
    
    result = []
    for h in history:
        user = db.query(models.User).filter(models.User.id == h.user_id).first()
        result.append({
            "id": h.id,
            "action": h.action,
            "description": h.description,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "created_at": h.created_at.isoformat(),
            "user_id": h.user_id,
            "user_name": user.username if user else "Unknown",
            "user_full_name": user.full_name if user else None
        })
    
    return result


@router.put("/{task_id}", response_model=schemas.Task)
def update_task(
    task_id: int,
    task_update: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    changes = []
    
    if task_update.title is not None and task_update.title != task.title:
        old_title = task.title
        task.title = task_update.title
        changes.append(("title", f"Название изменено", old_title, task_update.title))
    
    if task_update.description is not None and task_update.description != task.description:
        task.description = task_update.description
        changes.append(("description", "Описание изменено", None, None))
    
    if task_update.stage_id is not None and task_update.stage_id != task.stage_id:
        if current_user.user_type == "user" and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Regular users cannot change task stage")
        # Verify stage belongs to same project
        stage = db.query(models.Stage).filter(
            models.Stage.id == task_update.stage_id,
            models.Stage.project_id == task.project_id
        ).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Invalid stage for this project")
        
        old_stage_name = get_stage_name(db, task.stage_id)
        new_stage_name = get_stage_name(db, task_update.stage_id)
        task.stage_id = task_update.stage_id
        changes.append(("stage", f"Этап изменён: {old_stage_name} → {new_stage_name}", old_stage_name, new_stage_name))
    
    if task_update.assignee_id is not None and task_update.assignee_id != task.assignee_id:
        old_assignee = get_user_display_name(db, task.assignee_id)
        new_assignee = get_user_display_name(db, task_update.assignee_id)
        new_assignee_id = task_update.assignee_id if task_update.assignee_id != 0 else None
        
        # Create notification for new assignee
        if new_assignee_id and new_assignee_id != current_user.id:
            from routers.notifications import create_notification
            create_notification(
                db, new_assignee_id, task_id, "task_assigned",
                "Вам назначена задача",
                f"Вам назначена задача: '{task.title}'",
                actor_user_id=current_user.id
            )
        
        task.assignee_id = new_assignee_id
        changes.append(("assignee", f"Исполнитель изменён: {old_assignee} → {new_assignee}", old_assignee, new_assignee))
    
    if task_update.priority is not None and task_update.priority != task.priority:
        old_priority = task.priority
        task.priority = task_update.priority
        changes.append(("priority", f"Приоритет изменён: {old_priority} → {task_update.priority}", old_priority, task_update.priority))
    
    if task_update.start_date is not None:
        old_date = task.start_date.isoformat() if task.start_date else None
        new_date = task_update.start_date.isoformat() if task_update.start_date else None
        if old_date != new_date:
            task.start_date = task_update.start_date
            changes.append(("start_date", f"Дата начала изменена", old_date, new_date))
    
    if task_update.due_date is not None:
        old_date = task.due_date.isoformat() if task.due_date else None
        new_date = task_update.due_date.isoformat() if task_update.due_date else None
        if old_date != new_date:
            task.due_date = task_update.due_date
            changes.append(("due_date", f"Срок выполнения изменён", old_date, new_date))
    
    if task_update.is_archived is not None and task_update.is_archived != task.is_archived:
        old_archived = task.is_archived
        task.is_archived = task_update.is_archived
        if task_update.is_archived:
            changes.append(("archived", "Задача перемещена в архив", False, True))
        else:
            changes.append(("archived", "Задача восстановлена из архива", True, False))
    
    # Update field values
    if task_update.field_values:
        # Get old field values for history
        old_values = {fv.field_definition_id: fv.value for fv in task.field_values}
        
        # Remove existing field values
        db.query(models.FieldValue).filter(models.FieldValue.task_id == task_id).delete()
        
        for fv in task_update.field_values:
            field_value = models.FieldValue(
                task_id=task_id,
                field_definition_id=fv.field_definition_id,
                value=fv.value
            )
            db.add(field_value)
            
            # Check if value changed
            old_val = old_values.get(fv.field_definition_id)
            if old_val != fv.value:
                field_def = db.query(models.FieldDefinition).filter(
                    models.FieldDefinition.id == fv.field_definition_id
                ).first()
                field_name = field_def.name if field_def else f"Поле #{fv.field_definition_id}"
                changes.append(("field", f"Поле '{field_name}' изменено", old_val, fv.value))
    
    # Record all changes to history
    for change_type, description, old_val, new_val in changes:
        add_task_history(db, task_id, current_user.id, "updated", description, old_val, new_val)
    
    # Create notification for task author if task was updated by someone else
    if task.author_id and task.author_id != current_user.id and changes:
        from routers.notifications import create_notification
        create_notification(
            db, task.author_id, task_id, "task_updated",
            "Задача изменена",
            f"Задача '{task.title}' была изменена",
            actor_user_id=current_user.id
        )
    
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}/stage/{stage_id}")
def move_task_to_stage(
    task_id: int,
    stage_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Verify stage belongs to same project
    stage = db.query(models.Stage).filter(
        models.Stage.id == stage_id,
        models.Stage.project_id == task.project_id
    ).first()
    if not stage:
        raise HTTPException(status_code=400, detail="Invalid stage for this project")
    
    # Check if transitions are configured (admins can bypass transition rules)
    if not current_user.is_admin:
        transitions_count = db.query(models.StageTransition).filter(
            models.StageTransition.project_id == task.project_id
        ).count()
        
        if transitions_count > 0 and not force:
            # Check if transition is allowed
            allowed = db.query(models.StageTransition).filter(
                models.StageTransition.from_stage_id == task.stage_id,
                models.StageTransition.to_stage_id == stage_id
            ).first()
            
            if not allowed:
                raise HTTPException(
                    status_code=400, 
                    detail="Transition not allowed. Configure workflow transitions or use force=true"
                )
    
    # Record stage change in history
    old_stage_name = get_stage_name(db, task.stage_id)
    new_stage_name = get_stage_name(db, stage_id)
    
    add_task_history(
        db, task_id, current_user.id,
        "stage_changed",
        f"Этап изменён: {old_stage_name} → {new_stage_name}",
        old_stage_name, new_stage_name
    )
    
    # Create notification for task author about stage change
    if task.author_id and task.author_id != current_user.id:
        from routers.notifications import create_notification
        create_notification(
            db, task.author_id, task_id, "stage_changed",
            "Этап задачи изменён",
            f"Задача '{task.title}' перемещена: {old_stage_name} → {new_stage_name}",
            actor_user_id=current_user.id
        )
    
    task.stage_id = stage_id
    db.commit()
    return {"message": "Task moved", "stage_id": stage_id}


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


# Task-level permissions
@router.post("/{task_id}/permissions")
def add_task_permission(
    task_id: int,
    permission: schemas.PermissionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if user has write permission on project
    if not check_project_permission(db, current_user, task.project_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Remove existing permission
    db.query(models.TaskPermission).filter(
        models.TaskPermission.user_id == permission.user_id,
        models.TaskPermission.task_id == task_id
    ).delete()
    
    db_permission = models.TaskPermission(
        user_id=permission.user_id,
        task_id=task_id,
        permission_type=permission.permission_type
    )
    db.add(db_permission)
    db.commit()
    return {"message": "Permission added"}


# Task Comments (Chat)
@router.get("/{task_id}/comments")
def get_task_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить все комментарии задачи"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    comments = db.query(models.TaskComment).filter(
        models.TaskComment.task_id == task_id
    ).order_by(models.TaskComment.created_at.asc()).all()
    
    result = []
    for c in comments:
        user = db.query(models.User).filter(models.User.id == c.user_id).first()
        
        # Get reply info if exists
        reply_to_text = None
        reply_to_author = None
        if c.reply_to_id:
            reply = db.query(models.TaskComment).filter(models.TaskComment.id == c.reply_to_id).first()
            if reply:
                reply_user = db.query(models.User).filter(models.User.id == reply.user_id).first()
                reply_to_text = reply.message[:100] + ('...' if len(reply.message) > 100 else '')
                reply_to_author = reply_user.full_name or reply_user.username if reply_user else "Unknown"
        
        result.append({
            "id": c.id,
            "task_id": c.task_id,
            "user_id": c.user_id,
            "message": c.message,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "is_edited": c.is_edited,
            "user_name": user.username if user else "Unknown",
            "user_full_name": user.full_name if user else None,
            "is_own": c.user_id == current_user.id,
            "reply_to_id": c.reply_to_id,
            "reply_to_text": reply_to_text,
            "reply_to_author": reply_to_author
        })
    
    return result


@router.post("/{task_id}/comments")
def create_comment(
    task_id: int,
    comment: schemas.TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Добавить комментарий к задаче"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Для комментирования достаточно права на просмотр задачи
    if not check_task_permission(db, current_user, task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Validate reply_to_id if provided
    if comment.reply_to_id:
        reply_to = db.query(models.TaskComment).filter(
            models.TaskComment.id == comment.reply_to_id,
            models.TaskComment.task_id == task_id
        ).first()
        if not reply_to:
            raise HTTPException(status_code=400, detail="Reply target not found")
    
    db_comment = models.TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        message=comment.message,
        reply_to_id=comment.reply_to_id
    )
    db.add(db_comment)
    
    # Add to history
    add_task_history(
        db, task_id, current_user.id,
        "comment_added",
        f"Добавлен комментарий"
    )
    
    # Create notification for task author if comment was added by someone else
    if task.author_id and task.author_id != current_user.id:
        from routers.notifications import create_notification
        create_notification(
            db, task.author_id, task_id, "comment_added",
            "Новое сообщение",
            f"В задачу '{task.title}' добавлен новый комментарий",
            actor_user_id=current_user.id
        )
    
    # Create notification for task assignee if comment was added by someone else
    if task.assignee_id and task.assignee_id != current_user.id and task.assignee_id != task.author_id:
        from routers.notifications import create_notification
        create_notification(
            db, task.assignee_id, task_id, "comment_added",
            "Новое сообщение",
            f"В задачу '{task.title}' добавлен новый комментарий",
            actor_user_id=current_user.id
        )
    
    db.commit()
    db.refresh(db_comment)
    
    return {
        "id": db_comment.id,
        "task_id": db_comment.task_id,
        "user_id": db_comment.user_id,
        "message": db_comment.message,
        "created_at": db_comment.created_at.isoformat(),
        "updated_at": db_comment.updated_at.isoformat(),
        "is_edited": db_comment.is_edited,
        "user_name": current_user.username,
        "user_full_name": current_user.full_name,
        "is_own": True
    }


@router.put("/{task_id}/comments/{comment_id}")
def update_comment(
    task_id: int,
    comment_id: int,
    comment_update: schemas.TaskCommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Редактировать свой комментарий"""
    comment = db.query(models.TaskComment).filter(
        models.TaskComment.id == comment_id,
        models.TaskComment.task_id == task_id
    ).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Только автор может редактировать комментарий
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Can only edit your own comments")
    
    comment.message = comment_update.message
    comment.is_edited = True
    db.commit()
    db.refresh(comment)
    
    return {
        "id": comment.id,
        "task_id": comment.task_id,
        "user_id": comment.user_id,
        "message": comment.message,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
        "is_edited": comment.is_edited,
        "user_name": current_user.username,
        "user_full_name": current_user.full_name,
        "is_own": True
    }


@router.delete("/{task_id}/comments/{comment_id}")
def delete_comment(
    task_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удалить комментарий"""
    comment = db.query(models.TaskComment).filter(
        models.TaskComment.id == comment_id,
        models.TaskComment.task_id == task_id
    ).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Только автор или админ может удалить комментарий
    if comment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Can only delete your own comments")
    
    db.delete(comment)
    db.commit()
    
    return {"message": "Comment deleted"}

