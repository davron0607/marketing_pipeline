import json
import logging
from datetime import datetime, timezone

import boto3
from botocore.config import Config

from app.celery_app import celery_app
from app.db import SessionLocal
from app.config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE

logger = logging.getLogger(__name__)

REPORTS_BUCKET = "reports"


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


def _update_job_run(db, job_run_id: int, status: str, error_msg: str | None = None) -> None:
    from sqlalchemy import text
    now = datetime.now(timezone.utc)
    if status == "running":
        db.execute(
            text("UPDATE job_runs SET status=:s, started_at=:t WHERE id=:id"),
            {"s": status, "t": now, "id": job_run_id},
        )
    elif status in ("completed", "failed"):
        db.execute(
            text("UPDATE job_runs SET status=:s, completed_at=:t, error_msg=:e WHERE id=:id"),
            {"s": status, "t": now, "e": error_msg, "id": job_run_id},
        )
    db.commit()


def _load_project_name(db, project_id: int) -> str:
    from sqlalchemy import text
    row = db.execute(
        text("SELECT name FROM projects WHERE id=:p"), {"p": project_id}
    ).fetchone()
    return row[0] if row else f"Project {project_id}"


def _load_analytics(db, project_id: int) -> dict:
    """Load analytics_results and build summary dict."""
    from sqlalchemy import text

    rows = db.execute(
        text(
            "SELECT analysis_type, question_key, result_data, insight_text "
            "FROM analytics_results WHERE project_id=:p ORDER BY id"
        ),
        {"p": project_id},
    ).fetchall()

    sample_quality = {}
    insight_texts = []
    distributions = {}
    crosstabs = []
    top_drivers = []

    for analysis_type, question_key, result_data_raw, insight_text in rows:
        if isinstance(result_data_raw, str):
            try:
                rd = json.loads(result_data_raw)
            except Exception:
                rd = {}
        elif result_data_raw is None:
            rd = {}
        else:
            rd = dict(result_data_raw)

        if analysis_type == "sample_quality":
            sample_quality = rd
        elif analysis_type in ("distribution_numeric", "distribution_single_choice", "distribution_text"):
            dist_type_map = {
                "distribution_numeric": "numeric",
                "distribution_single_choice": "single_choice",
                "distribution_text": "text",
            }
            if question_key:
                distributions[question_key] = {
                    "type": dist_type_map.get(analysis_type, "single_choice"),
                    "data": rd,
                }
        elif analysis_type == "crosstab":
            crosstabs.append(rd)
        elif analysis_type == "top_driver":
            top_drivers.append(rd)

        if insight_text:
            insight_texts.append(insight_text)

    return {
        "sample_quality": sample_quality,
        "insight_texts": insight_texts,
        "distributions": distributions,
        "crosstabs": crosstabs,
        "top_drivers": top_drivers,
    }


def _load_fraud_summary(db, project_id: int) -> dict:
    """Load fraud summary from fraud_scores table."""
    from sqlalchemy import text

    # Label counts
    count_rows = db.execute(
        text("SELECT fraud_label, COUNT(*) FROM fraud_scores WHERE project_id=:p GROUP BY fraud_label"),
        {"p": project_id},
    ).fetchall()
    label_counts = {row[0]: int(row[1]) for row in count_rows}
    total_scored = sum(label_counts.values())

    label_pcts = {
        lbl: round(cnt / total_scored * 100, 2) if total_scored else 0.0
        for lbl, cnt in label_counts.items()
    }

    # Top reasons
    reason_rows = db.execute(
        text(
            "SELECT reason, COUNT(*) as cnt FROM ("
            "  SELECT jsonb_array_elements_text(fraud_reasons) as reason "
            "  FROM fraud_scores WHERE project_id=:p AND fraud_label='reject'"
            ") sub GROUP BY reason ORDER BY cnt DESC LIMIT 10"
        ),
        {"p": project_id},
    ).fetchall()
    top_reasons = [{"reason": row[0], "count": int(row[1])} for row in reason_rows]

    # Top suspicious
    suspicious_rows = db.execute(
        text(
            "SELECT sr.respondent_id, fs.fraud_score, fs.fraud_label, fs.fraud_reasons "
            "FROM fraud_scores fs "
            "JOIN survey_responses sr ON sr.id = fs.survey_response_id "
            "WHERE fs.project_id=:p AND fs.fraud_label='reject' "
            "ORDER BY fs.fraud_score DESC LIMIT 20"
        ),
        {"p": project_id},
    ).fetchall()
    top_suspicious = []
    for row in suspicious_rows:
        reasons_raw = row[3]
        if isinstance(reasons_raw, str):
            try:
                reasons = json.loads(reasons_raw)
            except Exception:
                reasons = []
        elif reasons_raw is None:
            reasons = []
        else:
            reasons = list(reasons_raw)
        top_suspicious.append({
            "respondent_id": row[0],
            "fraud_score": round(float(row[1]), 2),
            "label": row[2],
            "reasons": reasons,
        })

    return {
        "total_scored": total_scored,
        "label_counts": label_counts,
        "label_percentages": label_pcts,
        "top_reasons": top_reasons,
        "top_suspicious": top_suspicious,
    }


