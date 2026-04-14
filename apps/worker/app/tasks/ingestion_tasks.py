import io
import logging
from datetime import datetime, timezone

import pandas as pd
import boto3
from botocore.config import Config

from app.celery_app import celery_app
from app.db import SessionLocal
from app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE

logger = logging.getLogger(__name__)

RAW_UPLOADS_BUCKET = "raw-uploads"


def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=f"http{'s' if MINIO_SECURE else ''}://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _ensure_bucket(s3, bucket_name: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket_name)
    except Exception:
        s3.create_bucket(Bucket=bucket_name)


def _normalize_column_name(col: str) -> str:
    """Strip whitespace, lowercase, replace spaces/special chars with underscores."""
    col = str(col).strip().lower()
    import re
    col = re.sub(r"[\s\-\.]+", "_", col)
    col = re.sub(r"[^\w]", "", col)
    col = re.sub(r"_+", "_", col)
    return col.strip("_")


def _update_job_run(db, job_run_id: int, status: str, error_msg: str | None = None) -> None:
    from sqlalchemy import text
    now = datetime.now(timezone.utc)
    if status == "running":
        db.execute(
            text(
                "UPDATE job_runs SET status=:s, started_at=:t WHERE id=:id"
            ),
            {"s": status, "t": now, "id": job_run_id},
        )
    elif status in ("completed", "failed"):
        db.execute(
            text(
                "UPDATE job_runs SET status=:s, completed_at=:t, error_msg=:e WHERE id=:id"
            ),
            {"s": status, "t": now, "e": error_msg, "id": job_run_id},
        )
    db.commit()


def _update_uploaded_file(db, upload_file_id: int, status: str, row_count: int | None = None, error_msg: str | None = None) -> None:
    from sqlalchemy import text
    params = {"s": status, "e": error_msg, "id": upload_file_id}
    if row_count is not None:
        db.execute(
            text("UPDATE uploaded_files SET upload_status=:s, row_count=:r, error_msg=:e WHERE id=:id"),
            {**params, "r": row_count},
        )
    else:
        db.execute(
            text("UPDATE uploaded_files SET upload_status=:s, error_msg=:e WHERE id=:id"),
            params,
        )
    db.commit()


@celery_app.task(name="app.tasks.ingestion_tasks.process_uploaded_survey_file", bind=True)
def process_uploaded_survey_file(
    self,
    job_run_id: int,
    upload_file_id: int,
    storage_key: str,
    project_id: int,
):
    """
    Download file from MinIO, parse CSV/XLSX, normalize columns,
    insert survey_responses rows, then chain to feature computation.
    """
    logger.info(
        "process_uploaded_survey_file start job_run_id=%s upload_file_id=%s storage_key=%s project_id=%s",
        job_run_id,
        upload_file_id,
        storage_key,
        project_id,
    )
    db = SessionLocal()
    try:
        _update_job_run(db, job_run_id, "running")
        _update_uploaded_file(db, upload_file_id, "processing")

        # Download file from MinIO
        s3 = _get_s3()
        _ensure_bucket(s3, RAW_UPLOADS_BUCKET)
        logger.info("Downloading storage_key=%s from bucket=%s", storage_key, RAW_UPLOADS_BUCKET)
        obj = s3.get_object(Bucket=RAW_UPLOADS_BUCKET, Key=storage_key)
        content = obj["Body"].read()
        logger.info("Downloaded %d bytes", len(content))

        # Detect and parse
        buf = io.BytesIO(content)
        lower_key = storage_key.lower()
        if lower_key.endswith(".xlsx"):
            df = pd.read_excel(buf, dtype=str)
            logger.info("Parsed XLSX shape=%s", df.shape)
        else:
            # Default to CSV
            buf.seek(0)
            df = pd.read_csv(buf, dtype=str)
            logger.info("Parsed CSV shape=%s", df.shape)

        # Normalize column names
        orig_cols = list(df.columns)
        new_cols = [_normalize_column_name(c) for c in orig_cols]
        # Handle duplicates by appending index
        seen: dict[str, int] = {}
        final_cols = []
        for c in new_cols:
            if c in seen:
                seen[c] += 1
                final_cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                final_cols.append(c)
        df.columns = final_cols
        logger.info("Normalized columns: %s -> %s", orig_cols[:5], final_cols[:5])

        # Build mapping of original->normalized col names
        col_mapping = dict(zip(orig_cols, final_cols))

        row_count = len(df)
        logger.info("Inserting %d survey_responses", row_count)

        from sqlalchemy import text
        # Determine respondent_id column (first column)
        first_col = final_cols[0] if final_cols else None

        rows_to_insert = []
        for idx, row in df.iterrows():
            raw_data = {}
            # Use original column names for raw_data
            for orig_c, norm_c in col_mapping.items():
                val = row.get(norm_c)
                raw_data[orig_c] = None if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val)

            normalized_data = {}
            for norm_c in final_cols:
                val = row.get(norm_c)
                normalized_data[norm_c] = None if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val)

            respondent_id = str(row[first_col]) if first_col and row.get(first_col) is not None else str(idx)

            rows_to_insert.append({
                "project_id": project_id,
                "upload_file_id": upload_file_id,
                "job_run_id": job_run_id,
                "respondent_id": respondent_id,
                "raw_data": raw_data,
                "normalized_data": normalized_data,
                "row_index": int(idx),
            })

        import json
        # Insert rows one at a time — executemany conflicts with cast(:x as jsonb) syntax
        SQL = text(
            "INSERT INTO survey_responses "
            "(project_id, upload_file_id, job_run_id, respondent_id, raw_data, normalized_data, row_index) "
            "VALUES (:project_id, :upload_file_id, :job_run_id, :respondent_id, "
            "cast(:raw_data as jsonb), cast(:normalized_data as jsonb), :row_index)"
        )
        CHUNK = 500
        for i in range(0, len(rows_to_insert), CHUNK):
            chunk = rows_to_insert[i:i + CHUNK]
            for r in chunk:
                db.execute(SQL, {
                    **r,
                    "raw_data": json.dumps(r["raw_data"]),
                    "normalized_data": json.dumps(r["normalized_data"]),
                })
            db.commit()
            logger.info("Inserted chunk %d-%d", i, i + len(chunk))

        _update_uploaded_file(db, upload_file_id, "done", row_count=row_count)
        _update_job_run(db, job_run_id, "completed")

        logger.info(
            "process_uploaded_survey_file completed job_run_id=%s rows=%d",
            job_run_id,
            row_count,
        )

        # Chain to feature computation
        from app.tasks.feature_tasks import compute_response_features
        compute_response_features.delay(job_run_id, project_id)
        logger.info("Chained compute_response_features for job_run_id=%s", job_run_id)

        return {"status": "completed", "job_run_id": job_run_id, "row_count": row_count}

    except Exception as exc:
        logger.exception("process_uploaded_survey_file failed job_run_id=%s: %s", job_run_id, exc)
        try:
            _update_job_run(db, job_run_id, "failed", error_msg=str(exc))
            _update_uploaded_file(db, upload_file_id, "failed", error_msg=str(exc))
        except Exception:
            pass
        raise
    finally:
        db.close()
