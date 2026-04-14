"""
Tests for fraud feature engineering functions.
Tests all pure functions with synthetic survey data.
"""
import math
import sys
import os
import pytest

# Make worker app importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
    compute_missingness_ratio,
)


# ─────────────────────────── Fixtures ────────────────────────────────────────

@pytest.fixture
def normal_response():
    """A typical normal survey response."""
    return {
        "respondent_id": "R001",
        "start_time": "2024-01-15 10:00:00",
        "end_time": "2024-01-15 10:08:30",
        "q_1": "4",
        "q_2": "3",
        "q_3": "5",
        "q_4": "2",
        "q_5": "4",
        "age": "25-34",
        "gender": "Female",
        "feedback_text": "The product is great and I really enjoy using it daily.",
    }


@pytest.fixture
def straightliner_response():
    """A straightliner: all matrix questions have the same answer."""
    return {
        "respondent_id": "R002",
        "q_1": "3",
        "q_2": "3",
        "q_3": "3",
        "q_4": "3",
        "q_5": "3",
        "age": "35-44",
        "gender": "Male",
        "feedback_text": "ok",
    }


@pytest.fixture
def all_null_response():
    """A response with all null/empty values."""
    return {
        "respondent_id": "R003",
        "q_1": None,
        "q_2": "",
        "q_3": None,
        "q_4": "",
        "age": None,
        "gender": None,
        "feedback_text": None,
    }


@pytest.fixture
def single_row_batch():
    """Batch with only one response."""
    return [120.0]


# ─────────────────────────── Duration ────────────────────────────────────────

class TestComputeDurationSec:
    def test_normal_duration(self, normal_response):
        duration = compute_duration_sec(normal_response)
        # 8 minutes 30 seconds = 510 seconds
        assert abs(duration - 510.0) < 2

    def test_missing_times(self):
        response = {"q_1": "3", "q_2": "4"}
        assert compute_duration_sec(response) == -1.0

    def test_only_start_time(self):
        response = {"start_time": "2024-01-15 10:00:00"}
        assert compute_duration_sec(response) == -1.0

    def test_zero_duration(self):
        response = {"start_time": "2024-01-15 10:00:00", "end_time": "2024-01-15 10:00:00"}
        assert compute_duration_sec(response) == 0.0

    def test_negative_duration_returns_negative(self):
        # End before start
        response = {
            "start_time": "2024-01-15 10:10:00",
            "end_time": "2024-01-15 10:00:00",
        }
        result = compute_duration_sec(response)
        assert result == -1.0


# ─────────────────────────── Speed Z-score ───────────────────────────────────

class TestComputionSpeedZscore:
    def test_single_row_returns_zero(self, single_row_batch):
        zscore = compute_completion_speed_zscore(120.0, single_row_batch)
        assert zscore == 0.0

    def test_empty_batch_returns_zero(self):
        zscore = compute_completion_speed_zscore(60.0, [])
        assert zscore == 0.0

    def test_negative_duration_returns_zero(self):
        zscore = compute_completion_speed_zscore(-1.0, [120.0, 300.0, 180.0])
        assert zscore == 0.0

    def test_average_speed_near_zero_zscore(self):
        durations = [100.0, 200.0, 300.0, 400.0, 500.0]
        mean = sum(durations) / len(durations)
        zscore = compute_completion_speed_zscore(mean, durations)
        assert abs(zscore) < 0.01

    def test_fast_respondent_negative_zscore(self):
        durations = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0]
        zscore = compute_completion_speed_zscore(10.0, durations)
        assert zscore < -1.0

    def test_all_same_duration_returns_zero(self):
        durations = [300.0, 300.0, 300.0, 300.0]
        zscore = compute_completion_speed_zscore(300.0, durations)
        assert zscore == 0.0


# ─────────────────────────── Straightline ────────────────────────────────────

class TestComputeStraightlineRatio:
    def test_perfect_straightliner(self, straightliner_response):
        ratio = compute_straightline_ratio(straightliner_response)
        assert ratio == 1.0

    def test_no_matrix_columns_returns_zero(self):
        response = {"age": "25", "gender": "M", "country": "US"}
        ratio = compute_straightline_ratio(response)
        assert ratio == 0.0

    def test_varied_answers(self, normal_response):
        ratio = compute_straightline_ratio(normal_response)
        # 5 questions: q_1=4, q_2=3, q_3=5, q_4=2, q_5=4 → "4" appears twice
        assert ratio < 1.0
        assert ratio >= 0.0

    def test_single_matrix_returns_zero(self):
        response = {"q_1": "5", "age": "30"}
        ratio = compute_straightline_ratio(response)
        assert ratio == 0.0

    def test_custom_matrix_prefix(self):
        response = {"matrix_1": "yes", "matrix_2": "yes", "matrix_3": "yes"}
        ratio = compute_straightline_ratio(response, matrix_prefix="matrix_")
        assert ratio == 1.0


