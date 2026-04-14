"""
Seed script: creates demo user, project, synthetic survey responses,
features, fraud scores, and analytics results.

Run inside the api container:
    docker compose exec api python scripts/seed.py
"""
import json
import hashlib
import math
import random
import sys
import os
import logging
from datetime import datetime, timezone, timedelta

# Allow imports from /app
sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed")

from sqlalchemy import create_engine, text
import bcrypt

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@postgres:5432/survey_analytics",
).replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(DATABASE_URL, echo=False)

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"
DEMO_PROJECT = "Demo Survey Project"

random.seed(42)

# ── helpers ──────────────────────────────────────────────────────────────────

def _hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _md5(values: list) -> str:
    s = "|".join(sorted(str(v) for v in values))
    return hashlib.md5(s.encode()).hexdigest()


def _entropy(values: list) -> float:
    freq: dict = {}
    for v in values:
        freq[str(v)] = freq.get(str(v), 0) + 1
    total = len(values)
    if total == 0:
        return 0.0
    ent = 0.0
    for c in freq.values():
        p = c / total
        if p > 0:
            ent -= p * math.log2(p)
    return ent


def _zscore(val: float, vals: list) -> float:
    clean = [v for v in vals if v >= 0]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    var = sum((x - mean) ** 2 for x in clean) / len(clean)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return (val - mean) / std


def _make_normal_response(idx: int) -> dict:
    """70 normal responses — varied answers, reasonable duration."""
    age_groups = ["18-24", "25-34", "35-44", "45-54", "55+"]
    satisfaction = [str(random.randint(1, 5)) for _ in range(5)]
    duration = random.randint(180, 900)
    return {
        "respondent_id": f"R{idx:04d}",
        "q_age": random.choice(age_groups),
        "q_gender": random.choice(["Male", "Female", "Non-binary", "Prefer not to say"]),
        "q_sat_1": random.choice(satisfaction),
        "q_sat_2": random.choice(satisfaction),
        "q_sat_3": random.choice(satisfaction),
        "q_sat_4": random.choice(satisfaction),
        "q_nps": str(random.randint(0, 10)),
        "q_product_usage": random.choice(["Daily", "Weekly", "Monthly", "Rarely"]),
        "q_open_text": random.choice([
            "Great product overall, minor UX issues",
            "Very satisfied with the service",
            "Could improve onboarding",
            "Support team was very helpful",
            "The feature I needed was easy to find",
        ]),
        "start_time": (datetime.now(timezone.utc) - timedelta(seconds=duration + 60)).isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "duration_sec": duration,
    }


def _make_straightliner(idx: int) -> dict:
    """15 straight-liners — all same answer on matrix questions."""
    fixed = "3"
    duration = random.randint(30, 90)
    return {
        "respondent_id": f"R{idx:04d}",
        "q_age": random.choice(["25-34", "35-44"]),
        "q_gender": "Male",
        "q_sat_1": fixed,
        "q_sat_2": fixed,
        "q_sat_3": fixed,
        "q_sat_4": fixed,
        "q_nps": fixed,
        "q_product_usage": "Weekly",
        "q_open_text": "ok",
        "start_time": (datetime.now(timezone.utc) - timedelta(seconds=duration + 60)).isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "duration_sec": duration,
    }


def _make_speedster(idx: int) -> dict:
    """10 speedsters — very short duration."""
    duration = random.randint(5, 25)
    return {
        "respondent_id": f"R{idx:04d}",
        "q_age": "18-24",
        "q_gender": "Female",
        "q_sat_1": str(random.randint(1, 5)),
        "q_sat_2": str(random.randint(1, 5)),
        "q_sat_3": str(random.randint(1, 5)),
        "q_sat_4": str(random.randint(1, 5)),
        "q_nps": str(random.randint(0, 10)),
        "q_product_usage": "Daily",
        "q_open_text": "fast",
        "start_time": (datetime.now(timezone.utc) - timedelta(seconds=duration + 5)).isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "duration_sec": duration,
    }


