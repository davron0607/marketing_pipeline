import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.project_repository import ProjectRepository
from app.services.ingestion_service import handle_file_upload
from app.schemas.ingestion import UploadResponse
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/projects/{project_id}/uploads", response_model=UploadResponse)
async def upload_survey_file(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Accept a multipart file upload (.csv or .xlsx, max 100 MB)."""
    logger.info(
        "Upload request project_id=%s user_id=%s filename=%s",
        project_id, current_user.id, file.filename,
    )
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await handle_file_upload(db=db, project_id=project_id, file=file)
    return result


@router.get("/projects/{project_id}/uploads")
async def list_uploaded_files(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all uploaded files for a project."""
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        text(
            "SELECT id, original_filename, file_size_bytes, row_count, "
            "upload_status, created_at FROM uploaded_files "
            "WHERE project_id=:p ORDER BY created_at DESC"
        ),
        {"p": project_id},
    )
    rows = result.fetchall()
    return [
        {
            "id": r[0],
            "original_filename": r[1],
            "file_size_bytes": r[2],
            "row_count": r[3],
            "upload_status": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]
