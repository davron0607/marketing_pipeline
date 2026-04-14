"""
Fraud scoring engine: pure functions that compute per-response fraud scores.
"""
import logging
import math

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = {
    "speed_component": 0.20,
    "straightline_component": 0.20,
    "entropy_component": 0.15,
    "contradiction_component": 0.10,
    "duplicate_component": 0.15,
    "open_text_component": 0.10,
    "missingness_component": 0.05,
    "geo_device_component": 0.05,
}

DEFAULT_THRESHOLDS = {"valid_max": 29, "review_max": 59}


def score_speed(duration_sec: float, zscore: float, thresholds: dict) -> tuple:
    """
    Penalize very fast responses.
    - If duration_sec >= 0 and zscore < -2.0: penalty 100 (extremely fast)
    - If duration_sec >= 0 and -2.0 <= zscore < -1.5: penalty 60
    - If duration_sec >= 0 and zscore >= -1.5: penalty 0
    - If duration_sec < 0 (unknown): penalty 20 (slight default suspicion)
    Returns (raw_penalty_0_to_100, reason_string_or_None)
    """
    if duration_sec < 0:
        return (20.0, None)
    if zscore < -2.0:
        reason = f"Completion speed extremely fast (z={zscore:.2f})"
        return (100.0, reason)
    if zscore < -1.5:
        reason = f"Completion speed fast (z={zscore:.2f})"
        return (60.0, reason)
    return (0.0, None)


def score_straightline(ratio: float, thresholds: dict) -> tuple:
    """
    Penalty proportional to straightline ratio.
    penalty = ratio * 100
    Returns (penalty, reason_or_None)
    """
    penalty = max(0.0, min(100.0, ratio * 100.0))
    reason = None
    if ratio >= 0.8:
        reason = f"Straightlining detected ({ratio:.0%} identical matrix answers)"
    elif ratio >= 0.5:
        reason = f"Possible straightlining ({ratio:.0%} identical matrix answers)"
    return (penalty, reason)


def score_entropy(entropy: float, thresholds: dict) -> tuple:
    """
    Low entropy is suspicious; penalty = max(0, (1 - entropy/3) * 100).
    Returns (penalty, reason_or_None)
    """
    penalty = max(0.0, (1.0 - entropy / 3.0) * 100.0)
    penalty = min(100.0, penalty)
    reason = None
    if entropy < 0.5:
        reason = f"Very low answer diversity (entropy={entropy:.2f})"
    elif entropy < 1.0:
        reason = f"Low answer diversity (entropy={entropy:.2f})"
    return (penalty, reason)


def score_contradiction(count: int, thresholds: dict) -> tuple:
    """
    Each contradiction adds 25 points, capped at 100.
    Returns (penalty, reason_or_None)
    """
    penalty = min(100.0, count * 25.0)
    reason = f"{count} logical contradiction(s) detected" if count > 0 else None
    return (penalty, reason)


def score_duplicate(hash_val: str, all_hashes: list, thresholds: dict) -> tuple:
    """
    If this hash appears more than once in the batch: penalty 80, else 0.
    Returns (penalty, reason_or_None)
    """
    count = all_hashes.count(hash_val)
    if count > 1:
        reason = f"Identical answer pattern shared with {count - 1} other respondent(s)"
        return (80.0, reason)
    return (0.0, None)


def score_open_text(length_mean: float, uniqueness_score: float, thresholds: dict) -> tuple:
    """
    Very short text AND low uniqueness = suspicious.
    - length_mean < 5 and uniqueness_score > 0.3: penalty 80
    - length_mean < 20 and uniqueness_score > 0.5: penalty 50
    - Otherwise: penalty = max(0, (1 - length_mean / 50) * uniqueness_score * 60)
    Returns (penalty, reason_or_None)
    """
    reason = None
    if length_mean < 5 and uniqueness_score > 0.3:
        reason = "Very short or duplicate open-text responses"
        return (80.0, reason)
    if length_mean < 20 and uniqueness_score > 0.5:
        reason = "Short and non-unique open-text responses"
        return (50.0, reason)
    penalty = max(0.0, (1.0 - length_mean / 50.0) * uniqueness_score * 60.0)
    penalty = min(100.0, penalty)
    return (penalty, reason)