# ─────────────────────────── Entropy ─────────────────────────────────────────

class TestComputeAnswerEntropy:
    def test_all_same_answers_low_entropy(self, straightliner_response):
        entropy = compute_answer_entropy(straightliner_response)
        assert entropy < 1.0

    def test_varied_answers_higher_entropy(self, normal_response):
        entropy = compute_answer_entropy(normal_response)
        assert entropy > 0.5

    def test_empty_response_returns_zero(self):
        assert compute_answer_entropy({}) == 0.0

    def test_all_null_response(self, all_null_response):
        # After filtering nulls, nothing to compute
        entropy = compute_answer_entropy(all_null_response)
        assert entropy == 0.0

    def test_binary_responses_entropy_one(self):
        response = {"q_1": "1", "q_2": "0", "q_3": "1", "q_4": "0"}
        entropy = compute_answer_entropy(response)
        # Entropy of 50/50 binary = 1.0
        assert abs(entropy - 1.0) < 0.01

    def test_text_fields_excluded(self):
        response = {
            "q_1": "1",
            "q_2": "1",
            "q_3": "1",
            "feedback_text": "long varied text with many different words",
        }
        entropy_with_exclusion = compute_answer_entropy(response)
        # Should be low because q_* are all "1"
        assert entropy_with_exclusion < 0.1


# ─────────────────────────── Longstring ──────────────────────────────────────

class TestComputeLongstringMax:
    def test_straightliner_max_equals_length(self, straightliner_response):
        longstring = compute_longstring_max(straightliner_response)
        # The 5 "3" values are consecutive (among all values including age/gender)
        assert longstring >= 5

    def test_varied_response_low_longstring(self, normal_response):
        longstring = compute_longstring_max(normal_response)
        assert longstring < 5

    def test_empty_returns_zero(self):
        assert compute_longstring_max({}) == 0

    def test_all_same_returns_total_count(self):
        response = {"a": "x", "b": "x", "c": "x", "d": "x"}
        assert compute_longstring_max(response) == 4

    def test_single_field_returns_one(self):
        response = {"q_1": "5"}
        assert compute_longstring_max(response) == 1


# ─────────────────────────── Duplicate Hash ──────────────────────────────────

class TestComputeDuplicateHash:
    def test_identical_responses_same_hash(self):
        r1 = {"q_1": "1", "q_2": "2", "q_3": "3"}
        r2 = {"q_1": "1", "q_2": "2", "q_3": "3"}
        assert compute_duplicate_answer_vector_hash(r1) == compute_duplicate_answer_vector_hash(r2)

    def test_different_responses_different_hash(self):
        r1 = {"q_1": "1", "q_2": "2", "q_3": "3"}
        r2 = {"q_1": "4", "q_2": "5", "q_3": "6"}
        assert compute_duplicate_answer_vector_hash(r1) != compute_duplicate_answer_vector_hash(r2)

    def test_hash_is_string(self):
        response = {"a": "1", "b": "2"}
        h = compute_duplicate_answer_vector_hash(response)
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest

    def test_null_values_handled(self):
        response = {"q_1": None, "q_2": "3"}
        h = compute_duplicate_answer_vector_hash(response)
        assert isinstance(h, str)


# ─────────────────────────── Open Text ───────────────────────────────────────

class TestComputeOpenTextLengthMean:
    def test_no_text_fields_returns_zero(self):
        response = {"q_1": "3", "q_2": "4"}
        assert compute_open_text_length_mean(response) == 0.0

    def test_single_text_field(self):
        response = {"q_1": "3", "feedback_text": "Hello world"}
        mean = compute_open_text_length_mean(response)
        assert mean == len("Hello world")

    def test_multiple_text_fields(self):
        response = {
            "q_1": "3",
            "feedback_text": "Hello",  # 5 chars
            "other_comment": "World!",  # 6 chars
        }
        mean = compute_open_text_length_mean(response)
        assert abs(mean - 5.5) < 0.01

    def test_null_text_field_ignored(self):
        response = {"feedback_text": None, "other_comment": "OK"}
        mean = compute_open_text_length_mean(response)
        assert mean == 2.0  # "OK"

    def test_unicode_text(self):
        response = {"feedback_text": "Привет мир"}  # Russian, 10 chars
        mean = compute_open_text_length_mean(response)
        assert mean == len("Привет мир")


