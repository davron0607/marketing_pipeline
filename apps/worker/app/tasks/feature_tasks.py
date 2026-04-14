import logging
import json
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import SessionLocal
from app.fraud.feature_engineering import (
    compute_duration_sec,
    compute_completion_speed_zscore,
    compute_straightline_ratio,
    compute_answer_entropy,
    compute_longstring_max,
    compute_duplicate_answer_vector_hash,
    compute_open_text_length_mean,
    compute_open_text_uniqueness_score,
    compute_attention_fail_count,
    compute_contradiction_count,
    compute_device_submission_count_24h,
    compute_ip_submission_count_24h,
    compute_missingness_ratio,
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


@celery_app.task(name="app.tasks.feature_tasks.compute_response_features", bind=True)
def compute_response_features(self, job_run_id: int, project_id: int):
    """
    Load all survey_responses for this job_run_id, compute all features,
    batch insert into response_features, and update job_run status.
    Then chain to fraud scoring.
    """
    logger.info(
        "compute_response_features start job_run_id=%s project_id=%s",
        job_run_id,
        project_id,
    )
    db = SessionLocal()
    try:
        # Create a new job_run for the feature task
        from sqlalchemy import text

        # Insert a new job_run for this feature task phase
        res = db.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, created_at) "
                "VALUES (:p, 'compute_response_features', 'running', :t) RETURNING id"
            ),
            {"p": project_id, "t": datetime.now(timezone.utc)},
        )
        feature_job_run_id = res.fetchone()[0]
        db.commit()
        logger.info("Created feature job_run id=%s", feature_job_run_id)

        # Load survey_responses for original job_run_id
        result = db.execute(
            text(
                "SELECT id, normalized_data, raw_data FROM survey_responses "
                "WHERE job_run_id=:j ORDER BY id"
            ),
            {"j": job_run_id},
        )
        responses = result.fetchall()
        logger.info("Loaded %d responses for job_run_id=%s", len(responses), job_run_id)

        if not responses:
            _update_job_run(db, feature_job_run_id, "completed")
            logger.info("No responses to process, marking completed")
            return {"status": "completed", "job_run_id": feature_job_run_id, "features_computed": 0}

        # Pre-compute batch-level metrics
        all_normalized = []
        for resp_id, norm_data_raw, raw_data_raw in responses:
            if isinstance(norm_data_raw, str):
                nd = json.loads(norm_data_raw)
            elif norm_data_raw is None:
                nd = {}
            else:
                nd = dict(norm_data_raw)
            all_normalized.append((resp_id, nd))

        # Compute durations for zscore
        all_durations = [compute_duration_sec(nd) for _, nd in all_normalized]

        # Collect all open texts and hashes for batch scoring
        all_open_texts = [
            " ".join(
                str(v)
                for k, v in nd.items()
                if any(k.endswith(s) for s in ("_text", "_comment", "_other", "_open"))
                and v is not None
            )
            for _, nd in all_normalized
        ]
        all_hashes = [compute_duplicate_answer_vector_hash(nd) for _, nd in all_normalized]

        rows_to_insert = []
        now = datetime.now(timezone.utc)

        for i, (resp_id, nd) in enumerate(all_normalized):
            duration_sec = all_durations[i]
            speed_zscore = compute_completion_speed_zscore(duration_sec, all_durations)
            straightline = compute_straightline_ratio(nd)
            entropy = compute_answer_entropy(nd)
            longstring = compute_longstring_max(nd)
            dup_hash = all_hashes[i]
            open_text_mean = compute_open_text_length_mean(nd)
            open_text_combined = all_open_texts[i]
            uniqueness = compute_open_text_uniqueness_score(open_text_combined, all_open_texts)
            attn_fail = compute_attention_fail_count(nd, [], {})
            contradiction = compute_contradiction_count(nd, [])
            device_id = nd.get("device_id") or ""
            ip_address = nd.get("ip_address") or ""
            device_count = compute_device_submission_count_24h(device_id, project_id, db)
            ip_count = compute_ip_submission_count_24h(ip_address, project_id, db)
            missingness = compute_missingness_ratio(nd)

            features_dict = {
                "duration_sec": duration_sec,
                "completion_speed_zscore": speed_zscore,
                "straightline_ratio": straightline,
                "answer_entropy": entropy,
                "longstring_max": longstring,
                "duplicate_answer_vector_hash": dup_hash,
                "open_text_length_mean": open_text_mean,
                "open_text_uniqueness_score": uniqueness,
                "attention_fail_count": attn_fail,
                "contradiction_count": contradiction,
                "device_submission_count_24h": device_count,
                "ip_submission_count_24h": ip_count,
                "missingness_ratio": missingness,
            }

            rows_to_insert.append({
                "project_id": project_id,
                "survey_response_id": resp_id,
                "job_run_id": feature_job_run_id,
                "duration_sec": duration_sec if duration_sec >= 0 else None,
                "completion_speed_zscore": speed_zscore,
                "straightline_ratio": straightline,
                "answer_entropy": entropy,
                "longstring_max": longstring,
                "duplicate_answer_vector_hash": dup_hash,
                "open_text_length_mean": open_text_mean,
                "open_text_uniqueness_score": uniqueness,
                "attention_fail_count": attn_fail,
                "contradiction_count": contradiction,
                "device_submission_count_24h": device_count,
                "ip_submission_count_24h": ip_count,
                "missingness_ratio": missingness,
                "features_json": json.dumps(features_dict),
                "computed_at": now,
            })

        # Batch insert
        CHUNK = 200
        for i in range(0, len(rows_to_insert), CHUNK):
            chunk = rows_to_insert[i:i + CHUNK]
            db.execute(
                text(
                    "INSERT INTO response_features "
                    "(project_id, survey_response_id, job_run_id, duration_sec, completion_speed_zscore, "
                    "straightline_ratio, answer_entropy, longstring_max, duplicate_answer_vector_hash, "
                    "open_text_length_mean, open_text_uniqueness_score, attention_fail_count, contradiction_count, "
                    "device_submission_count_24h, ip_submission_count_24h, missingness_ratio, features_json, computed_at) "
                    "VALUES (:project_id, :survey_response_id, :job_run_id, :duration_sec, :completion_speed_zscore, "
                    ":straightline_ratio, :answer_entropy, :longstring_max, :duplicate_answer_vector_hash, "
                    ":open_text_length_mean, :open_text_uniqueness_score, :attention_fail_count, :contradiction_count, "
                    ":device_submission_count_24h, :ip_submission_count_24h, :missingness_ratio, "
                    "cast(:features_json as jsonb), :computed_at)"
                ),
                chunk,
            )
            db.commit()
            logger.info("Inserted feature chunk %d-%d", i, i + len(chunk))

        _update_job_run(db, feature_job_run_id, "completed")
        logger.info(
            "compute_response_features completed job_run_id=%s features=%d",
            feature_job_run_id,
            len(rows_to_insert),
        )

        # Chain to fraud scoring
        from app.tasks.scoring_tasks import run_fraud_scoring
        run_fraud_scoring.delay(feature_job_run_id, project_id, None)
        logger.info("Chained run_fraud_scoring for feature_job_run_id=%s", feature_job_run_id)

        return {
            "status": "completed",
            "job_run_id": feature_job_run_id,
            "features_computed": len(rows_to_insert),
        }

    except Exception as exc:
        logger.exception("compute_response_features failed job_run_id=%s: %s", job_run_id, exc)
        raise
    finally:
        db.close()
