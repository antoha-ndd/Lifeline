from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime


# Organization schemas
class OrganizationBase(BaseModel):
    name: str
    description: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class Organization(OrganizationBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Department schemas
class DepartmentBase(BaseModel):
    name: str
    organization_id: int
    description: Optional[str] = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    organization_id: Optional[int] = None
    description: Optional[str] = None


class Department(DepartmentBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentWithOrganization(Department):
    organization: Organization


# Role schemas
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class Role(RoleBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# User schemas
class UserBase(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    telegram: Optional[str] = None
    telegram_notify_types: Optional[List[str]] = None
    phone: Optional[str] = None
    user_type: Optional[str] = "user"  # admin, developer, user
    organization_id: Optional[int] = None
    department_id: Optional[int] = None


class UserCreate(UserBase):
    password: str
    organization_id: Optional[int] = None
    department_id: Optional[int] = None
    role_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    telegram: Optional[str] = None
    telegram_notify_types: Optional[List[str]] = None
    phone: Optional[str] = None
    user_type: Optional[str] = None
    is_active: Optional[bool] = None
    is_blocked: Optional[bool] = None
    password: Optional[str] = None
    organization_id: Optional[int] = None
    department_id: Optional[int] = None
    role_ids: Optional[List[int]] = []
    theme: Optional[str] = None


class User(UserBase):
    id: int
    user_type: str
    is_active: bool
    is_admin: bool
    is_blocked: bool
    organization_id: Optional[int] = None
    department_id: Optional[int] = None
    theme: str = "dark"
    created_at: datetime
    roles: List[Role] = []
    
    class Config:
        from_attributes = True


class UserWithDetails(User):
    organization: Optional[Organization] = None
    department: Optional[Department] = None
    roles: List[Role] = []
    theme: str = "dark"


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Project schemas
class StageBase(BaseModel):
    name: str
    order: int
    color: Optional[str] = "#6366f1"
    is_initial: bool = False
    is_final: bool = False


class StageCreate(StageBase):
    pass


class StageUpdate(BaseModel):
    name: Optional[str] = None
    order: Optional[int] = None
    color: Optional[str] = None
    is_initial: Optional[bool] = None
    is_final: Optional[bool] = None


class StageOrder(BaseModel):
    id: int
    order: int


class Stage(StageBase):
    id: int
    project_id: int
    
    class Config:
        from_attributes = True


# Stage Transitions (маршрутизация)
class StageTransitionBase(BaseModel):
    from_stage_id: int
    to_stage_id: int
    name: Optional[str] = None


class StageTransitionCreate(StageTransitionBase):
    pass


class StageTransition(StageTransitionBase):
    id: int
    project_id: int
    
    class Config:
        from_attributes = True


class StageWithTransitions(Stage):
    allowed_transitions: List[int] = []  # IDs этапов, на которые можно перейти


# Field Groups (группы полей)
class FieldGroupBase(BaseModel):
    name: str
    order: int = 0
    is_collapsed: bool = False


class FieldGroupCreate(FieldGroupBase):
    pass


class FieldGroup(FieldGroupBase):
    id: int
    project_id: int
    
    class Config:
        from_attributes = True


class FieldDefinitionBase(BaseModel):
    name: str
    field_type: str
    options: Optional[Any] = None
    is_required: bool = False
    order: int = 0
    group_id: Optional[int] = None


class FieldDefinitionCreate(FieldDefinitionBase):
    pass


class FieldDefinition(FieldDefinitionBase):
    id: int
    project_id: int
    
    class Config:
        from_attributes = True


class FieldGroupWithFields(FieldGroup):
    fields: List[FieldDefinition] = []


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    stages: Optional[List[StageCreate]] = None
    field_definitions: Optional[List[FieldDefinitionCreate]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_archived: Optional[bool] = None


class Project(ProjectBase):
    id: int
    owner_id: Optional[int] = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    stages: List[Stage] = []
    field_definitions: List[FieldDefinition] = []
    field_groups: List[FieldGroup] = []
    
    class Config:
        from_attributes = True


class ProjectWithOwner(Project):
    owner: Optional[User] = None
    
    class Config:
        from_attributes = True


# Task schemas
class FieldValueBase(BaseModel):
    field_definition_id: int
    value: Any


class FieldValueCreate(FieldValueBase):
    pass


class FieldValue(FieldValueBase):
    id: int
    task_id: int
    
    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    priority: int = 0
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    project_id: int
    stage_id: int
    field_values: Optional[List[FieldValueCreate]] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    stage_id: Optional[int] = None
    assignee_id: Optional[int] = None
    priority: Optional[int] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    is_archived: Optional[bool] = None
    field_values: Optional[List[FieldValueCreate]] = None


class Task(TaskBase):
    id: int
    project_id: int
    stage_id: int
    author_id: Optional[int] = None
    is_archived: bool = False
    is_overdue: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    field_values: List[FieldValue] = []
    
    class Config:
        from_attributes = True


class TaskWithDetails(Task):
    stage: Stage
    author: Optional[User] = None
    assignee: Optional[User] = None


# Permission schemas
class PermissionBase(BaseModel):
    user_id: int
    permission_type: str


class ProjectPermissionCreate(PermissionBase):
    project_id: int


class TaskPermissionCreate(PermissionBase):
    task_id: int


class FieldPermissionCreate(PermissionBase):
    field_definition_id: int


class Permission(PermissionBase):
    id: int
    
    class Config:
        from_attributes = True


# Field Stage Role Permission schemas
class FieldStageRolePermissionBase(BaseModel):
    field_definition_id: int
    stage_id: Optional[int] = None
    role_id: Optional[int] = None


class FieldStageRolePermissionCreate(FieldStageRolePermissionBase):
    pass


class FieldStageRolePermissionUpdate(BaseModel):
    pass


class FieldStageRolePermission(FieldStageRolePermissionBase):
    id: int
    
    class Config:
        from_attributes = True


class FieldStageRolePermissionWithDetails(FieldStageRolePermission):
    field_definition: Optional[FieldDefinition] = None
    stage: Optional[Stage] = None
    role: Optional[Role] = None


# Attachments
class TaskAttachment(BaseModel):
    id: int
    task_id: int
    filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    uploaded_by: int
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


# Task History
class TaskHistoryBase(BaseModel):
    action: str
    description: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class TaskHistoryCreate(TaskHistoryBase):
    task_id: int
    user_id: int


class TaskHistory(TaskHistoryBase):
    id: int
    task_id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class TaskHistoryWithUser(TaskHistory):
    user_name: str
    user_full_name: Optional[str] = None


# Task Comments (Chat)
class TaskCommentBase(BaseModel):
    message: str
    reply_to_id: Optional[int] = None


class TaskCommentCreate(TaskCommentBase):
    pass


class TaskCommentUpdate(BaseModel):
    message: str


class TaskComment(TaskCommentBase):
    id: int
    task_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_edited: bool
    
    class Config:
        from_attributes = True


class TaskCommentWithUser(TaskComment):
    user_name: str
    user_full_name: Optional[str] = None
    reply_to_text: Optional[str] = None
    reply_to_author: Optional[str] = None


# Filter/Sort schemas
class TaskFilter(BaseModel):
    stage_ids: Optional[List[int]] = None
    assignee_ids: Optional[List[int]] = None
    priority_min: Optional[int] = None
    priority_max: Optional[int] = None
    search: Optional[str] = None
    field_filters: Optional[dict] = None


class TaskSort(BaseModel):
    field: str = "created_at"
    direction: str = "desc"


class TaskGroup(BaseModel):
    field: str


# Notifications
class NotificationBase(BaseModel):
    notification_type: str
    title: str
    message: Optional[str] = None


class NotificationCreate(NotificationBase):
    user_id: int
    task_id: Optional[int] = None


class Notification(NotificationBase):
    id: int
    user_id: int
    task_id: Optional[int] = None
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationWithTask(Notification):
    task_title: Optional[str] = None
    project_id: Optional[int] = None


# App Settings
class TelegramBotSettings(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_test_chat_id: Optional[str] = None
    telegram_default_project_id: Optional[int] = None
    telegram_default_stage_id: Optional[int] = None


# Task Links (связи между задачами)
class TaskLinkCreate(BaseModel):
    source_task_id: int
    target_task_id: int
    link_type: str = "relates"  # blocks, blocked_by, relates, duplicates, duplicated_by, parent, child


class TaskLinkBase(BaseModel):
    id: int
    source_task_id: int
    target_task_id: int
    link_type: str
    created_by: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class LinkedTaskInfo(BaseModel):
    """Краткая информация о связанной задаче"""
    id: int
    title: str
    project_id: int
    stage_id: int
    stage_name: Optional[str] = None
    stage_color: Optional[str] = None
    priority: int = 0
    is_archived: bool = False
    
    class Config:
        from_attributes = True


class TaskLinkWithDetails(TaskLinkBase):
    """Связь с полной информацией о связанной задаче"""
    linked_task: LinkedTaskInfo
    creator: Optional[User] = None


class TaskLinksResponse(BaseModel):
    """Ответ со всеми связями задачи"""
    outgoing: List[TaskLinkWithDetails] = []  # Исходящие связи (эта задача -> другие)
    incoming: List[TaskLinkWithDetails] = []  # Входящие связи (другие задачи -> эта)

