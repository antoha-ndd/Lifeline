from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from auth import get_current_active_user

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.get("/", response_model=List[schemas.Organization])
def get_organizations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список всех организаций"""
    organizations = db.query(models.Organization).all()
    return organizations


@router.get("/{organization_id}", response_model=schemas.Organization)
def get_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить информацию об организации"""
    organization = db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.post("/", response_model=schemas.Organization)
def create_organization(
    organization: schemas.OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Создать новую организацию (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create organizations"
        )
    
    # Check if organization with same name exists
    db_org = db.query(models.Organization).filter(models.Organization.name == organization.name).first()
    if db_org:
        raise HTTPException(status_code=400, detail="Organization with this name already exists")
    
    db_organization = models.Organization(
        name=organization.name,
        description=organization.description
    )
    db.add(db_organization)
    db.commit()
    db.refresh(db_organization)
    return db_organization


@router.put("/{organization_id}", response_model=schemas.Organization)
def update_organization(
    organization_id: int,
    organization_update: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Обновить организацию (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update organizations"
        )
    
    db_organization = db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    if not db_organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Check name uniqueness if changing name
    if organization_update.name and organization_update.name != db_organization.name:
        existing_org = db.query(models.Organization).filter(models.Organization.name == organization_update.name).first()
        if existing_org:
            raise HTTPException(status_code=400, detail="Organization with this name already exists")
    
    if organization_update.name is not None:
        db_organization.name = organization_update.name
    if organization_update.description is not None:
        db_organization.description = organization_update.description
    
    db.commit()
    db.refresh(db_organization)
    return db_organization


@router.delete("/{organization_id}")
def delete_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Удалить организацию (только для администраторов)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete organizations"
        )
    
    db_organization = db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    if not db_organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    db.delete(db_organization)
    db.commit()
    return {"message": "Organization deleted successfully"}


@router.get("/{organization_id}/departments", response_model=List[schemas.Department])
def get_organization_departments(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Получить список подразделений организации"""
    organization = db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    departments = db.query(models.Department).filter(models.Department.organization_id == organization_id).all()
    return departments

