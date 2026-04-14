"""
Crosstab and driver analysis functions.
"""
import logging
import math

logger = logging.getLogger(__name__)


def compute_crosstab(df, row_var: str, col_var: str) -> dict:
    """
    Build a contingency table (crosstab) and compute chi-square p-value.
    Returns: {row_var, col_var, table: {row_val: {col_val: count}}, p_value, chi2, dof}
    """
    import pandas as pd

    if row_var not in df.columns or col_var not in df.columns:
        logger.warning("crosstab: missing column(s) %s %s", row_var, col_var)
        return {
            "row_var": row_var,
            "col_var": col_var,
            "table": {},
            "p_value": None,
            "chi2": None,
            "dof": None,
        }

    sub = df[[row_var, col_var]].dropna()
    if len(sub) < 5:
        return {
            "row_var": row_var,
            "col_var": col_var,
            "table": {},
            "p_value": None,
            "chi2": None,
            "dof": None,
        }

    try:
        ct = pd.crosstab(sub[row_var], sub[col_var])
        # Convert to nested dict
        table = {}
        for row_val in ct.index:
            table[str(row_val)] = {}
            for col_val in ct.columns:
                table[str(row_val)][str(col_val)] = int(ct.loc[row_val, col_val])

        # Chi-square test
        from scipy.stats import chi2_contingency
        chi2_stat, p_value, dof, expected = chi2_contingency(ct)

        return {
            "row_var": row_var,
            "col_var": col_var,
            "table": table,
            "p_value": round(float(p_value), 6),
            "chi2": round(float(chi2_stat), 4),
            "dof": int(dof),
        }

    except Exception as exc:
        logger.warning("compute_crosstab error: %s", exc)
        return {
            "row_var": row_var,
            "col_var": col_var,
            "table": {},
            "p_value": None,
            "chi2": None,
            "dof": None,
        }


def _cramers_v(confusion_matrix) -> float:
    """Compute Cramer's V from a contingency table array."""
    import numpy as np
    n = confusion_matrix.sum()
    if n == 0:
        return 0.0
    phi2 = (confusion_matrix ** 2 / confusion_matrix.sum(axis=1)[:, np.newaxis]).sum() / n - 1
    # Standard Cramer's V
    r, k = confusion_matrix.shape
    phi2_corr = max(0.0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    r_corr = r - (r - 1) ** 2 / (n - 1)
    k_corr = k - (k - 1) ** 2 / (n - 1)
    denom = min(k_corr - 1, r_corr - 1)
    if denom <= 0:
        return 0.0
    return float(math.sqrt(phi2_corr / denom))


def find_top_drivers(df, target: str, candidates: list) -> list:
    """
    For each candidate column, compute Cramer's V (for categorical) or
    Pearson correlation (for numeric) against the target column.
    Returns list of dicts sorted by effect_size descending.
    """
    import pandas as pd
    import numpy as np
    from scipy.stats import chi2_contingency, pearsonr

    if target not in df.columns:
        logger.warning("find_top_drivers: target column %s not found", target)
        return []

    results = []
    target_series = df[target].dropna()

    for cand in candidates:
        if cand not in df.columns or cand == target:
            continue
        try:
            sub = df[[cand, target]].dropna()
            if len(sub) < 5:
                continue

            cand_series = sub[cand]
            target_sub = sub[target]

            # Try numeric correlation first
            effect_size = 0.0
            method = "unknown"
            try:
                cand_num = pd.to_numeric(cand_series, errors="raise")
                target_num = pd.to_numeric(target_sub, errors="raise")
                corr, _ = pearsonr(cand_num, target_num)
                effect_size = abs(float(corr))
                method = "pearson_r"
            except Exception:
                # Fall back to Cramer's V
                try:
                    ct = pd.crosstab(cand_series.astype(str), target_sub.astype(str))
                    if ct.shape[0] < 2 or ct.shape[1] < 2:
                        continue
                    v = _cramers_v(ct.values)
                    effect_size = v
                    method = "cramers_v"
                except Exception:
                    continue

            results.append({
                "variable": cand,
                "target": target,
                "effect_size": round(effect_size, 4),
                "method": method,
            })
        except Exception as exc:
            logger.warning("find_top_drivers error for %s vs %s: %s", cand, target, exc)
            continue

    results.sort(key=lambda x: x["effect_size"], reverse=True)
    return results
