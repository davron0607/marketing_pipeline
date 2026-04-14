import json
import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import SessionLocal
from app.fraud.scoring_engine import (
    compute_fraud_score,
    DEFAULT_WEIGHTS,
    DEFAULT_THRESHOLDS,
)

logger = logging.getLogger(__name__)


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


@celery_app.task(name="app.tasks.scoring_tasks.run_fraud_scoring", bind=True)
def run_fraud_scoring(self, job_run_id: int, project_id: int, config_id: int | None = None):
    """
    Load response_features for this job_run_id, load fraud config (or use defaults),
    compute fraud_score for each response, batch insert into fraud_scores,
    then chain to analytics.
    """
    logger.info(
        "run_fraud_scoring start job_run_id=%s project_id=%s config_id=%s",
        job_run_id,
        project_id,
        config_id,
    )
    db = SessionLocal()
    try:
        from sqlalchemy import text

        # Create a new job_run for this scoring phase
        res = db.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, created_at) "
                "VALUES (:p, 'run_fraud_scoring', 'running', :t) RETURNING id"
            ),
            {"p": project_id, "t": datetime.now(timezone.utc)},
        )
        scoring_job_run_id = res.fetchone()[0]
        db.commit()
        logger.info("Created scoring job_run id=%s", scoring_job_run_id)

        # Load or create fraud_score_config
        weights = DEFAULT_WEIGHTS.copy()
        thresholds = DEFAULT_THRESHOLDS.copy()
        attention_rules = []
        contradiction_rules_list = []
        actual_config_id = None

        if config_id is not None:
            row = db.execute(
                text("SELECT id, weights, thresholds, attention_rules, contradiction_rules FROM fraud_score_configs WHERE id=:c"),
                {"c": config_id},
            ).fetchone()
            if row:
                actual_config_id = row[0]
                weights = dict(row[1]) if row[1] else weights
                thresholds = dict(row[2]) if row[2] else thresholds
                attention_rules = list(row[3]) if row[3] else []
                contradiction_rules_list = list(row[4]) if row[4] else []
        else:
            # Try active config for this project
            row = db.execute(
                text(
                    "SELECT id, weights, thresholds, attention_rules, contradiction_rules "
                    "FROM fraud_score_configs WHERE project_id=:p AND is_active=true ORDER BY id DESC LIMIT 1"
                ),
                {"p": project_id},
            ).fetchone()
            if row:
                actual_config_id = row[0]
                weights = dict(row[1]) if row[1] else weights
                thresholds = dict(row[2]) if row[2] else thresholds
                attention_rules = list(row[3]) if row[3] else []
                contradiction_rules_list = list(row[4]) if row[4] else []
            else:
                # Create default config
                res = db.execute(
                    text(
                        "INSERT INTO fraud_score_configs "
                        "(project_id, config_name, weights, thresholds, is_active) "
                        "VALUES (:p, 'Default', cast(:w as jsonb), cast(:t as jsonb), true) RETURNING id"
                    ),
                    {
                        "p": project_id,
                        "w": json.dumps(DEFAULT_WEIGHTS),
                        "t": json.dumps(DEFAULT_THRESHOLDS),
                    },
                )
                actual_config_id = res.fetchone()[0]
                db.commit()
                logger.info("Created default fraud_score_config id=%s", actual_config_id)

        # Load response_features for this job_run_id
        result = db.execute(
            text(
                "SELECT rf.id, rf.survey_response_id, rf.duplicate_answer_vector_hash, "
                "rf.duration_sec, rf.completion_speed_zscore, rf.straightline_ratio, "
                "rf.answer_entropy, rf.longstring_max, rf.open_text_length_mean, "
                "rf.open_text_uniqueness_score, rf.attention_fail_count, "
                "rf.contradiction_count, rf.device_submission_count_24h, "
                "rf.ip_submission_count_24h, rf.missingness_ratio "
                "FROM response_features rf "
                "WHERE rf.job_run_id=:j ORDER BY rf.id"
            ),
            {"j": job_run_id},
        )
        feature_rows = result.fetchall()
        logger.info("Loaded %d feature rows for job_run_id=%s", len(feature_rows), job_run_id)

        if not feature_rows:
            _update_job_run(db, scoring_job_run_id, "completed")
            logger.info("No features found, completing scoring job")
            return {"status": "completed", "job_run_id": scoring_job_run_id, "scores_computed": 0}

        # Collect all hashes for duplicate detection
        all_hashes = [row[2] or "" for row in feature_rows]

        rows_to_insert = []
        now = datetime.now(timezone.utc)

        for row in feature_rows:
            (feat_id, sr_id, dup_hash, duration_sec, speed_zscore, straightline,
             entropy, longstring, open_text_mean, uniqueness, attn_fail,
             contradiction, device_count, ip_count, missingness) = row

            features_dict = {
                "duration_sec": duration_sec if duration_sec is not None else -1.0,
                "completion_speed_zscore": speed_zscore or 0.0,
                "straightline_ratio": straightline or 0.0,
                "answer_entropy": entropy or 0.0,
                "longstring_max": longstring or 0,
                "duplicate_answer_vector_hash": dup_hash or "",
                "open_text_length_mean": open_text_mean or 0.0,
                "open_text_uniqueness_score": uniqueness or 0.0,
                "attention_fail_count": attn_fail or 0,
                "contradiction_count": contradiction or 0,
                "device_submission_count_24h": device_count or 0,
                "ip_submission_count_24h": ip_count or 0,
                "missingness_ratio": missingness or 0.0,
            }

            score_result = compute_fraud_score(
                features=features_dict,
                weights=weights,
                thresholds=thresholds,
                all_hashes=all_hashes,
            )

            rows_to_insert.append({
                "project_id": project_id,
                "survey_response_id": sr_id,
                "response_features_id": feat_id,
                "fraud_score": score_result["fraud_score"],
                "fraud_label": score_result["fraud_label"],
                "fraud_reasons": json.dumps(score_result["fraud_reasons"]),
                "component_scores": json.dumps(score_result["component_scores"]),
                "config_id": actual_config_id,
                "scored_at": now,
            })

        # Batch insert fraud_scores
        CHUNK = 200
        for i in range(0, len(rows_to_insert), CHUNK):
            chunk = rows_to_insert[i:i + CHUNK]
            db.execute(
                text(
                    "INSERT INTO fraud_scores "
                    "(project_id, survey_response_id, response_features_id, fraud_score, "
                    "fraud_label, fraud_reasons, component_scores, config_id, scored_at) "
                    "VALUES (:project_id, :survey_response_id, :response_features_id, :fraud_score, "
                    ":fraud_label, cast(:fraud_reasons as jsonb), cast(:component_scores as jsonb), :config_id, :scored_at)"
                ),
                chunk,
            )
            db.commit()
            logger.info("Inserted fraud_scores chunk %d-%d", i, i + len(chunk))

        _update_job_run(db, scoring_job_run_id, "completed")
        logger.info(
            "run_fraud_scoring completed job_run_id=%s scores=%d",
            scoring_job_run_id,
            len(rows_to_insert),
        )

        # Chain to analytics
        from app.tasks.analytics_tasks import run_analytics
        run_analytics.delay(scoring_job_run_id, project_id)
        logger.info("Chained run_analytics for scoring_job_run_id=%s", scoring_job_run_id)

        return {
            "status": "completed",
            "job_run_id": scoring_job_run_id,
            "scores_computed": len(rows_to_insert),
        }

    except Exception as exc:
        logger.exception("run_fraud_scoring failed job_run_id=%s: %s", job_run_id, exc)
        raise
    finally:
        db.close()
