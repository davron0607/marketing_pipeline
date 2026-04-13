import io
import logging
from datetime import datetime, timezone
import pandas as pd
from app.celery_app import celery_app
from app.db import SessionLocal
from app.tasks.fraud_tasks import run_fraud_detection
from app.tasks.report_tasks import generate_report

logger = logging.getLogger(__name__)


def _get_dataframe(storage_key: str) -> pd.DataFrame:
    import boto3
    from botocore.config import Config
    from app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE

    s3 = boto3.client(
        "s3",
        endpoint_url=f"http{'s' if MINIO_SECURE else ''}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    obj = s3.get_object(Bucket=MINIO_BUCKET, Key=storage_key)
    content = obj["Body"].read()
    buf = io.BytesIO(content)

    if storage_key.lower().endswith(".csv"):
        return pd.read_csv(buf)
    else:
        return pd.read_excel(buf)


def _update_job_status(db, job_id: int, status: str, error: str | None = None):
    from sqlalchemy import text
    now = datetime.now(timezone.utc)
    if status == "running":
        db.execute(
            text("UPDATE jobs SET status=:s, started_at=:t WHERE id=:id"),
            {"s": status, "t": now, "id": job_id},
        )
    elif status in ("completed", "failed"):
        db.execute(
            text("UPDATE jobs SET status=:s, completed_at=:t, error_message=:e WHERE id=:id"),
            {"s": status, "t": now, "e": error, "id": job_id},
        )
    db.commit()


@celery_app.task(name="worker.tasks.analysis_tasks.run_full_analysis", bind=True)
def run_full_analysis(self, job_id: int, storage_key: str, project_id: int):
    db = SessionLocal()
    try:
        logger.info(f"Starting full analysis job_id={job_id}")
        _update_job_status(db, job_id, "running")

        df = _get_dataframe(storage_key)
        logger.info(f"Loaded dataframe shape={df.shape}")

        # Run fraud detection sub-task (synchronous call within worker)
        run_fraud_detection(job_id=job_id, project_id=project_id, df_json=df.to_json())

        # Generate report
        generate_report(job_id=job_id, project_id=project_id)

        _update_job_status(db, job_id, "completed")
        logger.info(f"Completed full analysis job_id={job_id}")
        return {"status": "completed", "job_id": job_id}

    except Exception as e:
        logger.exception(f"Full analysis failed job_id={job_id}: {e}")
        _update_job_status(db, job_id, "failed", error=str(e))
        raise
    finally:
        db.close()