def score_missingness(ratio: float, thresholds: dict) -> tuple:
    """
    - ratio > 0.5: penalty 80
    - Otherwise: penalty = ratio * 100
    Returns (penalty, reason_or_None)
    """
    if ratio > 0.5:
        reason = f"High missingness ratio ({ratio:.0%} fields empty)"
        return (80.0, reason)
    penalty = min(100.0, ratio * 100.0)
    reason = None
    if ratio > 0.3:
        reason = f"Moderate missingness ({ratio:.0%} fields empty)"
    return (penalty, reason)


def score_geo_device(device_count: int, ip_count: int, thresholds: dict) -> tuple:
    """
    device_count > 3 or ip_count > 5: penalty 80, else scaled.
    Returns (penalty, reason_or_None)
    """
    reason = None
    if device_count > 3 or ip_count > 5:
        parts = []
        if device_count > 3:
            parts.append(f"device seen {device_count}x in 24h")
        if ip_count > 5:
            parts.append(f"IP seen {ip_count}x in 24h")
        reason = "High submission rate: " + ", ".join(parts)
        return (80.0, reason)
    # Scaled penalty
    device_penalty = min(80.0, device_count * 20.0)
    ip_penalty = min(80.0, ip_count * 12.0)
    penalty = max(device_penalty, ip_penalty)
    return (penalty, None)


def compute_fraud_score(
    features: dict,
    weights: dict,
    thresholds: dict,
    all_hashes: list,
) -> dict:
    """
    Compute the final fraud score for one response.

    features: dict with all feature values (as stored in response_features).
    weights: per-component weights (should sum to ~1.0).
    thresholds: {"valid_max": int, "review_max": int}
    all_hashes: list of all duplicate_answer_vector_hash values in the batch.

    Returns: {fraud_score, fraud_label, fraud_reasons, component_scores}
    """
    duration_sec = features.get("duration_sec") if features.get("duration_sec") is not None else -1.0
    zscore = features.get("completion_speed_zscore") or 0.0
    straightline = features.get("straightline_ratio") or 0.0
    entropy = features.get("answer_entropy") or 0.0
    contradiction = features.get("contradiction_count") or 0
    dup_hash = features.get("duplicate_answer_vector_hash") or ""
    open_text_mean = features.get("open_text_length_mean") or 0.0
    uniqueness = features.get("open_text_uniqueness_score") or 0.0
    missingness = features.get("missingness_ratio") or 0.0
    device_count = features.get("device_submission_count_24h") or 0
    ip_count = features.get("ip_submission_count_24h") or 0

    # Score each component
    speed_raw, speed_reason = score_speed(duration_sec, zscore, thresholds)
    straight_raw, straight_reason = score_straightline(straightline, thresholds)
    entropy_raw, entropy_reason = score_entropy(entropy, thresholds)
    contradiction_raw, contradiction_reason = score_contradiction(contradiction, thresholds)
    duplicate_raw, duplicate_reason = score_duplicate(dup_hash, all_hashes, thresholds)
    open_text_raw, open_text_reason = score_open_text(open_text_mean, uniqueness, thresholds)
    missingness_raw, missingness_reason = score_missingness(missingness, thresholds)
    geo_device_raw, geo_device_reason = score_geo_device(device_count, ip_count, thresholds)

    component_scores = {
        "speed_component": speed_raw,
        "straightline_component": straight_raw,
        "entropy_component": entropy_raw,
        "contradiction_component": contradiction_raw,
        "duplicate_component": duplicate_raw,
        "open_text_component": open_text_raw,
        "missingness_component": missingness_raw,
        "geo_device_component": geo_device_raw,
    }

    # Weighted sum
    fraud_score = 0.0
    for component_name, raw_penalty in component_scores.items():
        weight = weights.get(component_name, DEFAULT_WEIGHTS.get(component_name, 0.0))
        fraud_score += weight * raw_penalty

    fraud_score = min(100.0, max(0.0, fraud_score))

    # Label
    valid_max = thresholds.get("valid_max", 29)
    review_max = thresholds.get("review_max", 59)
    if fraud_score <= valid_max:
        fraud_label = "valid"
    elif fraud_score <= review_max:
        fraud_label = "review"
    else:
        fraud_label = "reject"

    # Collect reasons (non-None)
    fraud_reasons = [
        r for r in [
            speed_reason,
            straight_reason,
            entropy_reason,
            contradiction_reason,
            duplicate_reason,
            open_text_reason,
            missingness_reason,
            geo_device_reason,
        ]
        if r is not None
    ]

    return {
        "fraud_score": round(fraud_score, 4),
        "fraud_label": fraud_label,
        "fraud_reasons": fraud_reasons,
        "component_scores": {k: round(v, 4) for k, v in component_scores.items()},
    }