def _make_duplicate(idx: int) -> dict:
    """5 duplicates — identical answer vector."""
    return {
        "respondent_id": f"R{idx:04d}",
        "q_age": "35-44",
        "q_gender": "Male",
        "q_sat_1": "4",
        "q_sat_2": "4",
        "q_sat_3": "4",
        "q_sat_4": "4",
        "q_nps": "7",
        "q_product_usage": "Monthly",
        "q_open_text": "good",
        "start_time": (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "duration_sec": 200,
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    with engine.connect() as conn:
        # ── User ──────────────────────────────────────────────────────────────
        row = conn.execute(
            text("SELECT id FROM users WHERE email=:e"), {"e": DEMO_EMAIL}
        ).fetchone()
        if row:
            user_id = row[0]
            logger.info("Demo user already exists id=%s", user_id)
        else:
            hashed = _hash_pw(DEMO_PASSWORD)
            row = conn.execute(
                text(
                    "INSERT INTO users (email, hashed_password, full_name, is_active) "
                    "VALUES (:e, :h, 'Demo User', true) RETURNING id"
                ),
                {"e": DEMO_EMAIL, "h": hashed},
            ).fetchone()
            user_id = row[0]
            conn.commit()
            logger.info("Created demo user id=%s email=%s", user_id, DEMO_EMAIL)

        # ── Project ───────────────────────────────────────────────────────────
        row = conn.execute(
            text("SELECT id FROM projects WHERE owner_id=:u AND name=:n"),
            {"u": user_id, "n": DEMO_PROJECT},
        ).fetchone()
        if row:
            project_id = row[0]
            logger.info("Demo project already exists id=%s", project_id)
        else:
            row = conn.execute(
                text(
                    "INSERT INTO projects (name, description, owner_id) "
                    "VALUES (:n, :d, :u) RETURNING id"
                ),
                {
                    "n": DEMO_PROJECT,
                    "d": "Auto-generated demo project for testing the pipeline",
                    "u": user_id,
                },
            ).fetchone()
            project_id = row[0]
            conn.commit()
            logger.info("Created demo project id=%s", project_id)

        # ── Check existing responses ───────────────────────────────────────────
        existing = conn.execute(
            text("SELECT COUNT(*) FROM survey_responses WHERE project_id=:p"),
            {"p": project_id},
        ).fetchone()[0]
        if existing > 0:
            logger.info("Seed data already present (%d responses). Skipping.", existing)
            return

        # ── Uploaded file + job run ────────────────────────────────────────────
        uf_row = conn.execute(
            text(
                "INSERT INTO uploaded_files "
                "(project_id, original_filename, storage_key, bucket, file_size_bytes, "
                "row_count, mime_type, upload_status) "
                "VALUES (:p, 'demo_survey.csv', 'seed/demo_survey.csv', 'raw-uploads', "
                "51200, 100, 'text/csv', 'done') RETURNING id"
            ),
            {"p": project_id},
        ).fetchone()
        upload_file_id = uf_row[0]

        jr_row = conn.execute(
            text(
                "INSERT INTO job_runs (project_id, upload_file_id, task_name, status, "
                "started_at, completed_at) "
                "VALUES (:p, :u, 'process_uploaded_survey_file', 'completed', :s, :e) RETURNING id"
            ),
            {
                "p": project_id,
                "u": upload_file_id,
                "s": datetime.now(timezone.utc) - timedelta(minutes=5),
                "e": datetime.now(timezone.utc) - timedelta(minutes=4),
            },
        ).fetchone()
        job_run_id = jr_row[0]
        conn.commit()
        logger.info("Created upload_file_id=%s job_run_id=%s", upload_file_id, job_run_id)

        # ── Build synthetic responses ──────────────────────────────────────────
        responses = []
        idx = 1
        for _ in range(70):
            responses.append(("normal", _make_normal_response(idx)))
            idx += 1
        for _ in range(15):
            responses.append(("straightliner", _make_straightliner(idx)))
            idx += 1
        for _ in range(10):
            responses.append(("speedster", _make_speedster(idx)))
            idx += 1
        for _ in range(5):
            responses.append(("duplicate", _make_duplicate(idx)))
            idx += 1

        random.shuffle(responses)

        # ── Insert survey_responses ────────────────────────────────────────────
        response_ids = []
        for row_index, (pattern, nd) in enumerate(responses):
            respondent_id = nd.pop("respondent_id", str(row_index))
            raw_data = {k: v for k, v in nd.items()}
            normalized_data = {k: v for k, v in nd.items()}

            row = conn.execute(
                text(
                    "INSERT INTO survey_responses "
                    "(project_id, upload_file_id, job_run_id, respondent_id, raw_data, normalized_data, row_index) "
                    "VALUES (:p, :u, :j, :r, cast(:raw as jsonb), cast(:norm as jsonb), :ri) RETURNING id"
                ),
                {
                    "p": project_id,
                    "u": upload_file_id,
                    "j": job_run_id,
                    "r": respondent_id,
                    "raw": json.dumps(raw_data),
                    "norm": json.dumps(normalized_data),
                    "ri": row_index,
                },
            ).fetchone()
            response_ids.append((row[0], pattern, normalized_data))

        conn.commit()
        logger.info("Inserted %d survey_responses", len(response_ids))

        # ── Compute features ──────────────────────────────────────────────────
        feature_jr_row = conn.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, started_at, completed_at) "
                "VALUES (:p, 'compute_response_features', 'completed', :s, :e) RETURNING id"
            ),
            {
                "p": project_id,
                "s": datetime.now(timezone.utc) - timedelta(minutes=3),
                "e": datetime.now(timezone.utc) - timedelta(minutes=2, seconds=30),
            },
        ).fetchone()
        feature_job_run_id = feature_jr_row[0]
        conn.commit()

        all_durations = [float(nd.get("duration_sec", -1)) for _, _, nd in response_ids]
        all_texts = [str(nd.get("q_open_text", "")) for _, _, nd in response_ids]
        all_hashes = [_md5(list(nd.values())) for _, _, nd in response_ids]

        feature_rows = []
        now = datetime.now(timezone.utc)
        for sr_id, pattern, nd in response_ids:
            duration_sec = float(nd.get("duration_sec", -1))
            zscore = _zscore(duration_sec, all_durations)

            matrix_vals = [nd.get(f"q_sat_{i}", "") for i in range(1, 5)]
            non_null = [v for v in matrix_vals if v]
            straightline = (matrix_vals.count(matrix_vals[0]) / len(matrix_vals)) if matrix_vals else 0.0

            all_vals = [v for v in nd.values() if v]
            entropy = _entropy(all_vals)

            longstring_max = 1
            cur = 1
            for i in range(1, len(all_vals)):
                if str(all_vals[i]) == str(all_vals[i-1]):
                    cur += 1
                    longstring_max = max(longstring_max, cur)
                else:
                    cur = 1

            dup_hash = all_hashes[response_ids.index((sr_id, pattern, nd))]
            open_text = str(nd.get("q_open_text", ""))
            open_text_mean = float(len(open_text))
            uniqueness = all_texts.count(open_text) / len(all_texts)
            missingness = sum(1 for v in nd.values() if not v) / max(len(nd), 1)

            features_dict = {
                "duration_sec": duration_sec,
                "completion_speed_zscore": zscore,
                "straightline_ratio": straightline,
                "answer_entropy": entropy,
                "longstring_max": longstring_max,
                "duplicate_answer_vector_hash": dup_hash,
                "open_text_length_mean": open_text_mean,
                "open_text_uniqueness_score": uniqueness,
                "attention_fail_count": 0,
                "contradiction_count": 0,
                "device_submission_count_24h": 1,
                "ip_submission_count_24h": 1,
                "missingness_ratio": missingness,
            }

            feature_rows.append({
                "sr_id": sr_id,
                "fj": feature_job_run_id,
                **features_dict,
                "features_json": json.dumps(features_dict),
                "now": now,
            })

        for fr in feature_rows:
            conn.execute(
                text(
                    "INSERT INTO response_features "
                    "(project_id, survey_response_id, job_run_id, duration_sec, completion_speed_zscore, "
                    "straightline_ratio, answer_entropy, longstring_max, duplicate_answer_vector_hash, "
                    "open_text_length_mean, open_text_uniqueness_score, attention_fail_count, contradiction_count, "
                    "device_submission_count_24h, ip_submission_count_24h, missingness_ratio, features_json, computed_at) "
                    "VALUES (:p, :sr_id, :fj, :duration_sec, :completion_speed_zscore, "
                    ":straightline_ratio, :answer_entropy, :longstring_max, :duplicate_answer_vector_hash, "
                    ":open_text_length_mean, :open_text_uniqueness_score, :attention_fail_count, :contradiction_count, "
                    ":device_submission_count_24h, :ip_submission_count_24h, :missingness_ratio, "
                    "cast(:features_json as jsonb), :now) RETURNING id"
                ),
                {**fr, "p": project_id},
            )
        conn.commit()
        logger.info("Inserted %d response_features", len(feature_rows))

        # ── Fraud config ──────────────────────────────────────────────────────
        WEIGHTS = {
            "speed_component": 0.20, "straightline_component": 0.20,
            "entropy_component": 0.15, "contradiction_component": 0.10,
            "duplicate_component": 0.15, "open_text_component": 0.10,
            "missingness_component": 0.05, "geo_device_component": 0.05,
        }
        THRESHOLDS = {"valid_max": 29, "review_max": 59}

        cfg_row = conn.execute(
            text(
                "INSERT INTO fraud_score_configs (project_id, config_name, weights, thresholds, is_active) "
                "VALUES (:p, 'Default', cast(:w as jsonb), cast(:t as jsonb), true) RETURNING id"
            ),
            {"p": project_id, "w": json.dumps(WEIGHTS), "t": json.dumps(THRESHOLDS)},
        ).fetchone()
        config_id = cfg_row[0]
        conn.commit()

        # ── Insert fraud_scores ────────────────────────────────────────────────
        scoring_jr_row = conn.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, started_at, completed_at) "
                "VALUES (:p, 'run_fraud_scoring', 'completed', :s, :e) RETURNING id"
            ),
            {
                "p": project_id,
                "s": datetime.now(timezone.utc) - timedelta(minutes=2),
                "e": datetime.now(timezone.utc) - timedelta(minutes=1, seconds=30),
            },
        ).fetchone()
        conn.commit()

        # Re-fetch feature row ids
        feat_rows_db = conn.execute(
            text(
                "SELECT id, survey_response_id, duplicate_answer_vector_hash, "
                "duration_sec, completion_speed_zscore, straightline_ratio, "
                "answer_entropy, longstring_max, open_text_length_mean, "
                "open_text_uniqueness_score, attention_fail_count, contradiction_count, "
                "device_submission_count_24h, ip_submission_count_24h, missingness_ratio "
                "FROM response_features WHERE project_id=:p ORDER BY id"
            ),
            {"p": project_id},
        ).fetchall()

        db_all_hashes = [row[2] or "" for row in feat_rows_db]

        fraud_score_rows = []
        for row in feat_rows_db:
            (feat_id, sr_id, dup_hash, duration_sec, speed_z, straightline,
             entropy, longstring, open_text_mean, uniqueness, attn_fail,
             contradiction, device_count, ip_count, missingness) = row

            # Score speed
            speed_pen = 0.0
            speed_reason = None
            if (duration_sec or -1) >= 0:
                if (speed_z or 0) < -2.0:
                    speed_pen, speed_reason = 100.0, f"Completion speed extremely fast (z={speed_z:.2f})"
                elif (speed_z or 0) < -1.5:
                    speed_pen, speed_reason = 60.0, f"Completion speed fast (z={speed_z:.2f})"
            else:
                speed_pen = 20.0

            sl = straightline or 0.0
            straight_pen = sl * 100.0
            straight_reason = None
            if sl >= 0.8:
                straight_reason = f"Straightlining detected ({sl:.0%} identical matrix answers)"
            elif sl >= 0.5:
                straight_reason = f"Possible straightlining ({sl:.0%} identical matrix answers)"

            ent = entropy or 0.0
            ent_pen = max(0.0, (1.0 - ent / 3.0) * 100.0)
            ent_reason = f"Very low answer diversity (entropy={ent:.2f})" if ent < 0.5 else None

            dup_count = db_all_hashes.count(dup_hash or "")
            dup_pen = 80.0 if dup_count > 1 else 0.0
            dup_reason = f"Identical answer pattern shared with {dup_count-1} other respondent(s)" if dup_count > 1 else None

            miss = missingness or 0.0
            miss_pen = 80.0 if miss > 0.5 else miss * 100.0
            miss_reason = f"High missingness ratio ({miss:.0%} fields empty)" if miss > 0.5 else None

            ot_mean = open_text_mean or 0.0
            uniq = uniqueness or 0.0
            if ot_mean < 5 and uniq > 0.3:
                ot_pen, ot_reason = 80.0, "Very short or duplicate open-text responses"
            elif ot_mean < 20 and uniq > 0.5:
                ot_pen, ot_reason = 50.0, "Short and non-unique open-text responses"
            else:
                ot_pen, ot_reason = max(0.0, (1.0 - ot_mean / 50.0) * uniq * 60.0), None

            contr_pen = min(100.0, (contradiction or 0) * 25.0)
            contr_reason = f"{contradiction} logical contradiction(s) detected" if (contradiction or 0) > 0 else None

            geo_pen = 0.0
            geo_reason = None

            components = {
                "speed_component": round(speed_pen, 4),
                "straightline_component": round(straight_pen, 4),
                "entropy_component": round(ent_pen, 4),
                "contradiction_component": round(contr_pen, 4),
                "duplicate_component": round(dup_pen, 4),
                "open_text_component": round(ot_pen, 4),
                "missingness_component": round(miss_pen, 4),
                "geo_device_component": round(geo_pen, 4),
            }

            score = sum(WEIGHTS[k] * v for k, v in components.items())
            score = min(100.0, max(0.0, score))

            if score <= 29:
                label = "valid"
            elif score <= 59:
                label = "review"
            else:
                label = "reject"

            reasons = [r for r in [speed_reason, straight_reason, ent_reason, dup_reason,
                                   ot_reason, miss_reason, contr_reason, geo_reason] if r]

            fraud_score_rows.append({
                "p": project_id,
                "sr": sr_id,
                "rf": feat_id,
                "score": round(score, 4),
                "label": label,
                "reasons": json.dumps(reasons),
                "components": json.dumps(components),
                "cfg": config_id,
                "scored_at": now,
            })

        for fs in fraud_score_rows:
            conn.execute(
                text(
                    "INSERT INTO fraud_scores "
                    "(project_id, survey_response_id, response_features_id, fraud_score, fraud_label, "
                    "fraud_reasons, component_scores, config_id, scored_at) "
                    "VALUES (:p, :sr, :rf, :score, :label, cast(:reasons as jsonb), cast(:components as jsonb), :cfg, :scored_at)"
                ),
                fs,
            )
        conn.commit()

        label_counts = {}
        for fs in fraud_score_rows:
            label_counts[fs["label"]] = label_counts.get(fs["label"], 0) + 1
        logger.info("Inserted %d fraud_scores: %s", len(fraud_score_rows), label_counts)

        # ── Analytics results ─────────────────────────────────────────────────
        analytics_jr_row = conn.execute(
            text(
                "INSERT INTO job_runs (project_id, task_name, status, started_at, completed_at) "
                "VALUES (:p, 'run_analytics', 'completed', :s, :e) RETURNING id"
            ),
            {
                "p": project_id,
                "s": datetime.now(timezone.utc) - timedelta(minutes=1),
                "e": datetime.now(timezone.utc) - timedelta(seconds=20),
            },
        ).fetchone()
        analytics_job_run_id = analytics_jr_row[0]
        conn.commit()

        total = len(fraud_score_rows)
        valid = label_counts.get("valid", 0)
        review = label_counts.get("review", 0)
        reject = label_counts.get("reject", 0)
        usable = valid + review
        reject_pct = round(reject / total * 100, 1) if total else 0.0

        analytics_rows = [
            {
                "p": project_id,
                "j": analytics_job_run_id,
                "atype": "sample_quality",
                "qkey": None,
                "rdata": json.dumps({"total": total, "valid": valid, "review": review, "reject": reject, "usable": usable}),
                "itext": f"After fraud cleanup, usable sample size is {usable:,} from {total:,} submissions ({reject_pct}% rejected as likely fraudulent).",
            },
            {
                "p": project_id,
                "j": analytics_job_run_id,
                "atype": "distribution_single_choice",
                "qkey": "q_age",
                "rdata": json.dumps({
                    "counts": {"25-34": 28, "35-44": 25, "18-24": 22, "45-54": 15, "55+": 10},
                    "percentages": {"25-34": 28.0, "35-44": 25.0, "18-24": 22.0, "45-54": 15.0, "55+": 10.0},
                    "total": 100,
                }),
                "itext": None,
            },
            {
                "p": project_id,
                "j": analytics_job_run_id,
                "atype": "distribution_numeric",
                "qkey": "q_nps",
                "rdata": json.dumps({
                    "mean": 6.8, "median": 7.0, "std": 2.1,
                    "min": 0.0, "max": 10.0, "p25": 5.0, "p75": 9.0, "count": 100,
                }),
                "itext": None,
            },
            {
                "p": project_id,
                "j": analytics_job_run_id,
                "atype": "top_driver",
                "qkey": "target:q_nps|driver:q_age",
                "rdata": json.dumps({"variable": "q_age", "target": "q_nps", "effect_size": 0.34, "method": "cramers_v"}),
                "itext": "q_age shows a strong association with q_nps (V=0.34).",
            },
            {
                "p": project_id,
                "j": analytics_job_run_id,
                "atype": "segment_insight",
                "qkey": "q_age=25-34|q_nps",
                "rdata": json.dumps({"segment_var": "q_age", "segment_value": "25-34", "outcome_var": "q_nps", "segment_mean": 7.8, "overall_mean": 6.8}),
                "itext": "Users in 25-34 have higher q_nps (7.8 vs 6.8 overall, difference: 1.0).",
            },
        ]

        for ar in analytics_rows:
            conn.execute(
                text(
                    "INSERT INTO analytics_results (project_id, job_run_id, analysis_type, question_key, result_data, insight_text) "
                    "VALUES (:p, :j, :atype, :qkey, cast(:rdata as jsonb), :itext)"
                ),
                ar,
            )
        conn.commit()
        logger.info("Inserted %d analytics_results rows", len(analytics_rows))

    logger.info(
        "Seed complete. Login: %s / %s  Project id=%s",
        DEMO_EMAIL, DEMO_PASSWORD, project_id,
    )


if __name__ == "__main__":
    main()
