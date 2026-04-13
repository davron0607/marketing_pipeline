import io
import uuid
import pandas as pd
import boto3
from botocore.config import Config
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.repositories.upload_repository import UploadRepository
from app.models.upload import Upload

settings = get_settings()


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}",
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=settings.MINIO_BUCKET)


async def upload_dataset(db: AsyncSession, project_id: int, file: UploadFile) -> Upload:
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")

    content = await file.read()
    file_size = len(content)

    # Parse to get row/column counts
    row_count = col_count = None
    try:
        buf = io.BytesIO(content)
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(buf)
        else:
            df = pd.read_excel(buf)
        row_count, col_count = df.shape
    except Exception:
        pass

    # Upload to MinIO
    storage_key = f"projects/{project_id}/{uuid.uuid4().hex}_{file.filename}"
    ensure_bucket()
    s3 = get_s3_client()
    s3.put_object(Bucket=settings.MINIO_BUCKET, Key=storage_key, Body=content)

    repo = UploadRepository(db)
    return await repo.create(
        project_id=project_id,
        filename=file.filename,
        storage_key=storage_key,
        file_size=file_size,
        row_count=row_count,
        column_count=col_count,
    )


def get_upload_bytes(storage_key: str) -> bytes:
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=settings.MINIO_BUCKET, Key=storage_key)
    return obj["Body"].read()