# ─────────────────────────── Uniqueness ──────────────────────────────────────

class TestComputeOpenTextUniqueScore:
    def test_unique_text_returns_low_score(self):
        texts = ["abc", "def", "ghi", "jkl", "mno"]
        score = compute_open_text_uniqueness_score("abc", texts)
        assert score == 1 / 5  # only 1 match out of 5

    def test_all_identical_returns_one(self):
        texts = ["same", "same", "same"]
        score = compute_open_text_uniqueness_score("same", texts)
        assert score == 1.0

    def test_empty_batch_returns_zero(self):
        assert compute_open_text_uniqueness_score("text", []) == 0.0


# ─────────────────────────── Attention Checks ────────────────────────────────

class TestComputeAttentionFailCount:
    def test_pass_all_attention_checks(self):
        response = {"attn_q1": "strongly agree", "attn_q2": "5"}
        keys = ["attn_q1", "attn_q2"]
        expected = {"attn_q1": "strongly agree", "attn_q2": "5"}
        assert compute_attention_fail_count(response, keys, expected) == 0

    def test_fail_one_attention_check(self):
        response = {"attn_q1": "disagree", "attn_q2": "5"}
        keys = ["attn_q1", "attn_q2"]
        expected = {"attn_q1": "strongly agree", "attn_q2": "5"}
        assert compute_attention_fail_count(response, keys, expected) == 1

    def test_fail_all_attention_checks(self):
        response = {"attn_q1": "wrong", "attn_q2": "99"}
        keys = ["attn_q1", "attn_q2"]
        expected = {"attn_q1": "correct", "attn_q2": "5"}
        assert compute_attention_fail_count(response, keys, expected) == 2

    def test_missing_attention_key_counts_as_fail(self):
        response = {}
        keys = ["attn_q1"]
        expected = {"attn_q1": "yes"}
        assert compute_attention_fail_count(response, keys, expected) == 1

    def test_no_attention_keys(self):
        response = {"q_1": "3"}
        assert compute_attention_fail_count(response, [], {}) == 0


# ─────────────────────────── Contradictions ──────────────────────────────────

class TestComputeContradictionCount:
    def test_no_contradiction(self):
        response = {"age": "under_18", "has_children": "no"}
        rules = [{"if_key": "age", "if_value": "over_65", "then_key": "is_retired", "must_be": "yes"}]
        assert compute_contradiction_count(response, rules) == 0

    def test_one_contradiction(self):
        response = {"age": "over_65", "is_retired": "no"}
        rules = [{"if_key": "age", "if_value": "over_65", "then_key": "is_retired", "must_be": "yes"}]
        assert compute_contradiction_count(response, rules) == 1

    def test_multiple_contradictions(self):
        response = {"q1": "yes", "q2": "no", "q3": "true", "q4": "false"}
        rules = [
            {"if_key": "q1", "if_value": "yes", "then_key": "q2", "must_be": "yes"},
            {"if_key": "q3", "if_value": "true", "then_key": "q4", "must_be": "true"},
        ]
        assert compute_contradiction_count(response, rules) == 2

    def test_empty_rules(self):
        response = {"q1": "yes"}
        assert compute_contradiction_count(response, []) == 0

    def test_case_insensitive_comparison(self):
        response = {"age": "OVER_65", "is_retired": "NO"}
        rules = [{"if_key": "age", "if_value": "over_65", "then_key": "is_retired", "must_be": "yes"}]
        assert compute_contradiction_count(response, rules) == 1


# ─────────────────────────── Missingness ─────────────────────────────────────

class TestComputeMissingnessRatio:
    def test_no_missing(self, normal_response):
        ratio = compute_missingness_ratio(normal_response)
        assert ratio == 0.0

    def test_all_missing(self, all_null_response):
        ratio = compute_missingness_ratio(all_null_response)
        assert ratio == 1.0

    def test_half_missing(self):
        response = {"q_1": "3", "q_2": None, "q_3": "5", "q_4": ""}
        ratio = compute_missingness_ratio(response)
        assert abs(ratio - 0.5) < 0.01

    def test_empty_response_returns_zero(self):
        assert compute_missingness_ratio({}) == 0.0

    def test_whitespace_only_counts_as_missing(self):
        response = {"q_1": "  ", "q_2": "3"}
        ratio = compute_missingness_ratio(response)
        assert ratio == 0.5
