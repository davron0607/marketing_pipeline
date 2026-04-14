import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.routers.deps import get_current_active_user
from app.repositories.project_repository import ProjectRepository
from app.services.report_service import get_reports, download_report
from app.schemas.report import ReportResponse
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/project/{project_id}", response_model=list[ReportResponse])
async def list_reports(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_reports(db, project_id)


@router.get("/{report_id}/download")
async def download(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    return await download_report(db, report_id)


@router.post("/projects/{project_id}/generate-report")
async def trigger_report_generation(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    POST /projects/{project_id}/generate-report
    Enqueue PDF report generation for a project.
    Returns {job_run_id, status}.
    """
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info("generate-report request project_id=%s user_id=%s", project_id, current_user.id)

    # Create job_run
    result = await db.execute(
        text(
            "INSERT INTO job_runs (project_id, task_name, status, created_at) "
            "VALUES (:p, 'generate_pdf_report', 'pending', now()) RETURNING id"
        ),
        {"p": project_id},
    )
    job_run_id = result.fetchone()[0]
    await db.commit()

    # Dispatch Celery task
    from app.worker_client import dispatch_report_task
    celery_task_id = dispatch_report_task(job_run_id=job_run_id, project_id=project_id)

    await db.execute(
        text("UPDATE job_runs SET celery_task_id=:c WHERE id=:id"),
        {"c": celery_task_id, "id": job_run_id},
    )
    await db.commit()

    logger.info("Dispatched report task celery_id=%s job_run_id=%s", celery_task_id, job_run_id)
    return {"job_run_id": job_run_id, "status": "pending"}


@router.get("/projects/{project_id}/reports/latest")
async def get_latest_report(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    GET /projects/{project_id}/reports/latest
    Returns the latest generated_reports record with a pre-signed download URL.
    """
    proj_repo = ProjectRepository(db)
    project = await proj_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        text(
            "SELECT id, project_id, job_run_id, report_type, storage_key, bucket, "
            "file_size_bytes, status, error_msg, generated_at, created_at "
            "FROM generated_reports WHERE project_id=:p "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"p": project_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No report found for this project")

    (
        report_id, proj_id, job_run_id, report_type, storage_key, bucket,
        file_size, status, error_msg, generated_at, created_at,
    ) = row

    download_url = None
    if status == "completed" and storage_key and bucket:
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
            download_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": storage_key},
                ExpiresIn=3600,  # 1 hour
            )
        except Exception as e:
            logger.warning("Could not generate pre-signed URL: %s", e)

    return {
        "id": report_id,
        "project_id": proj_id,
        "job_run_id": job_run_id,
        "report_type": report_type,
        "storage_key": storage_key,
        "bucket": bucket,
        "file_size_bytes": file_size,
        "status": status,
        "error_msg": error_msg,
        "generated_at": generated_at.isoformat() if generated_at else None,
        "created_at": created_at.isoformat() if created_at else None,
        "download_url": download_url,
    }
