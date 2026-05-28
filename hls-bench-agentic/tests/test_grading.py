import pytest
from hls_bench_agentic.grading import (
    compute_grade,
    compute_composite,
    functional_equivalence_from_execution,
    get_difficulty_weight,
    DIFFICULTY_WEIGHTS,
)


def test_grade_bands():
    assert compute_grade(1.00) == "A"
    assert compute_grade(0.90) == "A"
    assert compute_grade(0.89) == "B"
    assert compute_grade(0.75) == "B"
    assert compute_grade(0.74) == "C"
    assert compute_grade(0.60) == "C"
    assert compute_grade(0.59) == "D"
    assert compute_grade(0.40) == "D"
    assert compute_grade(0.39) == "F"
    assert compute_grade(0.00) == "F"


def test_difficulty_weights():
    assert DIFFICULTY_WEIGHTS["easy"]   == 1.0
    assert DIFFICULTY_WEIGHTS["medium"] == 1.5
    assert DIFFICULTY_WEIGHTS["hard"]   == 2.0


def test_get_difficulty_weight_from_spec():
    spec = {"hidden_spec": {"difficulty": "hard"}}
    assert get_difficulty_weight(spec) == 2.0


def test_get_difficulty_weight_default():
    assert get_difficulty_weight({}) == 1.5   # default medium


def test_compute_composite_with_llm():
    result = compute_composite(
        synthesis_pass=1.0,
        security_property_correctness=0.8,
        functional_equivalence=1.0,
        security_completeness=1.0,
        llm_security_score=0.9,
    )
    assert "composite_score" in result
    assert "grade" in result
    assert "llm_security_score" in result["dimension_scores"]
    assert 0.0 <= result["composite_score"] <= 1.0


def test_compute_composite_without_llm():
    result = compute_composite(
        synthesis_pass=1.0,
        security_property_correctness=0.8,
        functional_equivalence=1.0,
        security_completeness=1.0,
    )
    assert "llm_security_score" not in result["dimension_scores"]
    assert 0.0 <= result["composite_score"] <= 1.0


def test_functional_equivalence_all_pass():
    exec_results = {"steps": [
        {"status": "pass"}, {"status": "pass"},
    ]}
    assert functional_equivalence_from_execution(exec_results) == 1.0


def test_functional_equivalence_all_not_run():
    exec_results = {"steps": [
        {"status": "not_run"}, {"status": "not_run"},
    ]}
    assert functional_equivalence_from_execution(exec_results) == 0.5


def test_functional_equivalence_mixed():
    exec_results = {"steps": [
        {"status": "pass"}, {"status": "fail"}, {"status": "not_run"},
    ]}
    score = functional_equivalence_from_execution(exec_results)
    assert score == pytest.approx(0.5, abs=0.01)


def test_functional_equivalence_prefers_csim_step():
    exec_results = {"steps": [
        {"name": "csim", "status": "pass"},
        {"name": "rtl_security", "status": "fail"},
        {"name": "synth", "status": "not_run"},
    ]}
    assert functional_equivalence_from_execution(exec_results) == 1.0


def test_functional_equivalence_empty():
    assert functional_equivalence_from_execution({"steps": []}) == 0.5


def test_composite_score_clamped():
    result = compute_composite(
        synthesis_pass=1.0,
        security_property_correctness=1.0,
        functional_equivalence=1.0,
        security_completeness=1.0,
        llm_security_score=1.0,
    )
    assert result["composite_score"] <= 1.0


def test_composite_grade_a_for_perfect():
    result = compute_composite(
        synthesis_pass=1.0,
        security_property_correctness=1.0,
        functional_equivalence=1.0,
        security_completeness=1.0,
        llm_security_score=1.0,
    )
    assert result["grade"] == "A"
