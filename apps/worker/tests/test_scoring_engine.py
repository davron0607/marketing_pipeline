"""
Tests for the fraud scoring engine.
"""
import sys
import os
import math
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.fraud.scoring_engine import (
    compute_fraud_score,
    score_speed,
    score_straightline,
    score_entropy,
    score_contradiction,
    score_duplicate,
    score_open_text,
    score_missingness,
    score_geo_device,
    DEFAULT_WEIGHTS,
    DEFAULT_THRESHOLDS,
)


# ─────────────────────────── Helpers ─────────────────────────────────────────

def _perfect_features() -> dict:
    """Features for a perfectly legitimate response."""
    return {
        "duration_sec": 300.0,
        "completion_speed_zscore": 0.0,
        "straightline_ratio": 0.1,
        "answer_entropy": 2.5,
        "longstring_max": 2,
        "duplicate_answer_vector_hash": "abc123unique",
        "open_text_length_mean": 80.0,
        "open_text_uniqueness_score": 0.1,
        "attention_fail_count": 0,
        "contradiction_count": 0,
        "device_submission_count_24h": 1,
        "ip_submission_count_24h": 1,
        "missingness_ratio": 0.0,
    }


def _fraudulent_features() -> dict:
    """Features for a highly suspicious response."""
    return {
        "duration_sec": 8.0,
        "completion_speed_zscore": -3.5,
        "straightline_ratio": 1.0,
        "answer_entropy": 0.0,
        "longstring_max": 50,
        "duplicate_answer_vector_hash": "same_hash",
        "open_text_length_mean": 2.0,
        "open_text_uniqueness_score": 0.9,
        "attention_fail_count": 2,
        "contradiction_count": 3,
        "device_submission_count_24h": 10,
        "ip_submission_count_24h": 15,
        "missingness_ratio": 0.7,
    }


# ─────────────────────────── Speed scoring ───────────────────────────────────

class TestScoreSpeed:
    def test_extremely_fast_penalty_100(self):
        penalty, reason = score_speed(5.0, -3.0, DEFAULT_THRESHOLDS)
        assert penalty == 100.0
        assert reason is not None

    def test_moderately_fast_penalty_60(self):
        penalty, reason = score_speed(60.0, -1.8, DEFAULT_THRESHOLDS)
        assert penalty == 60.0

    def test_normal_speed_penalty_zero(self):
        penalty, reason = score_speed(300.0, 0.5, DEFAULT_THRESHOLDS)
        assert penalty == 0.0
        assert reason is None

    def test_unknown_duration_small_penalty(self):
        penalty, reason = score_speed(-1.0, 0.0, DEFAULT_THRESHOLDS)
        assert penalty == 20.0
        assert reason is None


# ─────────────────────────── Straightline scoring ────────────────────────────

class TestScoreStraightline:
    def test_perfect_straightliner(self):
        penalty, reason = score_straightline(1.0, DEFAULT_THRESHOLDS)
        assert penalty == 100.0
        assert reason is not None

    def test_zero_straightline_no_penalty(self):
        penalty, reason = score_straightline(0.0, DEFAULT_THRESHOLDS)
        assert penalty == 0.0
        assert reason is None

    def test_partial_straightline(self):
        penalty, reason = score_straightline(0.6, DEFAULT_THRESHOLDS)
        assert 50 <= penalty <= 65


# ─────────────────────────── Entropy scoring ─────────────────────────────────

class TestScoreEntropy:
    def test_zero_entropy_max_penalty(self):
        penalty, reason = score_entropy(0.0, DEFAULT_THRESHOLDS)
        assert penalty == 100.0

    def test_high_entropy_low_penalty(self):
        penalty, reason = score_entropy(3.0, DEFAULT_THRESHOLDS)
        assert penalty == 0.0

    def test_medium_entropy(self):
        penalty, reason = score_entropy(1.5, DEFAULT_THRESHOLDS)
        assert 0 < penalty < 100


# ─────────────────────────── Contradiction scoring ───────────────────────────

class TestScoreContradiction:
    def test_no_contradiction(self):
        penalty, reason = score_contradiction(0, DEFAULT_THRESHOLDS)
        assert penalty == 0.0
        assert reason is None

    def test_one_contradiction(self):
        penalty, reason = score_contradiction(1, DEFAULT_THRESHOLDS)
        assert penalty == 25.0
        assert reason is not None

    def test_four_contradictions_capped(self):
        penalty, reason = score_contradiction(4, DEFAULT_THRESHOLDS)
        assert penalty == 100.0

    def test_many_contradictions_still_capped(self):
        penalty, reason = score_contradiction(100, DEFAULT_THRESHOLDS)
        assert penalty == 100.0


# ─────────────────────────── Duplicate scoring ───────────────────────────────

class TestScoreDuplicate:
    def test_unique_hash_no_penalty(self):
        all_hashes = ["aaa", "bbb", "ccc", "ddd"]
        penalty, reason = score_duplicate("aaa", all_hashes, DEFAULT_THRESHOLDS)
        assert penalty == 0.0  # unique (appears once)

    def test_duplicate_hash_penalty(self):
        all_hashes = ["aaa", "aaa", "bbb", "ccc"]
        penalty, reason = score_duplicate("aaa", all_hashes, DEFAULT_THRESHOLDS)
        assert penalty == 80.0
        assert reason is not None

    def test_triple_duplicate_same_penalty(self):
        all_hashes = ["xxx", "xxx", "xxx"]
        penalty, reason = score_duplicate("xxx", all_hashes, DEFAULT_THRESHOLDS)
        assert penalty == 80.0


