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


@router.delete("/projects/{project_id}/uploads/{upload_id}", status_code=204)
async def delete_uploaded_file(
    project_id: int,
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an uploaded file record and its object from MinIO."""
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    row = await db.execute(
        text("SELECT storage_key, bucket FROM uploaded_files WHERE id=:id AND project_id=:p"),
        {"id": upload_id, "p": project_id},
    )
    file_row = row.fetchone()
    if not file_row:
        raise HTTPException(status_code=404, detail="Upload not found")

    storage_key, bucket = file_row

    # Delete from MinIO (best-effort)
    try:
        from app.config import get_settings
        import boto3
        from botocore.config import Config
        settings = get_settings()
        s3 = boto3.client(
            "s3",
            endpoint_url=f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        s3.delete_object(Bucket=bucket or "raw-uploads", Key=storage_key)
        logger.info("Deleted MinIO object bucket=%s key=%s", bucket, storage_key)
    except Exception as e:
        logger.warning("Could not delete MinIO object: %s", e)

    # Cascade-delete DB records (survey_responses etc. have ON DELETE CASCADE)
    await db.execute(text("DELETE FROM uploaded_files WHERE id=:id"), {"id": upload_id})
    await db.commit()
    logger.info("Deleted uploaded_file id=%s project_id=%s", upload_id, project_id)


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
