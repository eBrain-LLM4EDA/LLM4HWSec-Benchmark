import tempfile
from pathlib import Path

from agentic_bench_gen.validator import _compute_dynamic_mutation_score, validate_benchmark_case
from agentic_bench_gen.workspace import Workspace


def test_validator_accepts_minimal_hls_case():
    task_spec = {
        "task_id": "hls_case",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["HLS C/C++ code"],
            "functional_requirements": [{"id": "FR1", "requirement": "Synthesizes"}],
        },
        "hidden_spec": {
            "ground_truth": "No illegal secret-to-public flow.",
            "security_requirements": [{"id": "SR1", "requirement": "No secret leakage"}],
        },
        "evaluation": {
            "metrics": [
                {"name": "synthesis_pass_rate", "description": "Bambu synthesis success", "direction": "maximize"}
            ]
        },
    }
    artifact_bundle = {
        "files": [
            {"path": "README.md", "content": "case"},
            {"path": "metadata.json", "content": "{}"},
            {"path": "inputs/kernel.cpp", "content": "int f(){return 0;}"},
        ]
    }
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": "print('{}')"},
        ]
    }
    expert_bundle = {"files": [{"path": "ground_truth/labels.json", "content": "{}"}]}
    mutation_bundle = {"mutants": [
        {"mutant_id": "M1", "target_requirement_id": "SR1"}
    ]}

    report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle)

    assert report["status"] == "pass"
    assert report["coverage_score"] == 1.0
    assert report["mutation_score"] == 1.0


def test_validator_rejects_missing_evaluator_and_metrics():
    report = validate_benchmark_case(
        {"task_id": "x", "domain_id": "rtl_trojan_detection", "public_spec": {}, "hidden_spec": {}},
        {"files": []},
        {"files": []},
    )
    issues = {issue["issue"] for issue in report["issues"]}

    assert report["status"] == "fail"
    assert "missing_metrics" in issues
    assert "missing_evaluator" in issues
    assert "missing_case_file" in issues


def test_dynamic_mutation_score_detects_mutant():
    # evaluate.py passes when inputs/code.c contains SECURE_PATTERN,
    # and fails (exit 1) when it is absent — a mutant that removes the
    # pattern should therefore be counted as detected (score > 0).
    evaluate_py = """\
import sys, pathlib, re

src = pathlib.Path("inputs/code.c").read_text()
if re.search(r"SECURE_PATTERN", src):
    print("[TEST] PASS: SR1")
    sys.exit(0)
else:
    print("[TEST] FAIL: SR1: SECURE_PATTERN missing")
    sys.exit(1)
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        # Write original (clean) source that would pass
        ws.write_text("inputs/code.c", "// SECURE_PATTERN\nint f(){return 0;}")
        # Write evaluator
        ws.write_text("evaluation/evaluate.py", evaluate_py)

        # Mutant removes the secure pattern — evaluator should exit 1
        mutation_bundle = {
            "mutants": [
                {
                    "mutant_id": "M1",
                    "target_requirement_id": "SR1",
                    "files": [{"path": "inputs/code.c", "content": "// no pattern here\nint f(){return 0;}"}],
                }
            ]
        }
        mapped_ids = {"SR1"}
        score = _compute_dynamic_mutation_score(mutation_bundle, mapped_ids, ws)

    assert score == 1.0, f"Expected mutation_score=1.0, got {score}"


def test_dynamic_mutation_score_returns_zero_when_no_evaluator():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        ws.write_text("inputs/code.c", "int f(){return 0;}")
        # No evaluation/evaluate.py written

        mutation_bundle = {
            "mutants": [
                {"mutant_id": "M1", "target_requirement_id": "SR1", "files": []}
            ]
        }
        score = _compute_dynamic_mutation_score(mutation_bundle, {"SR1"}, ws)

    assert score == 0.0