@celery_app.task(name="app.tasks.report_tasks.generate_pdf_report", bind=True)
def generate_pdf_report(self, job_run_id: int, project_id: int):
    """
    Generate a full PDF report, upload to MinIO, and record in generated_reports.
    """
    logger.info(
        "generate_pdf_report start job_run_id=%s project_id=%s",
        job_run_id,
        project_id,
    )
    db = SessionLocal()
    try:
        from sqlalchemy import text

        # Create job_run for report generation
        res = db.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, created_at) "
                "VALUES (:p, 'generate_pdf_report', 'running', :t) RETURNING id"
            ),
            {"p": project_id, "t": datetime.now(timezone.utc)},
        )
        report_job_run_id = res.fetchone()[0]
        db.commit()

        # Create pending generated_reports record
        res2 = db.execute(
            text(
                "INSERT INTO generated_reports (project_id, job_run_id, report_type, status, created_at) "
                "VALUES (:p, :j, 'pdf', 'pending', :t) RETURNING id"
            ),
            {"p": project_id, "j": report_job_run_id, "t": datetime.now(timezone.utc)},
        )
        report_id = res2.fetchone()[0]
        db.commit()
        logger.info("Created generated_reports id=%s", report_id)

        project_name = _load_project_name(db, project_id)
        analytics = _load_analytics(db, project_id)
        fraud_summary = _load_fraud_summary(db, project_id)
        suspicious = fraud_summary.get("top_suspicious", [])

        # Build PDF
        logger.info("Building PDF for project_id=%s", project_id)
        from app.reports.pdf_builder import build_report
        pdf_bytes = build_report(
            project_name=project_name,
            analytics=analytics,
            fraud_summary=fraud_summary,
            suspicious=suspicious,
        )
        logger.info("PDF built: %d bytes", len(pdf_bytes))

        # Upload to MinIO
        storage_key = f"reports/{project_id}/{report_job_run_id}/report.pdf"
        s3 = _get_s3()
        _ensure_bucket(s3, REPORTS_BUCKET)
        s3.put_object(
            Bucket=REPORTS_BUCKET,
            Key=storage_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        logger.info("PDF uploaded to MinIO bucket=%s key=%s", REPORTS_BUCKET, storage_key)

        # Update generated_reports
        now = datetime.now(timezone.utc)
        db.execute(
            text(
                "UPDATE generated_reports SET status='completed', storage_key=:sk, bucket=:b, "
                "file_size_bytes=:sz, generated_at=:t WHERE id=:id"
            ),
            {
                "sk": storage_key,
                "b": REPORTS_BUCKET,
                "sz": len(pdf_bytes),
                "t": now,
                "id": report_id,
            },
        )
        db.commit()

        _update_job_run(db, report_job_run_id, "completed")
        logger.info(
            "generate_pdf_report completed report_id=%s storage_key=%s",
            report_id,
            storage_key,
        )

        return {
            "status": "completed",
            "report_id": report_id,
            "storage_key": storage_key,
        }

    except Exception as exc:
        logger.exception("generate_pdf_report failed job_run_id=%s: %s", job_run_id, exc)
        try:
            from sqlalchemy import text
            db.execute(
                text("UPDATE generated_reports SET status='failed', error_msg=:e WHERE project_id=:p AND status='pending'"),
                {"e": str(exc), "p": project_id},
            )
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


# Keep backward-compatible stub for old tasks
def generate_report(job_id: int, project_id: int):
    """Legacy function, kept for backward compatibility."""
    logger.info("Legacy generate_report called, dispatching generate_pdf_report")
    generate_pdf_report.delay(job_id, project_id)


@celery_app.task(name="worker.tasks.report_tasks.generate_report_task", bind=True)
def generate_report_task(self, job_id: int, project_id: int):
    """Legacy task name kept for compatibility."""
    generate_report(job_id, project_id)
    return {"status": "dispatched", "job_id": job_id}
