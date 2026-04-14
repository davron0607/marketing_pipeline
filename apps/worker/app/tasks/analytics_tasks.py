import json
import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import SessionLocal
from app.analytics.distributions import (
    compute_single_choice_distribution,
    compute_numeric_stats,
    compute_text_summary,
    detect_column_type,
)
from app.analytics.crosstabs import compute_crosstab, find_top_drivers
from app.analytics.insights import (
    generate_sample_quality_insight,
    generate_segment_insight,
    generate_driver_insight,
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


@celery_app.task(name="app.tasks.analytics_tasks.run_analytics", bind=True)
def run_analytics(self, job_run_id: int, project_id: int):
    """
    Run analytics pipeline:
    1. Load usable survey_responses (valid + review fraud_scores)
    2. Compute per-column distributions
    3. Run crosstabs for first 3 segment vars x first 3 outcome vars
    4. Generate insight texts
    5. Save all to analytics_results
    6. Chain to report generation
    """
    logger.info(
        "run_analytics start job_run_id=%s project_id=%s",
        job_run_id,
        project_id,
    )
    db = SessionLocal()
    try:
        import pandas as pd
        from sqlalchemy import text

        # Create analytics job_run
        res = db.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, created_at) "
                "VALUES (:p, 'run_analytics', 'running', :t) RETURNING id"
            ),
            {"p": project_id, "t": datetime.now(timezone.utc)},
        )
        analytics_job_run_id = res.fetchone()[0]
        db.commit()
        logger.info("Created analytics job_run id=%s", analytics_job_run_id)

        # Load fraud score counts for this project
        counts_result = db.execute(
            text(
                "SELECT fraud_label, COUNT(*) FROM fraud_scores "
                "WHERE project_id=:p GROUP BY fraud_label"
            ),
            {"p": project_id},
        )
        label_counts = {row[0]: int(row[1]) for row in counts_result.fetchall()}
        total_scored = sum(label_counts.values())
        valid_count = label_counts.get("valid", 0)
        review_count = label_counts.get("review", 0)
        reject_count = label_counts.get("reject", 0)

        # Load usable responses (valid + review) joined with normalized_data
        usable_result = db.execute(
            text(
                "SELECT sr.id, sr.normalized_data, sr.respondent_id "
                "FROM survey_responses sr "
                "JOIN fraud_scores fs ON fs.survey_response_id = sr.id "
                "WHERE sr.project_id=:p AND fs.fraud_label IN ('valid', 'review') "
                "ORDER BY sr.id"
            ),
            {"p": project_id},
        )
        usable_rows = usable_result.fetchall()
        logger.info("Loaded %d usable responses", len(usable_rows))

        analytics_to_insert = []
        now_ts = datetime.now(timezone.utc)

        # Sample quality insight
        quality_insight = generate_sample_quality_insight(
            total=total_scored,
            valid=valid_count,
            review=review_count,
            reject=reject_count,
        )
        analytics_to_insert.append({
            "project_id": project_id,
            "job_run_id": analytics_job_run_id,
            "analysis_type": "sample_quality",
            "question_key": None,
            "result_data": json.dumps({
                "total": total_scored,
                "valid": valid_count,
                "review": review_count,
                "reject": reject_count,
                "usable": valid_count + review_count,
            }),
            "insight_text": quality_insight,
        })

        if not usable_rows:
            _save_analytics(db, analytics_to_insert)
            _update_job_run(db, analytics_job_run_id, "completed")
            logger.info("No usable responses, analytics completed with quality insight only")
            return {"status": "completed", "job_run_id": analytics_job_run_id}

        # Build DataFrame from normalized_data
        records = []
        for row_id, norm_data_raw, resp_id in usable_rows:
            if isinstance(norm_data_raw, str):
                nd = json.loads(norm_data_raw)
            elif norm_data_raw is None:
                nd = {}
            else:
                nd = dict(norm_data_raw)
            nd["_response_id"] = row_id
            nd["_respondent_id"] = resp_id
            records.append(nd)

        df = pd.DataFrame(records)
        # Drop internal columns for analysis
        analysis_cols = [c for c in df.columns if not c.startswith("_")]
        logger.info("DataFrame shape=%s analysis_cols=%d", df.shape, len(analysis_cols))

        # Per-column distributions
        for col in analysis_cols[:50]:  # Limit to first 50 columns
            try:
                col_values = df[col].tolist()
                col_type = detect_column_type(col_values)

                if col_type == "numeric":
                    dist_data = compute_numeric_stats(col_values)
                    analysis_type = "distribution_numeric"
                elif col_type == "text":
                    dist_data = compute_text_summary(col_values)
                    analysis_type = "distribution_text"
                else:
                    dist_data = compute_single_choice_distribution(col_values)
                    analysis_type = "distribution_single_choice"

                analytics_to_insert.append({
                    "project_id": project_id,
                    "job_run_id": analytics_job_run_id,
                    "analysis_type": analysis_type,
                    "question_key": col,
                    "result_data": json.dumps(dist_data),
                    "insight_text": None,
                })
            except Exception as col_exc:
                logger.warning("Error computing distribution for col=%s: %s", col, col_exc)

        # Crosstabs: first 3 "segment" vars x first 3 "outcome" vars
        # Heuristic: pick categorical columns with 2-10 distinct values as segment vars
        # Pick columns that look like scales (numeric or few ordered choices) as outcome vars
        def is_segment_candidate(col: str) -> bool:
            vals = [v for v in df[col].dropna().tolist() if str(v).strip()]
            n_distinct = len(set(str(v).strip() for v in vals))
            return 2 <= n_distinct <= 10

        def is_outcome_candidate(col: str) -> bool:
            vals = df[col].dropna().tolist()
            numeric_count = sum(1 for v in vals if _is_numeric(v))
            return len(vals) > 0 and numeric_count / len(vals) > 0.5

        segment_vars = [c for c in analysis_cols if is_segment_candidate(c)][:3]
        outcome_vars = [c for c in analysis_cols if is_outcome_candidate(c)][:3]

        for seg_var in segment_vars:
            for out_var in outcome_vars:
                if seg_var == out_var:
                    continue
                try:
                    ct = compute_crosstab(df, seg_var, out_var)
                    analytics_to_insert.append({
                        "project_id": project_id,
                        "job_run_id": analytics_job_run_id,
                        "analysis_type": "crosstab",
                        "question_key": f"{seg_var}|{out_var}",
                        "result_data": json.dumps(ct),
                        "insight_text": None,
                    })
                except Exception as ct_exc:
                    logger.warning("crosstab error %s x %s: %s", seg_var, out_var, ct_exc)

        # Top drivers for each outcome variable
        for out_var in outcome_vars:
            try:
                drivers = find_top_drivers(df, out_var, analysis_cols)[:5]
                for d in drivers:
                    insight_text = generate_driver_insight(
                        driver_var=d["variable"],
                        target_var=d["target"],
                        effect_size=d["effect_size"],
                    )
                    analytics_to_insert.append({
                        "project_id": project_id,
                        "job_run_id": analytics_job_run_id,
                        "analysis_type": "top_driver",
                        "question_key": f"target:{out_var}|driver:{d['variable']}",
                        "result_data": json.dumps(d),
                        "insight_text": insight_text,
                    })

                    # Segment insight for top driver
                    if segment_vars:
                        top_seg = segment_vars[0]
                        try:
                            seg_vals = df[top_seg].dropna().unique()
                            if len(seg_vals) > 0:
                                overall_out = pd.to_numeric(df[out_var], errors="coerce").dropna()
                                if len(overall_out) > 0:
                                    overall_mean = float(overall_out.mean())
                                    for sv in seg_vals[:3]:
                                        seg_subset = df[df[top_seg] == sv]
                                        seg_out = pd.to_numeric(seg_subset[out_var], errors="coerce").dropna()
                                        if len(seg_out) > 0:
                                            seg_mean = float(seg_out.mean())
                                            seg_insight = generate_segment_insight(
                                                segment_var=top_seg,
                                                segment_value=str(sv),
                                                outcome_var=out_var,
                                                outcome_mean=seg_mean,
                                                overall_mean=overall_mean,
                                            )
                                            analytics_to_insert.append({
                                                "project_id": project_id,
                                                "job_run_id": analytics_job_run_id,
                                                "analysis_type": "segment_insight",
                                                "question_key": f"{top_seg}={sv}|{out_var}",
                                                "result_data": json.dumps({"segment_var": top_seg, "segment_value": str(sv), "outcome_var": out_var, "segment_mean": seg_mean, "overall_mean": overall_mean}),
                                                "insight_text": seg_insight,
                                            })
                        except Exception as si_exc:
                            logger.warning("segment insight error: %s", si_exc)
            except Exception as d_exc:
                logger.warning("top_drivers error for %s: %s", out_var, d_exc)

        # Save all analytics rows
        _save_analytics(db, analytics_to_insert)

        _update_job_run(db, analytics_job_run_id, "completed")
        logger.info(
            "run_analytics completed job_run_id=%s rows=%d",
            analytics_job_run_id,
            len(analytics_to_insert),
        )

        # Chain to report generation
        from app.tasks.report_tasks import generate_pdf_report
        generate_pdf_report.delay(analytics_job_run_id, project_id)
        logger.info("Chained generate_pdf_report for analytics_job_run_id=%s", analytics_job_run_id)

        return {
            "status": "completed",
            "job_run_id": analytics_job_run_id,
            "analytics_rows": len(analytics_to_insert),
        }

    except Exception as exc:
        logger.exception("run_analytics failed job_run_id=%s: %s", job_run_id, exc)
        raise
    finally:
        db.close()


def _save_analytics(db, rows: list) -> None:
    from sqlalchemy import text
    CHUNK = 100
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        db.execute(
            text(
                "INSERT INTO analytics_results "
                "(project_id, job_run_id, analysis_type, question_key, result_data, insight_text) "
                "VALUES (:project_id, :job_run_id, :analysis_type, :question_key, "
                ":result_data::jsonb, :insight_text)"
            ),
            chunk,
        )
        db.commit()


def _is_numeric(val) -> bool:
    try:
        import math
        f = float(str(val))
        return not math.isnan(f) and not math.isinf(f)
    except Exception:
        return False