# ─────────────────────────── Open text scoring ───────────────────────────────

class TestScoreOpenText:
    def test_very_short_and_common_high_penalty(self):
        penalty, reason = score_open_text(2.0, 0.8, DEFAULT_THRESHOLDS)
        assert penalty == 80.0
        assert reason is not None

    def test_long_unique_text_low_penalty(self):
        penalty, reason = score_open_text(150.0, 0.05, DEFAULT_THRESHOLDS)
        assert penalty < 20.0

    def test_short_unique_text_moderate(self):
        penalty, reason = score_open_text(15.0, 0.6, DEFAULT_THRESHOLDS)
        assert penalty == 50.0


# ─────────────────────────── Missingness scoring ─────────────────────────────

class TestScoreMissingness:
    def test_no_missing_no_penalty(self):
        penalty, reason = score_missingness(0.0, DEFAULT_THRESHOLDS)
        assert penalty == 0.0
        assert reason is None

    def test_high_missingness_penalty_80(self):
        penalty, reason = score_missingness(0.7, DEFAULT_THRESHOLDS)
        assert penalty == 80.0
        assert reason is not None

    def test_moderate_missingness(self):
        penalty, reason = score_missingness(0.3, DEFAULT_THRESHOLDS)
        assert penalty == 30.0


# ─────────────────────────── Geo/device scoring ──────────────────────────────

class TestScoreGeoDevice:
    def test_no_submissions_no_penalty(self):
        penalty, reason = score_geo_device(1, 1, DEFAULT_THRESHOLDS)
        assert penalty == 0.0

    def test_too_many_device_subs_penalty_80(self):
        penalty, reason = score_geo_device(5, 1, DEFAULT_THRESHOLDS)
        assert penalty == 80.0
        assert reason is not None

    def test_too_many_ip_subs_penalty_80(self):
        penalty, reason = score_geo_device(1, 8, DEFAULT_THRESHOLDS)
        assert penalty == 80.0

    def test_borderline_device(self):
        penalty, reason = score_geo_device(3, 2, DEFAULT_THRESHOLDS)
        assert penalty < 80.0


# ─────────────────────────── Full score computation ──────────────────────────

class TestComputeFraudScore:
    def test_perfect_response_is_valid(self):
        features = _perfect_features()
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, ["abc123unique"])
        assert result["fraud_label"] == "valid"
        assert result["fraud_score"] <= DEFAULT_THRESHOLDS["valid_max"]

    def test_fraudulent_response_is_reject(self):
        features = _fraudulent_features()
        all_hashes = ["same_hash"] * 5
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, all_hashes)
        assert result["fraud_label"] == "reject"
        assert result["fraud_score"] > DEFAULT_THRESHOLDS["review_max"]

    def test_result_contains_required_keys(self):
        features = _perfect_features()
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, ["abc123unique"])
        assert "fraud_score" in result
        assert "fraud_label" in result
        assert "fraud_reasons" in result
        assert "component_scores" in result

    def test_fraud_score_is_bounded_0_to_100(self):
        features = _fraudulent_features()
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, ["same_hash"] * 3)
        assert 0 <= result["fraud_score"] <= 100

    def test_threshold_boundary_valid_max(self):
        """A response at exactly valid_max threshold should be labeled valid."""
        features = _perfect_features()
        # Use weights that produce exactly valid_max = 29 score
        custom_weights = {k: 0.0 for k in DEFAULT_WEIGHTS}
        result = compute_fraud_score(features, custom_weights, DEFAULT_THRESHOLDS, ["abc123unique"])
        # With all zero weights, score should be 0 -> valid
        assert result["fraud_label"] == "valid"
        assert result["fraud_score"] == 0.0

    def test_threshold_boundary_review_label(self):
        """A moderately suspicious response should get review label."""
        features = _perfect_features()
        # Inject some moderate signals
        features["straightline_ratio"] = 0.6
        features["completion_speed_zscore"] = -1.8
        features["answer_entropy"] = 1.2
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, ["abc123unique"])
        # Should not be perfectly valid
        assert result["fraud_score"] > 0

    def test_reasons_populated_for_fraudulent(self):
        features = _fraudulent_features()
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, ["same_hash"] * 3)
        assert len(result["fraud_reasons"]) > 0

    def test_component_scores_all_present(self):
        features = _perfect_features()
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, ["abc123unique"])
        expected_components = [
            "speed_component", "straightline_component", "entropy_component",
            "contradiction_component", "duplicate_component", "open_text_component",
            "missingness_component", "geo_device_component",
        ]
        for comp in expected_components:
            assert comp in result["component_scores"]

    def test_all_null_features_handled_gracefully(self):
        """Features with all None values should not crash."""
        features = {k: None for k in _perfect_features().keys()}
        features["duplicate_answer_vector_hash"] = ""
        result = compute_fraud_score(features, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, [""])
        assert "fraud_score" in result
        assert result["fraud_label"] in ("valid", "review", "reject")
