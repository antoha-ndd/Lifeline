from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Enum as SQLEnum, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

# Notification types supported by the system
DEFAULT_TELEGRAM_NOTIFY_TYPES = [
    "task_assigned",
    "task_updated",
    "stage_changed",
    "comment_added",
    "attachment_added"
]


class PermissionType(enum.Enum):
    READ = "read"
    WRITE = "write"


class UserType(enum.Enum):
    """User type enum for validation (stored as string in DB)"""
    ADMIN = "admin"
    DEVELOPER = "developer"
    USER = "user"


class FieldType(enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    MULTISELECT = "multiselect"
    CHECKBOX = "checkbox"
    USER = "user"


class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    departments = relationship("Department", back_populates="organization", cascade="all, delete-orphan")
    users = relationship("User", back_populates="organization")


class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="departments")
    users = relationship("User", back_populates="department")


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)


class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(100))
    telegram = Column(String(100), nullable=True)
    telegram_notify_types = Column(JSON, nullable=True, default=lambda: DEFAULT_TELEGRAM_NOTIFY_TYPES.copy())
    phone = Column(String(20), nullable=True)
    user_type = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # Для обратной совместимости
    is_blocked = Column(Boolean, default=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    theme = Column(String(20), default="dark")  # dark, light
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship("Organization", back_populates="users")
    department = relationship("Department", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    owned_projects = relationship("Project", back_populates="owner")
    permissions = relationship("Permission", back_populates="user")
    assigned_tasks = relationship("Task", foreign_keys="Task.assignee_id", back_populates="assignee")


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="owned_projects")
    stages = relationship("Stage", back_populates="project", order_by="Stage.order")
    tasks = relationship("Task", back_populates="project")
    field_definitions = relationship("FieldDefinition", back_populates="project")
    field_groups = relationship("FieldGroup", back_populates="project", order_by="FieldGroup.order")
    permissions = relationship("Permission", back_populates="project")


class Stage(Base):
    __tablename__ = "stages"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String(50))
    order = Column(Integer)
    color = Column(String(7), default="#6366f1")
    is_initial = Column(Boolean, default=False)  # Начальный этап
    is_final = Column(Boolean, default=False)    # Конечный этап
    
    project = relationship("Project", back_populates="stages")
    tasks = relationship("Task", back_populates="stage")
    transitions_from = relationship("StageTransition", foreign_keys="StageTransition.from_stage_id", back_populates="from_stage")
    transitions_to = relationship("StageTransition", foreign_keys="StageTransition.to_stage_id", back_populates="to_stage")


class StageTransition(Base):
    """Переходы между этапами (маршрутизация workflow)"""
    __tablename__ = "stage_transitions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    from_stage_id = Column(Integer, ForeignKey("stages.id"))
    to_stage_id = Column(Integer, ForeignKey("stages.id"))
    name = Column(String(100), nullable=True)  # Название перехода (например, "Отправить на проверку")
    
    from_stage = relationship("Stage", foreign_keys=[from_stage_id], back_populates="transitions_from")
    to_stage = relationship("Stage", foreign_keys=[to_stage_id], back_populates="transitions_to")


class FieldGroup(Base):
    """Группы полей для организации на форме"""
    __tablename__ = "field_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    name = Column(String(100))
    order = Column(Integer, default=0)
    is_collapsed = Column(Boolean, default=False)  # Свёрнута по умолчанию
    
    project = relationship("Project", back_populates="field_groups")
    fields = relationship("FieldDefinition", back_populates="group")


