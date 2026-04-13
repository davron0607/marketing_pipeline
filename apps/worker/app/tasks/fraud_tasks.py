import json
import logging
import pandas as pd
from app.celery_app import celery_app
from app.db import SessionLocal

logger = logging.getLogger(__name__)

# Fraud detection thresholds
STRAIGHT_LINE_THRESHOLD = 0.9   # fraction of identical answers
SPEED_THRESHOLD_SECONDS = 60     # too fast = suspect


def detect_straight_lining(df: pd.DataFrame) -> list[dict]:
    """Flag respondents who answered all questions identically."""
    flags = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if len(numeric_cols) < 3:
        return flags

    id_col = df.columns[0]
    for _, row in df.iterrows():
        vals = row[numeric_cols].dropna()
        if len(vals) == 0:
            continue
        unique_ratio = vals.nunique() / len(vals)
        if unique_ratio <= (1 - STRAIGHT_LINE_THRESHOLD):
            flags.append({
                "respondent_id": str(row[id_col]),
                "flag_type": "straight_lining",
                "confidence": round(1.0 - unique_ratio, 3),
                "details": f"Only {vals.nunique()} unique values across {len(vals)} responses",
            })
    return flags


def detect_duplicates(df: pd.DataFrame) -> list[dict]:
    """Flag exact duplicate rows."""
    flags = []
    id_col = df.columns[0]
    data_cols = df.columns[1:]
    dupes = df.duplicated(subset=data_cols, keep="first")
    for idx, is_dupe in dupes.items():
        if is_dupe:
            flags.append({
                "respondent_id": str(df.loc[idx, id_col]),
                "flag_type": "duplicate_response",
                "confidence": 1.0,
                "details": "Exact duplicate of another response",
            })
    return flags


def run_fraud_detection(job_id: int, project_id: int, df_json: str):
    """Called directly (not as Celery task) from within analysis_tasks."""
    db = SessionLocal()
    try:
        df = pd.read_json(df_json)

        all_flags = []
        all_flags.extend(detect_straight_lining(df))
        all_flags.extend(detect_duplicates(df))

        if all_flags:
            from sqlalchemy import text
            for flag in all_flags:
                db.execute(
                    text(
                        "INSERT INTO fraud_results (project_id, job_id, respondent_id, flag_type, confidence, details) "
                        "VALUES (:p, :j, :r, :f, :c, :d)"
                    ),
                    {
                        "p": project_id,
                        "j": job_id,
                        "r": flag["respondent_id"],
                        "f": flag["flag_type"],
                        "c": flag["confidence"],
                        "d": flag["details"],
                    },
                )
            db.commit()
            logger.info(f"Inserted {len(all_flags)} fraud flags for job_id={job_id}")
    except Exception as e:
        logger.exception(f"Fraud detection failed: {e}")
    finally:
        db.close()


@celery_app.task(name="worker.tasks.fraud_tasks.run_fraud_check", bind=True)
def run_fraud_check(self, job_id: int, project_id: int, df_json: str):
    run_fraud_detection(job_id, project_id, df_json)
    return {"status": "completed", "job_id": job_id}
