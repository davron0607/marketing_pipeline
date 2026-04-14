"""
Pure-function fraud feature engineering module.
All functions are stateless and testable independently.
"""
import hashlib
import math
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def compute_duration_sec(response: dict) -> float:
    """
    Compute survey duration in seconds using start_time/end_time fields.
    Returns -1.0 if the fields are absent or cannot be parsed.
    """
    start_raw = response.get("start_time") or response.get("starttime") or response.get("start")
    end_raw = response.get("end_time") or response.get("endtime") or response.get("end")
    if start_raw is None or end_raw is None:
        return -1.0
    try:
        from dateutil import parser as dtparser
        start_dt = dtparser.parse(str(start_raw))
        end_dt = dtparser.parse(str(end_raw))
        duration = (end_dt - start_dt).total_seconds()
        return float(duration) if duration >= 0 else -1.0
    except Exception:
        pass
    # Try numeric directly
    try:
        return float(end_raw) - float(start_raw)
    except Exception:
        return -1.0


def compute_completion_speed_zscore(duration_sec: float, all_durations: list) -> float:
    """
    Z-score of this response's duration among all valid durations in the batch.
    Returns 0.0 if fewer than 2 valid durations or duration is -1.
    """
    if duration_sec < 0:
        return 0.0
    valid = [d for d in all_durations if d >= 0]
    if len(valid) < 2:
        return 0.0
    n = len(valid)
    mean = sum(valid) / n
    variance = sum((x - mean) ** 2 for x in valid) / n
    std = math.sqrt(variance)
    if std == 0.0:
        return 0.0
    return (duration_sec - mean) / std


def compute_straightline_ratio(normalized_data: dict, matrix_prefix: str = "q_") -> float:
    """
    For columns starting with matrix_prefix, compute fraction of identical answers.
    Returns 0.0 if fewer than 2 matrix questions are found.
    """
    matrix_values = [
        v for k, v in normalized_data.items()
        if k.startswith(matrix_prefix) and v is not None and str(v).strip() != ""
    ]
    if len(matrix_values) < 2:
        return 0.0
    first = str(matrix_values[0])
    identical_count = sum(1 for v in matrix_values if str(v) == first)
    return identical_count / len(matrix_values)


def compute_answer_entropy(normalized_data: dict) -> float:
    """
    Shannon entropy of the answer values (excluding open-text fields).
    Higher entropy means more varied answers (less suspicious).
    Returns 0.0 if no values found.
    """
    text_suffixes = ("_text", "_comment", "_other", "_open")
    values = [
        str(v).strip()
        for k, v in normalized_data.items()
        if v is not None
        and str(v).strip() != ""
        and not any(k.endswith(s) for s in text_suffixes)
    ]
    if not values:
        return 0.0
    freq: dict[str, int] = {}
    for val in values:
        freq[val] = freq.get(val, 0) + 1
    total = len(values)
    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def compute_longstring_max(normalized_data: dict) -> int:
    """
    Maximum number of consecutive identical answers in the ordered sequence of values.
    Only considers non-null, non-empty values.
    Returns 0 if fewer than 2 answers.
    """
    values = [
        str(v).strip()
        for v in normalized_data.values()
        if v is not None and str(v).strip() != ""
    ]
    if len(values) < 2:
        return len(values)
    max_run = 1
    current_run = 1
    for i in range(1, len(values)):
        if values[i] == values[i - 1]:
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 1
    return max_run


def compute_duplicate_answer_vector_hash(normalized_data: dict) -> str:
    """
    MD5 hash of the sorted values list.
    Identical hash across respondents indicates identical answer patterns.
    """
    values = sorted(
        str(v) if v is not None else ""
        for v in normalized_data.values()
    )
    vector_str = "|".join(values)
    return hashlib.md5(vector_str.encode("utf-8")).hexdigest()