class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    group_id = Column(Integer, ForeignKey("field_groups.id"), nullable=True)
    name = Column(String(50))
    field_type = Column(String(20))
    options = Column(JSON, nullable=True)  # Для select/multiselect
    is_required = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    
    project = relationship("Project", back_populates="field_definitions")
    group = relationship("FieldGroup", back_populates="fields")
    values = relationship("FieldValue", back_populates="field_definition", cascade="all, delete-orphan")
    permissions = relationship("FieldPermission", back_populates="field_definition", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    stage_id = Column(Integer, ForeignKey("stages.id"))
    title = Column(String(200))
    description = Column(Text, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    priority = Column(Integer, default=0)
    start_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project", back_populates="tasks")
    stage = relationship("Stage", back_populates="tasks")
    author = relationship("User", foreign_keys=[author_id], backref="created_tasks")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    field_values = relationship("FieldValue", back_populates="task", cascade="all, delete-orphan")
    permissions = relationship("TaskPermission", back_populates="task")
    attachments = relationship("TaskAttachment", back_populates="task", cascade="all, delete-orphan")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan", order_by="TaskHistory.created_at.desc()")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan", order_by="TaskComment.created_at.asc()")


class FieldValue(Base):
    __tablename__ = "field_values"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    field_definition_id = Column(Integer, ForeignKey("field_definitions.id"))
    value = Column(JSON)
    
    task = relationship("Task", back_populates="field_values")
    field_definition = relationship("FieldDefinition", back_populates="values")


class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    project_id = Column(Integer, ForeignKey("projects.id"))
    permission_type = Column(String(20))  # read, write
    
    user = relationship("User", back_populates="permissions")
    project = relationship("Project", back_populates="permissions")


class TaskPermission(Base):
    __tablename__ = "task_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    permission_type = Column(String(20))
    
    task = relationship("Task", back_populates="permissions")


class FieldPermission(Base):
    __tablename__ = "field_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    field_definition_id = Column(Integer, ForeignKey("field_definitions.id"))
    permission_type = Column(String(20))
    
    field_definition = relationship("FieldDefinition", back_populates="permissions")


class FieldStageRolePermission(Base):
    """Права доступа к полям в зависимости от этапа и роли.
    Если правило существует, значит пользователь с данной ролью может редактировать поле на данном этапе.
    Если stage_id = None, правило действует на все этапы.
    Если role_id = None, правило действует для всех ролей (отключает проверку ролей)."""
    __tablename__ = "field_stage_role_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    field_definition_id = Column(Integer, ForeignKey("field_definitions.id"), nullable=False)
    stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    
    field_definition = relationship("FieldDefinition")
    stage = relationship("Stage")
    role = relationship("Role")


class TaskAttachment(Base):
    """Прикреплённые файлы к задачам"""
    __tablename__ = "task_attachments"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    filename = Column(String(255))  # Оригинальное имя файла
    stored_filename = Column(String(255))  # Имя файла на диске
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    task = relationship("Task", back_populates="attachments")
    uploader = relationship("User")


class TaskHistory(Base):
    """История изменений задачи"""
    __tablename__ = "task_history"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(50))  # created, updated, stage_changed, field_changed, attachment_added, attachment_deleted
    description = Column(Text)  # Описание изменения
    old_value = Column(JSON, nullable=True)  # Старое значение (для отслеживания)
    new_value = Column(JSON, nullable=True)  # Новое значение
    created_at = Column(DateTime, default=datetime.utcnow)
    
    task = relationship("Task", back_populates="history")
    user = relationship("User")


class TaskComment(Base):
    """Комментарии к задаче (чат)"""
    __tablename__ = "task_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    reply_to_id = Column(Integer, ForeignKey("task_comments.id"), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_edited = Column(Boolean, default=False)
    
    task = relationship("Task", back_populates="comments")
    user = relationship("User")
    reply_to = relationship("TaskComment", remote_side=[id], backref="replies")


class Notification(Base):
    """Уведомления для пользователей"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    notification_type = Column(String(50), nullable=False)  # task_updated, attachment_added, comment_added
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User")
    task = relationship("Task")


class AppSetting(Base):
    """Глобальные настройки приложения"""
    __tablename__ = "app_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LinkType(enum.Enum):
    """Типы связей между задачами"""
    BLOCKS = "blocks"           # Блокирует
    BLOCKED_BY = "blocked_by"   # Заблокирована
    RELATES = "relates"         # Связана с
    DUPLICATES = "duplicates"   # Дублирует
    DUPLICATED_BY = "duplicated_by"  # Дублируется
    PARENT = "parent"           # Родительская
    CHILD = "child"             # Дочерняя


class TaskLink(Base):
    """Связи между задачами"""
    __tablename__ = "task_links"
    
    id = Column(Integer, primary_key=True, index=True)
    source_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    target_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    link_type = Column(String(50), default="relates")  # blocks, blocked_by, relates, duplicates, duplicated_by, parent, child
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    source_task = relationship("Task", foreign_keys=[source_task_id], backref="outgoing_links")
    target_task = relationship("Task", foreign_keys=[target_task_id], backref="incoming_links")
    creator = relationship("User")

