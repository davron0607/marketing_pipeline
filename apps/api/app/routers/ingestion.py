import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
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
    """
    Accept a multipart file upload (.csv or .xlsx, max 100 MB),
    store it in MinIO, and enqueue processing.
    """
    logger.info(
        "Upload request project_id=%s user_id=%s filename=%s",
        project_id,
        current_user.id,
        file.filename,
    )

    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await handle_file_upload(db=db, project_id=project_id, file=file)
    logger.info(
        "Upload accepted project_id=%s upload_id=%s job_run_id=%s",
        project_id,
        result["upload_id"],
        result["job_run_id"],
    )
    return result
