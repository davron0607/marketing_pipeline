"""
Template-based insight text generators.
Pure functions, no ML.
"""


def generate_sample_quality_insight(
    total: int,
    valid: int,
    review: int,
    reject: int,
) -> str:
    """
    Returns a human-readable sentence about sample quality.
    """
    usable = valid + review
    if total == 0:
        return "No survey responses have been processed yet."
    reject_pct = round(reject / total * 100, 1)
    return (
        f"After fraud cleanup, usable sample size is {usable:,} from {total:,} submissions "
        f"({reject_pct}% rejected as likely fraudulent)."
    )


def generate_segment_insight(
    segment_var: str,
    segment_value: str,
    outcome_var: str,
    outcome_mean: float,
    overall_mean: float,
) -> str:
    """
    Returns a human-readable sentence comparing a segment to the overall mean.
    """
    direction = "higher" if outcome_mean > overall_mean else "lower"
    diff = abs(outcome_mean - overall_mean)
    return (
        f"Users in {segment_value} have {direction} {outcome_var} "
        f"({outcome_mean:.1f} vs {overall_mean:.1f} overall, "
        f"difference: {diff:.1f})."
    )


def generate_driver_insight(
    driver_var: str,
    target_var: str,
    effect_size: float,
) -> str:
    """
    Returns a human-readable sentence about the strength of an association.
    """
    strength = "strong" if effect_size > 0.3 else "moderate"
    return (
        f"{driver_var} shows a {strength} association with {target_var} "
        f"(V={effect_size:.2f})."
    )
