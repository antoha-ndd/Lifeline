from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from auth import get_current_active_user

router = APIRouter(prefix="/api/task-links", tags=["task-links"])


# Противоположные типы связей
REVERSE_LINK_TYPES = {
    "blocks": "blocked_by",
    "blocked_by": "blocks",
    "duplicates": "duplicated_by",
    "duplicated_by": "duplicates",
    "parent": "child",
    "child": "parent",
    "relates": "relates"
}

LINK_TYPE_NAMES = {
    "blocks": "Блокирует",
    "blocked_by": "Заблокирована",
    "relates": "Связана с",
    "duplicates": "Дублирует",
    "duplicated_by": "Дублируется",
    "parent": "Родительская для",
    "child": "Дочерняя от"
}


def get_linked_task_info(task: models.Task) -> schemas.LinkedTaskInfo:
    """Получить информацию о связанной задаче"""
    return schemas.LinkedTaskInfo(
        id=task.id,
        title=task.title,
        project_id=task.project_id,
        stage_id=task.stage_id,
        stage_name=task.stage.name if task.stage else None,
        stage_color=task.stage.color if task.stage else None,
        priority=task.priority,
        is_archived=task.is_archived
    )


@router.get("/{task_id}", response_model=schemas.TaskLinksResponse)
def get_task_links(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить все связи задачи"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Исходящие связи (эта задача -> другие)
    outgoing_links = db.query(models.TaskLink).filter(
        models.TaskLink.source_task_id == task_id
    ).all()
    
    # Входящие связи (другие задачи -> эта)
    incoming_links = db.query(models.TaskLink).filter(
        models.TaskLink.target_task_id == task_id
    ).all()
    
    outgoing_result = []
    for link in outgoing_links:
        target_task = db.query(models.Task).filter(models.Task.id == link.target_task_id).first()
        if target_task:
            creator = db.query(models.User).filter(models.User.id == link.created_by).first() if link.created_by else None
            outgoing_result.append(schemas.TaskLinkWithDetails(
                id=link.id,
                source_task_id=link.source_task_id,
                target_task_id=link.target_task_id,
                link_type=link.link_type,
                created_by=link.created_by,
                created_at=link.created_at,
                linked_task=get_linked_task_info(target_task),
                creator=schemas.User(
                    id=creator.id,
                    username=creator.username,
                    email=creator.email,
                    full_name=creator.full_name,
                    telegram=creator.telegram,
                    phone=creator.phone,
                    user_type=creator.user_type,
                    is_active=creator.is_active,
                    is_admin=creator.is_admin,
                    is_blocked=creator.is_blocked,
                    theme=creator.theme,
                    created_at=creator.created_at,
                    organization_id=creator.organization_id,
                    department_id=creator.department_id,
                    roles=[]
                ) if creator else None
            ))
    
    incoming_result = []
    for link in incoming_links:
        source_task = db.query(models.Task).filter(models.Task.id == link.source_task_id).first()
        if source_task:
            creator = db.query(models.User).filter(models.User.id == link.created_by).first() if link.created_by else None
            # Для входящих связей показываем инвертированный тип
            inverted_type = REVERSE_LINK_TYPES.get(link.link_type, link.link_type)
            incoming_result.append(schemas.TaskLinkWithDetails(
                id=link.id,
                source_task_id=link.source_task_id,
                target_task_id=link.target_task_id,
                link_type=inverted_type,
                created_by=link.created_by,
                created_at=link.created_at,
                linked_task=get_linked_task_info(source_task),
                creator=schemas.User(
                    id=creator.id,
                    username=creator.username,
                    email=creator.email,
                    full_name=creator.full_name,
                    telegram=creator.telegram,
                    phone=creator.phone,
                    user_type=creator.user_type,
                    is_active=creator.is_active,
                    is_admin=creator.is_admin,
                    is_blocked=creator.is_blocked,
                    theme=creator.theme,
                    created_at=creator.created_at,
                    organization_id=creator.organization_id,
                    department_id=creator.department_id,
                    roles=[]
                ) if creator else None
            ))
    
    return schemas.TaskLinksResponse(
        outgoing=outgoing_result,
        incoming=incoming_result
    )


@router.post("/", response_model=schemas.TaskLinkBase)
def create_task_link(
    link_data: schemas.TaskLinkCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Создать связь между задачами"""
    # Проверяем, что задачи существуют
    source_task = db.query(models.Task).filter(models.Task.id == link_data.source_task_id).first()
    target_task = db.query(models.Task).filter(models.Task.id == link_data.target_task_id).first()
    
    if not source_task:
        raise HTTPException(status_code=404, detail="Source task not found")
    if not target_task:
        raise HTTPException(status_code=404, detail="Target task not found")
    
    # Проверяем, что связь не на себя
    if link_data.source_task_id == link_data.target_task_id:
        raise HTTPException(status_code=400, detail="Cannot link task to itself")
    
    # Проверяем, что такая связь еще не существует
    existing_link = db.query(models.TaskLink).filter(
        models.TaskLink.source_task_id == link_data.source_task_id,
        models.TaskLink.target_task_id == link_data.target_task_id
    ).first()
    
    if existing_link:
        raise HTTPException(status_code=400, detail="Link already exists")
    
    # Также проверяем обратную связь для двусторонних типов
    reverse_link = db.query(models.TaskLink).filter(
        models.TaskLink.source_task_id == link_data.target_task_id,
        models.TaskLink.target_task_id == link_data.source_task_id
    ).first()
    
    if reverse_link:
        raise HTTPException(status_code=400, detail="Reverse link already exists")
    
    # Создаем связь
    link = models.TaskLink(
        source_task_id=link_data.source_task_id,
        target_task_id=link_data.target_task_id,
        link_type=link_data.link_type,
        created_by=current_user.id
    )
    
    db.add(link)
    
    # Добавляем в историю обеих задач
    link_type_name = LINK_TYPE_NAMES.get(link_data.link_type, link_data.link_type)
    reverse_type_name = LINK_TYPE_NAMES.get(REVERSE_LINK_TYPES.get(link_data.link_type, link_data.link_type), link_data.link_type)
    
    # История для исходной задачи
    source_history = models.TaskHistory(
        task_id=link_data.source_task_id,
        user_id=current_user.id,
        action="link_added",
        description=f"Добавлена связь: {link_type_name} #{target_task.id} «{target_task.title}»"
    )
    db.add(source_history)
    
    # История для целевой задачи
    target_history = models.TaskHistory(
        task_id=link_data.target_task_id,
        user_id=current_user.id,
        action="link_added",
        description=f"Добавлена связь: {reverse_type_name} #{source_task.id} «{source_task.title}»"
    )
    db.add(target_history)
    
    db.commit()
    db.refresh(link)
    
    return link


@router.delete("/{link_id}")
def delete_task_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удалить связь между задачами"""
    link = db.query(models.TaskLink).filter(models.TaskLink.id == link_id).first()
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    # Получаем информацию о задачах для истории
    source_task = db.query(models.Task).filter(models.Task.id == link.source_task_id).first()
    target_task = db.query(models.Task).filter(models.Task.id == link.target_task_id).first()
    
    link_type_name = LINK_TYPE_NAMES.get(link.link_type, link.link_type)
    reverse_type_name = LINK_TYPE_NAMES.get(REVERSE_LINK_TYPES.get(link.link_type, link.link_type), link.link_type)
    
    # Добавляем в историю обеих задач
    if source_task:
        source_history = models.TaskHistory(
            task_id=link.source_task_id,
            user_id=current_user.id,
            action="link_removed",
            description=f"Удалена связь: {link_type_name} #{target_task.id if target_task else 'N/A'} «{target_task.title if target_task else 'Удалённая задача'}»"
        )
        db.add(source_history)
    
    if target_task:
        target_history = models.TaskHistory(
            task_id=link.target_task_id,
            user_id=current_user.id,
            action="link_removed",
            description=f"Удалена связь: {reverse_type_name} #{source_task.id if source_task else 'N/A'} «{source_task.title if source_task else 'Удалённая задача'}»"
        )
        db.add(target_history)
    
    db.delete(link)
    db.commit()
    
    return {"status": "ok"}


@router.get("/task/{task_id}/chain")
def get_task_links_chain(
    task_id: int,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить цепочку связей задачи - все задачи, связанные напрямую или транзитивно"""
    # Проверяем существование задачи
    root_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not root_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Рекурсивно собираем все связанные задачи
    visited_ids = set()
    tasks_to_visit = [task_id]
    
    while tasks_to_visit:
        current_id = tasks_to_visit.pop()
        if current_id in visited_ids:
            continue
        visited_ids.add(current_id)
        
        # Находим все задачи, связанные с текущей
        outgoing_links = db.query(models.TaskLink).filter(
            models.TaskLink.source_task_id == current_id
        ).all()
        
        incoming_links = db.query(models.TaskLink).filter(
            models.TaskLink.target_task_id == current_id
        ).all()
        
        for link in outgoing_links:
            if link.target_task_id not in visited_ids:
                tasks_to_visit.append(link.target_task_id)
        
        for link in incoming_links:
            if link.source_task_id not in visited_ids:
                tasks_to_visit.append(link.source_task_id)
    
    # Получаем все найденные задачи
    tasks_query = db.query(models.Task).filter(models.Task.id.in_(visited_ids))
    if not include_archived:
        # Но всегда включаем корневую задачу, даже если она архивирована
        tasks_query = tasks_query.filter(
            (models.Task.is_archived == False) | (models.Task.id == task_id)
        )
    tasks = tasks_query.all()
    
    task_ids = [t.id for t in tasks]
    
    # Получаем все связи между найденными задачами
    links = db.query(models.TaskLink).filter(
        models.TaskLink.source_task_id.in_(task_ids),
        models.TaskLink.target_task_id.in_(task_ids)
    ).all()
    
    # Формируем данные для визуализации
    nodes = []
    for task in tasks:
        nodes.append({
            "id": task.id,
            "title": task.title,
            "project_id": task.project_id,
            "stage_id": task.stage_id,
            "stage_name": task.stage.name if task.stage else None,
            "stage_color": task.stage.color if task.stage else "#6366f1",
            "priority": task.priority,
            "is_archived": task.is_archived,
            "assignee_id": task.assignee_id,
            "assignee_name": task.assignee.full_name or task.assignee.username if task.assignee else None,
            "is_root": task.id == task_id
        })
    
    edges = []
    for link in links:
        edges.append({
            "id": link.id,
            "source": link.source_task_id,
            "target": link.target_task_id,
            "type": link.link_type,
            "type_name": LINK_TYPE_NAMES.get(link.link_type, link.link_type)
        })
    
    return {
        "root_task_id": task_id,
        "project_id": root_task.project_id,
        "nodes": nodes,
        "edges": edges,
        "link_types": LINK_TYPE_NAMES
    }


@router.get("/types")
def get_link_types():
    """Получить список доступных типов связей"""
    return {
        "types": [
            {"value": "relates", "label": "Связана с", "reverse": "relates"},
            {"value": "blocks", "label": "Блокирует", "reverse": "blocked_by"},
            {"value": "blocked_by", "label": "Заблокирована", "reverse": "blocks"},
            {"value": "duplicates", "label": "Дублирует", "reverse": "duplicated_by"},
            {"value": "duplicated_by", "label": "Дублируется", "reverse": "duplicates"},
            {"value": "parent", "label": "Родительская для", "reverse": "child"},
            {"value": "child", "label": "Дочерняя от", "reverse": "parent"}
        ]
    }