def compute_open_text_length_mean(
    normalized_data: dict,
    text_suffixes: tuple = ("_text", "_comment", "_other", "_open"),
) -> float:
    """
    Mean character length of open-text fields.
    Returns 0.0 if no text fields found.
    """
    text_values = [
        str(v)
        for k, v in normalized_data.items()
        if any(k.endswith(s) for s in text_suffixes) and v is not None
    ]
    if not text_values:
        return 0.0
    return sum(len(v) for v in text_values) / len(text_values)


def compute_open_text_uniqueness_score(text: str, all_texts: list) -> float:
    """
    Ratio of how many other responses share this exact text.
    Returns 0.0 if this text is unique; 1.0 if all responses have the same text.
    """
    if not all_texts:
        return 0.0
    match_count = sum(1 for t in all_texts if t == text)
    return match_count / len(all_texts)


def compute_attention_fail_count(
    normalized_data: dict,
    attention_keys: list,
    expected_values: dict,
) -> int:
    """
    Count how many attention-check questions have wrong answers.
    attention_keys: list of column names to check
    expected_values: dict mapping column name -> expected value
    """
    fail_count = 0
    for key in attention_keys:
        actual = normalized_data.get(key)
        expected = expected_values.get(key)
        if expected is not None and actual is not None:
            if str(actual).strip().lower() != str(expected).strip().lower():
                fail_count += 1
        elif expected is not None and actual is None:
            fail_count += 1
    return fail_count


def compute_contradiction_count(
    normalized_data: dict,
    contradiction_rules: list,
) -> int:
    """
    Count violated contradiction rules.
    Each rule: {"if_key": k, "if_value": v, "then_key": k2, "must_be": v2}
    """
    count = 0
    for rule in contradiction_rules:
        if_key = rule.get("if_key")
        if_value = rule.get("if_value")
        then_key = rule.get("then_key")
        must_be = rule.get("must_be")
        if if_key is None or then_key is None:
            continue
        actual_if = normalized_data.get(if_key)
        if actual_if is None:
            continue
        if str(actual_if).strip().lower() == str(if_value).strip().lower():
            actual_then = normalized_data.get(then_key)
            if actual_then is None:
                count += 1
            elif str(actual_then).strip().lower() != str(must_be).strip().lower():
                count += 1
    return count


def compute_device_submission_count_24h(
    device_id: str,
    project_id: int,
    db_session,
) -> int:
    """
    Count submissions from the same device_id in the last 24 hours.
    Looks in survey_responses.normalized_data->>'device_id'.
    """
    if not device_id:
        return 0
    from sqlalchemy import text
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = db_session.execute(
        text(
            "SELECT COUNT(*) FROM survey_responses "
            "WHERE project_id=:p "
            "AND normalized_data->>'device_id' = :d "
            "AND created_at >= :c"
        ),
        {"p": project_id, "d": str(device_id), "c": cutoff},
    )
    row = result.fetchone()
    return int(row[0]) if row else 0


def compute_ip_submission_count_24h(
    ip_address: str,
    project_id: int,
    db_session,
) -> int:
    """
    Count submissions from the same IP address in the last 24 hours.
    Looks in survey_responses.normalized_data->>'ip_address'.
    """
    if not ip_address:
        return 0
    from sqlalchemy import text
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    result = db_session.execute(
        text(
            "SELECT COUNT(*) FROM survey_responses "
            "WHERE project_id=:p "
            "AND normalized_data->>'ip_address' = :ip "
            "AND created_at >= :c"
        ),
        {"p": project_id, "ip": str(ip_address), "c": cutoff},
    )
    row = result.fetchone()
    return int(row[0]) if row else 0


def compute_missingness_ratio(normalized_data: dict) -> float:
    """
    Fraction of fields that are null or empty string.
    Returns 0.0 if the response dict is empty.
    """
    if not normalized_data:
        return 0.0
    total = len(normalized_data)
    missing = sum(
        1 for v in normalized_data.values()
        if v is None or str(v).strip() == ""
    )
    return missing / total
