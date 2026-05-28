import json
from pathlib import Path

import pytest

from hls_bench_agentic.schemas import load_schema, validate_or_raise

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def _load(name: str) -> dict:
    return load_schema(SCHEMAS_DIR / name)


# ---------------------------------------------------------------------------
# Smoke-test: every schema file is valid JSON
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("schema_file", list(SCHEMAS_DIR.glob("*.schema.json")))
def test_schema_is_valid_json(schema_file):
    data = json.loads(schema_file.read_text())
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# task_spec: valid minimal instance passes
# ---------------------------------------------------------------------------

def test_task_spec_valid():
    schema = _load("task_spec.schema.json")
    instance = {
        "task_id": "hls_cwe385_test",
        "title": "Test task",
        "public_spec": {
            "language": "C++ HLS",
            "top_function": "foo",
            "description": "A test function.",
            "interface": "ap_uint<8> foo(ap_uint<8> a, ap_uint<8> b)",
            "functional_requirements": [{"id": "FR1", "requirement": "Returns a+b"}],
            "constraints": ["no recursion"],
            "allowed_pragmas": ["HLS PIPELINE"],
        },
        "hidden_spec": {
            "cwe_ids": ["CWE-385"],
            "security_domain": "side_channel",
            "difficulty": "easy",
            "security_requirements": [
                {
                    "id": "SR1",
                    "requirement": "Constant-time execution",
                    "detection_strategy": "Measure cycle count for all inputs",
                }
            ],
            "forbidden_patterns": ["early return"],
            "threat_model": "Timing adversary",
            "oracle_notes": "Check loop structure",
        },
        "evaluation_plan": {
            "positive_tests": ["csim passes"],
            "negative_tests": ["early return detected"],
            "coverage_goals": ["all byte values"],
            "mutation_goals": ["add early return"],
        },
    }
    validate_or_raise(instance, schema)


def test_task_spec_missing_cwe_ids_fails():
    schema = _load("task_spec.schema.json")
    instance = {
        "task_id": "x",
        "title": "x",
        "public_spec": {
            "language": "C++",
            "top_function": "f",
            "description": "d",
            "interface": "i",
            "functional_requirements": [],
            "constraints": [],
            "allowed_pragmas": [],
        },
        "hidden_spec": {
            # cwe_ids missing intentionally
            "security_requirements": [],
            "forbidden_patterns": [],
            "threat_model": "t",
            "oracle_notes": "o",
        },
        "evaluation_plan": {
            "positive_tests": [],
            "negative_tests": [],
            "coverage_goals": [],
            "mutation_goals": [],
        },
    }
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_or_raise(instance, schema)


def test_score_report_schema_avoids_provider_rejected_numeric_bounds():
    schema_text = (SCHEMAS_DIR / "score_report.schema.json").read_text()
    assert '"minimum"' not in schema_text
    assert '"maximum"' not in schema_text


# ---------------------------------------------------------------------------
# arbiter_decision: invalid enum fails
# ---------------------------------------------------------------------------

def test_arbiter_invalid_root_cause_fails():
    schema = _load("arbiter_decision.schema.json")
    instance = {
        "root_cause": "made_up_cause",
        "retain_task": False,
        "artifact_to_revise": "none",
        "revision_instructions": "x",
        "rationale": "y",
    }
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_or_raise(instance, schema)
