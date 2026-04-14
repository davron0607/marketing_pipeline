"""
Distribution computation functions for survey analytics.
All functions are pure, stateless, and independently testable.
"""
import math
import logging

logger = logging.getLogger(__name__)


def compute_single_choice_distribution(values: list) -> dict:
    """
    Compute value counts and percentages for a single-choice column.
    Returns {"counts": {value: count, ...}, "percentages": {value: pct, ...}, "total": N}
    """
    if not values:
        return {"counts": {}, "percentages": {}, "total": 0}

    freq: dict[str, int] = {}
    total = 0
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        key = str(v).strip()
        freq[key] = freq.get(key, 0) + 1
        total += 1

    if total == 0:
        return {"counts": {}, "percentages": {}, "total": 0}

    percentages = {k: round(count / total * 100, 2) for k, count in freq.items()}
    # Sort by count descending
    sorted_counts = dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))
    sorted_pcts = {k: percentages[k] for k in sorted_counts}

    return {"counts": sorted_counts, "percentages": sorted_pcts, "total": total}


def compute_numeric_stats(values: list) -> dict:
    """
    Compute descriptive statistics for a numeric column.
    Returns {mean, median, std, min, max, p25, p75, count}
    """
    clean = []
    for v in values:
        if v is None:
            continue
        try:
            fv = float(v)
            if not math.isnan(fv) and not math.isinf(fv):
                clean.append(fv)
        except (ValueError, TypeError):
            continue

    if not clean:
        return {"mean": None, "median": None, "std": None, "min": None, "max": None,
                "p25": None, "p75": None, "count": 0}

    n = len(clean)
    clean_sorted = sorted(clean)
    mean_val = sum(clean_sorted) / n
    variance = sum((x - mean_val) ** 2 for x in clean_sorted) / n
    std_val = math.sqrt(variance)

    def percentile(sorted_data: list, p: float) -> float:
        idx = (len(sorted_data) - 1) * p / 100.0
        lo = int(idx)
        hi = lo + 1
        if hi >= len(sorted_data):
            return sorted_data[lo]
        frac = idx - lo
        return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac

    median_val = percentile(clean_sorted, 50)
    p25 = percentile(clean_sorted, 25)
    p75 = percentile(clean_sorted, 75)

    return {
        "mean": round(mean_val, 4),
        "median": round(median_val, 4),
        "std": round(std_val, 4),
        "min": round(clean_sorted[0], 4),
        "max": round(clean_sorted[-1], 4),
        "p25": round(p25, 4),
        "p75": round(p75, 4),
        "count": n,
    }


def compute_multi_choice_distribution(values: list) -> dict:
    """
    Flatten multi-select values and count each option.
    Each element in values can be a list or a comma-separated string.
    Returns {"counts": {option: count, ...}, "percentages": {option: pct, ...}, "total_responses": N}
    """
    if not values:
        return {"counts": {}, "percentages": {}, "total_responses": 0}

    freq: dict[str, int] = {}
    total_responses = 0

    for item in values:
        if item is None:
            continue
        if isinstance(item, list):
            options = [str(o).strip() for o in item if o is not None]
        elif isinstance(item, str):
            options = [o.strip() for o in item.split(",") if o.strip()]
        else:
            options = [str(item).strip()]

        if options:
            total_responses += 1
        for opt in options:
            freq[opt] = freq.get(opt, 0) + 1

    if total_responses == 0:
        return {"counts": {}, "percentages": {}, "total_responses": 0}

    percentages = {k: round(v / total_responses * 100, 2) for k, v in freq.items()}
    sorted_counts = dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))
    sorted_pcts = {k: percentages[k] for k in sorted_counts}

    return {"counts": sorted_counts, "percentages": sorted_pcts, "total_responses": total_responses}


def compute_text_summary(values: list) -> dict:
    """
    Summarize open-text field values.
    Returns: {count, avg_length, top_words: [{word: str, count: int}, ...]}
    """
    non_empty = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not non_empty:
        return {"count": 0, "avg_length": 0.0, "top_words": []}

    count = len(non_empty)
    avg_length = sum(len(s) for s in non_empty) / count

    # Simple word frequency (no ML, no stopwords removal — keep it simple)
    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "i", "is", "it", "this", "that", "was", "are", "be",
        "have", "had", "has", "not", "as", "do", "did", "will", "would",
        "my", "me", "we", "our", "you", "your", "they", "their", "them",
    }
    word_freq: dict[str, int] = {}
    import re
    for text in non_empty:
        words = re.findall(r"\b[a-z]{2,}\b", text.lower())
        for word in words:
            if word not in STOP_WORDS:
                word_freq[word] = word_freq.get(word, 0) + 1

    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]
    top_words_list = [{"word": w, "count": c} for w, c in top_words]

    return {
        "count": count,
        "avg_length": round(avg_length, 2),
        "top_words": top_words_list,
    }


def detect_column_type(values: list) -> str:
    """
    Heuristically detect whether a column is:
    - "numeric": most values parseable as float
    - "text": values are long strings
    - "single_choice": few distinct values
    """
    if not values:
        return "single_choice"

    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return "single_choice"

    # Try numeric
    numeric_count = 0
    for v in non_null:
        try:
            float(str(v))
            numeric_count += 1
        except (ValueError, TypeError):
            pass

    if numeric_count / len(non_null) > 0.8:
        return "numeric"

    # Check for long text
    avg_len = sum(len(str(v)) for v in non_null) / len(non_null)
    if avg_len > 40:
        return "text"

    # Few distinct values → single_choice
    distinct = len(set(str(v).strip() for v in non_null))
    if distinct <= 20 or distinct / len(non_null) < 0.3:
        return "single_choice"

    return "text"
