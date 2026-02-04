from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import shutil
from datetime import datetime
from jose import JWTError, jwt
from urllib.parse import quote

from database import get_db
import models
import schemas
from auth import get_current_active_user, check_task_permission, SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/api/attachments", tags=["attachments"])

# Directory for storing uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_user_from_token(token: str, db: Session) -> Optional[models.User]:
    """Get user from JWT token (for download links)"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(models.User).filter(models.User.username == username).first()
        return user
    except JWTError:
        return None

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.rtf', '.odt', '.ods', '.odp',
    # Archives
    '.zip', '.rar', '.7z', '.tar', '.gz',
    # Other
    '.csv', '.json', '.xml'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def is_image(mime_type: str) -> bool:
    return mime_type.startswith('image/')


@router.get("/task/{task_id}")
def get_task_attachments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Get all attachments for a task"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    attachments = db.query(models.TaskAttachment).filter(
        models.TaskAttachment.task_id == task_id
    ).order_by(models.TaskAttachment.uploaded_at.desc()).all()
    
    result = []
    for att in attachments:
        uploader = db.query(models.User).filter(models.User.id == att.uploaded_by).first()
        result.append({
            "id": att.id,
            "filename": att.filename,
            "file_size": att.file_size,
            "mime_type": att.mime_type,
            "is_image": is_image(att.mime_type),
            "uploaded_by": att.uploaded_by,
            "uploader_name": uploader.full_name or uploader.username if uploader else "Unknown",
            "uploaded_at": att.uploaded_at.isoformat()
        })
    
    return result


@router.post("/task/{task_id}")
async def upload_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Upload a file attachment to a task"""
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not check_task_permission(db, current_user, task_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Check file extension
    ext = get_file_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file and check size
    contents = await file.read()
    file_size = len(contents)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    
    # Generate unique filename
    unique_id = uuid.uuid4().hex
    stored_filename = f"{unique_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, stored_filename)
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(contents)
    
    # Get MIME type
    mime_type = file.content_type or "application/octet-stream"
    
    # Create database record
    attachment = models.TaskAttachment(
        task_id=task_id,
        filename=file.filename,
        stored_filename=stored_filename,
        file_size=file_size,
        mime_type=mime_type,
        uploaded_by=current_user.id
    )
    db.add(attachment)
    
    # Add history entry
    history = models.TaskHistory(
        task_id=task_id,
        user_id=current_user.id,
        action="attachment_added",
        description=f"Прикреплён файл: {file.filename}"
    )
    db.add(history)
    
    # Create notification for task author if file was uploaded by someone else
    if task.author_id and task.author_id != current_user.id:
        from routers.notifications import create_notification
        create_notification(
            db, task.author_id, task_id, "attachment_added",
            "Новый файл",
            f"В задачу '{task.title}' прикреплён файл: {file.filename}",
            actor_user_id=current_user.id
        )
    
    db.commit()
    db.refresh(attachment)
    
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "file_size": attachment.file_size,
        "mime_type": attachment.mime_type,
        "is_image": is_image(mime_type),
        "message": "File uploaded successfully"
    }


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Download an attachment. Accepts token via query parameter for direct links."""
    attachment = db.query(models.TaskAttachment).filter(
        models.TaskAttachment.id == attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Get user from token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = get_user_from_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if not check_task_permission(db, user, attachment.task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    file_path = os.path.join(UPLOAD_DIR, attachment.stored_filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    # Encode filename for Content-Disposition header (RFC 5987)
    encoded_filename = quote(attachment.filename)
    
    return FileResponse(
        path=file_path,
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.get("/{attachment_id}/view")
def view_attachment(
    attachment_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """View an attachment (for images - inline display). Accepts token via query parameter."""
    attachment = db.query(models.TaskAttachment).filter(
        models.TaskAttachment.id == attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    # Get user from token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = get_user_from_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if not check_task_permission(db, user, attachment.task_id, "read"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    file_path = os.path.join(UPLOAD_DIR, attachment.stored_filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    
    # For images, return inline; for others, force download
    # Encode filename for Content-Disposition header (RFC 5987)
    encoded_filename = quote(attachment.filename)
    
    if is_image(attachment.mime_type):
        return FileResponse(
            path=file_path,
            media_type=attachment.mime_type,
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"
            }
        )
    else:
        return FileResponse(
            path=file_path,
            media_type=attachment.mime_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )


@router.delete("/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user)
):
    """Delete an attachment"""
    attachment = db.query(models.TaskAttachment).filter(
        models.TaskAttachment.id == attachment_id
    ).first()
    
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    if not check_task_permission(db, current_user, attachment.task_id, "write"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Delete file from disk
    file_path = os.path.join(UPLOAD_DIR, attachment.stored_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Add history entry
    history = models.TaskHistory(
        task_id=attachment.task_id,
        user_id=current_user.id,
        action="attachment_deleted",
        description=f"Удалён файл: {attachment.filename}"
    )
    db.add(history)
    
    # Delete database record
    db.delete(attachment)
    db.commit()
    
    return {"message": "Attachment deleted successfully"}

