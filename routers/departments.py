from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
import models
import schemas
from auth import get_current_active_user

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("/", response_model=List[schemas.DepartmentWithOrganization])
def get_departments(
    organization_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список всех подразделений (опционально фильтр по организации)"""
    query = db.query(models.Department)
    if organization_id:
        query = query.filter(models.Department.organization_id == organization_id)
    departments = query.all()
    return departments


@router.get("/{department_id}", response_model=schemas.DepartmentWithOrganization)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить информацию о подразделении"""
    department = db.query(models.Department).filter(models.Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


@router.post("/", response_model=schemas.Department)
def create_department(
    department: schemas.DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Создать новое подразделение (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create departments"
        )
    
    # Check if organization exists
    organization = db.query(models.Organization).filter(models.Organization.id == department.organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check if department with same name in organization exists
    db_dept = db.query(models.Department).filter(
        models.Department.name == department.name,
        models.Department.organization_id == department.organization_id
    ).first()
    if db_dept:
        raise HTTPException(status_code=400, detail="Department with this name already exists in this organization")
    
    db_department = models.Department(
        name=department.name,
        organization_id=department.organization_id,
        description=department.description
    )
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department


@router.put("/{department_id}", response_model=schemas.Department)
def update_department(
    department_id: int,
    department_update: schemas.DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить подразделение (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update departments"
        )
    
    db_department = db.query(models.Department).filter(models.Department.id == department_id).first()
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Check organization if changing
    if department_update.organization_id is not None:
        organization = db.query(models.Organization).filter(models.Organization.id == department_update.organization_id).first()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check name uniqueness if changing name or organization
    if department_update.name or department_update.organization_id:
        new_name = department_update.name or db_department.name
        new_org_id = department_update.organization_id or db_department.organization_id
        
        existing_dept = db.query(models.Department).filter(
            models.Department.name == new_name,
            models.Department.organization_id == new_org_id,
            models.Department.id != department_id
        ).first()
        if existing_dept:
            raise HTTPException(status_code=400, detail="Department with this name already exists in this organization")
    
    if department_update.name is not None:
        db_department.name = department_update.name
    if department_update.organization_id is not None:
        db_department.organization_id = department_update.organization_id
    if department_update.description is not None:
        db_department.description = department_update.description
    
    db.commit()
    db.refresh(db_department)
    return db_department


@router.delete("/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удалить подразделение (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete departments"
        )
    
    db_department = db.query(models.Department).filter(models.Department.id == department_id).first()
    if not db_department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    db.delete(db_department)
    db.commit()
    return {"message": "Department deleted successfully"}

