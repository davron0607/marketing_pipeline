import io
import uuid
import logging
import boto3
from botocore.config import Config
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.ingestion import UploadedFile, JobRun

logger = logging.getLogger(__name__)
settings = get_settings()

RAW_UPLOADS_BUCKET = "raw-uploads"
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _ensure_bucket(s3_client, bucket_name: str) -> None:
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        logger.debug("Bucket %s already exists", bucket_name)
    except Exception:
        logger.info("Creating bucket %s", bucket_name)
        s3_client.create_bucket(Bucket=bucket_name)


def _get_mime_type(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/octet-stream"


def _get_extension(filename: str) -> str:
    import os
    return os.path.splitext(filename.lower())[1]


async def handle_file_upload(
    db: AsyncSession,
    project_id: int,
    file: UploadFile,
) -> dict:
    """
    Validate, store, and enqueue a survey file upload.
    Returns dict with upload_id, job_run_id, filename, status.
    """
    logger.info(
        "handle_file_upload project_id=%s filename=%s",
        project_id,
        file.filename,
    )

    # --- Validation ---
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Only .csv and .xlsx are allowed.",
        )

    content = await file.read()
    file_size = len(content)
    logger.info("Read %d bytes for %s", file_size, file.filename)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File size {file_size} bytes exceeds maximum of {MAX_FILE_SIZE_BYTES} bytes (100 MB).",
        )

    # --- Upload to MinIO ---
    storage_key = f"projects/{project_id}/{uuid.uuid4().hex}_{file.filename}"
    mime_type = _get_mime_type(file.filename)

    s3 = _get_s3_client()
    _ensure_bucket(s3, RAW_UPLOADS_BUCKET)

    logger.info("Uploading to MinIO bucket=%s key=%s", RAW_UPLOADS_BUCKET, storage_key)
    s3.put_object(
        Bucket=RAW_UPLOADS_BUCKET,
        Key=storage_key,
        Body=content,
        ContentType=mime_type,
    )
    logger.info("Upload to MinIO complete key=%s", storage_key)

    # --- Create uploaded_files record ---
    uploaded_file = UploadedFile(
        project_id=project_id,
        original_filename=file.filename,
        storage_key=storage_key,
        bucket=RAW_UPLOADS_BUCKET,
        file_size_bytes=file_size,
        mime_type=mime_type,
        upload_status="pending",
    )
    db.add(uploaded_file)
    await db.flush()
    logger.info("Created uploaded_files id=%s", uploaded_file.id)

    # --- Create job_runs record ---
    job_run = JobRun(
        project_id=project_id,
        upload_file_id=uploaded_file.id,
        task_name="process_uploaded_survey_file",
        status="pending",
    )
    db.add(job_run)
    await db.flush()
    logger.info("Created job_runs id=%s", job_run.id)

    await db.commit()
    await db.refresh(uploaded_file)
    await db.refresh(job_run)

    # --- Dispatch Celery task ---
    from app.worker_client import dispatch_ingestion_task
    celery_task_id = dispatch_ingestion_task(
        job_run_id=job_run.id,
        upload_file_id=uploaded_file.id,
        storage_key=storage_key,
        project_id=project_id,
    )
    logger.info("Dispatched Celery task id=%s for job_run_id=%s", celery_task_id, job_run.id)

    # Update job_run with celery task id
    from sqlalchemy import update
    await db.execute(
        update(JobRun)
        .where(JobRun.id == job_run.id)
        .values(celery_task_id=celery_task_id)
    )
    await db.commit()

    return {
        "upload_id": uploaded_file.id,
        "job_run_id": job_run.id,
        "filename": file.filename,
        "status": "pending",
    }
