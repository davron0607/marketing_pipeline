import io
import json
import logging
from datetime import datetime, timezone
import boto3
from botocore.config import Config
from app.celery_app import celery_app
from app.db import SessionLocal
from app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET, MINIO_SECURE

logger = logging.getLogger(__name__)


def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if MINIO_SECURE else ''}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _ensure_bucket(s3):
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=MINIO_BUCKET)


def generate_report(job_id: int, project_id: int):
    """Generate a simple JSON report and store in MinIO, then record in DB."""
    db = SessionLocal()
    try:
        from sqlalchemy import text

        # Fetch fraud summary
        result = db.execute(
            text("SELECT flag_type, COUNT(*) as cnt FROM fraud_results WHERE project_id=:p AND job_id=:j GROUP BY flag_type"),
            {"p": project_id, "j": job_id},
        )
        fraud_summary = {row[0]: row[1] for row in result}

        report_data = {
            "project_id": project_id,
            "job_id": job_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fraud_summary": fraud_summary,
        }

        # Upload report JSON to MinIO
        s3 = _get_s3()
        _ensure_bucket(s3)
        report_key = f"reports/{project_id}/{job_id}/report.json"
        s3.put_object(
            Bucket=MINIO_BUCKET,
            Key=report_key,
            Body=json.dumps(report_data, indent=2).encode(),
            ContentType="application/json",
        )

        # Record in reports table
        db.execute(
            text(
                "INSERT INTO reports (project_id, job_id, report_type, status, file_path) "
                "VALUES (:p, :j, 'fraud_summary', 'completed', :fp)"
            ),
            {"p": project_id, "j": job_id, "fp": report_key},
        )
        db.commit()
        logger.info(f"Report generated for job_id={job_id} at {report_key}")
    except Exception as e:
        logger.exception(f"Report generation failed: {e}")
    finally:
        db.close()


@celery_app.task(name="worker.tasks.report_tasks.generate_report_task", bind=True)
def generate_report_task(self, job_id: int, project_id: int):
    generate_report(job_id, project_id)
    return {"status": "completed", "job_id": job_id}
