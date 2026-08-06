import tempfile
from pathlib import Path

from agentic_bench_gen.validator import (
    _compute_differential_validation,
    _compute_dynamic_mutation_score,
    _find_opened_input_files,
    _golden_overlay,
    _parse_failing_checks,
    _submission_overlay_plan,
    validate_benchmark_case,
)
from agentic_bench_gen.workspace import Workspace


def test_validator_accepts_minimal_hls_case():
    task_spec = {
        "task_id": "hls_case",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["kernel.cpp"],
            "interface": "int f(void) in kernel.cpp",
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


def _simulate_case(interface: str) -> tuple[dict, dict, dict]:
    """Minimal hardware_reverse_engineering (simulate) case parameterised by the
    interface string, for the sequential-timing floor check."""
    task_spec = {
        "task_id": "re_case",
        "domain_id": "hardware_reverse_engineering",
        "public_spec": {
            "input_artifacts": ["flattened_netlist.v"],
            "interface": interface,
            "functional_requirements": [
                {"id": "FR1", "requirement": "Recovered module matches reference on random vectors"},
            ],
        },
        "hidden_spec": {
            "ground_truth": "Reference netlist behavior.",
            "security_requirements": [{"id": "SR1", "requirement": "No hidden state"}],
        },
        "evaluation": {"metrics": [{"name": "functional_equivalence", "description": "match", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "case"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/flattened_netlist.v", "content": "module m; endmodule"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional"},
            {"requirement_id": "SR1", "requirement_type": "security"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": "print('{}')"},
        ],
    }
    return task_spec, artifact_bundle, tester_bundle


def test_simulate_interface_without_timing_is_flagged():
    # A functional-only interface (no timing discipline / cycle relationship)
    # is the FSM-recovery failure mode: golden and reference diverge by a cycle.
    task_spec, artifacts, tester = _simulate_case(
        "module recovered_fsm(input clk, input rst, input in, output out); out is high when the "
        "sequence 101 has been seen."
    )
    report = validate_benchmark_case(task_spec, artifacts, tester)
    assert "missing_timing_discipline" in {i["issue"] for i in report["issues"]}


def test_simulate_interface_with_pinned_timing_passes_the_floor():
    task_spec, artifacts, tester = _simulate_case(
        "module recovered_fsm(input clk, input rst, input in, output out); out is a Moore output "
        "asserted on the rising edge following the cycle in which the final pattern bit is sampled; "
        "rst is synchronous active-high and out is 0 the cycle after reset releases."
    )
    report = validate_benchmark_case(task_spec, artifacts, tester)
    assert "missing_timing_discipline" not in {i["issue"] for i in report["issues"]}


def test_report_grading_domain_is_not_subject_to_timing_check():
    # Non-simulate domains must never get the timing issue, whatever the interface.
    task_spec, artifacts, tester = _simulate_case("no timing here at all")
    task_spec["domain_id"] = "gate_trojan_detection"
    task_spec["public_spec"]["input_artifacts"] = ["netlist.v"]
    artifacts["files"][2]["path"] = "inputs/netlist.v"
    report = validate_benchmark_case(task_spec, artifacts, tester)
    assert "missing_timing_discipline" not in {i["issue"] for i in report["issues"]}


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
        ws.write_text("inputs/code.c", "// SECURE_PATTERN\nint f(){return 0;}")
        ws.write_text("evaluation/evaluate.py", evaluate_py)

        mutation_bundle = {
            "mutants": [
                {
                    "mutant_id": "M1",
                    "target_requirement_id": "SR1",
                    "files": [{"path": "inputs/code.c", "content": "// no pattern here\nint f(){return 0;}"}],
                }
            ]
        }
        result = _compute_dynamic_mutation_score(mutation_bundle, {"SR1"}, ws)

    assert result["score"] == 1.0, f"Expected score=1.0, got {result['score']}"
    assert result["baseline_run"] is not None
    assert result["baseline_run"]["exit_code"] == 0
    assert result["per_requirement_coverage"]["SR1"]["covered"] is True
    assert result["check_activation"].get("SR1", 0) == 1
    assert "SR1" not in result["dead_checks"]
    assert "SR1" not in result["uncovered_requirements"]


def test_dynamic_mutation_score_returns_zero_when_baseline_fails():
    evaluate_py = "import sys; sys.exit(1)\n"
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        ws.write_text("inputs/code.c", "int f(){return 0;}")
        ws.write_text("evaluation/evaluate.py", evaluate_py)
        mutation_bundle = {
            "mutants": [
                {"mutant_id": "M1", "target_requirement_id": "SR1",
                 "files": [{"path": "inputs/code.c", "content": "// mutated"}]}
            ]
        }
        result = _compute_dynamic_mutation_score(mutation_bundle, {"SR1"}, ws)
    assert result["score"] == 0.0, f"Expected 0.0 when baseline fails, got {result['score']}"
    assert result["baseline_run"] is not None
    assert result["baseline_run"]["exit_code"] != 0
    assert result["baseline_failed"] is True


def test_dynamic_mutation_score_returns_zero_when_no_evaluator():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        ws.write_text("inputs/code.c", "int f(){return 0;}")
        mutation_bundle = {
            "mutants": [
                {"mutant_id": "M1", "target_requirement_id": "SR1", "files": []}
            ]
        }
        result = _compute_dynamic_mutation_score(mutation_bundle, {"SR1"}, ws)

    assert result["score"] == 0.0
    assert result["baseline_run"] is None


def test_untargeted_requirement_is_untested_not_dead():
    # SR2 is mapped but no mutant targets it — its check cannot be judged, so it
    # is reported as untested rather than dead (dead would punish the mutant
    # sampling, not the check). SR1 is targeted and detected — not dead.
    evaluate_py = """\
import sys, pathlib, re
src = pathlib.Path("inputs/code.c").read_text()
if re.search(r"VULN_PATTERN", src):
    print("[TEST] PASS: SR1")
else:
    print("[TEST] FAIL: SR1: pattern missing")
print("[TEST] PASS: SR2")
sys.exit(0 if re.search(r"VULN_PATTERN", src) else 1)
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        ws.write_text("inputs/code.c", "// VULN_PATTERN\nint f(){return 0;}")
        ws.write_text("evaluation/evaluate.py", evaluate_py)

        mutation_bundle = {
            "mutants": [
                {
                    "mutant_id": "M1",
                    "target_requirement_id": "SR1",
                    "files": [{"path": "inputs/code.c", "content": "// no pattern\nint f(){return 0;}"}],
                }
            ]
        }
        result = _compute_dynamic_mutation_score(mutation_bundle, {"SR1", "SR2"}, ws)

    assert result["score"] == 1.0
    assert "SR2" not in result["dead_checks"]
    assert "SR2" in result["untested_requirements"]
    assert "SR2" not in result["uncovered_requirements"]
    assert "SR1" not in result["dead_checks"]
    assert result["check_activation"].get("SR1", 0) == 1
    assert result["check_activation"].get("SR2", 0) == 0


def test_uncovered_requirement_detected_when_no_mutant_targets_sr():
    # SR2 has a mutant that targets it but the evaluator doesn't catch it (SR2 always passes).
    # SR1 is targeted and detected.
    evaluate_py = """\
import sys, pathlib, re
src = pathlib.Path("inputs/code.c").read_text()
if re.search(r"VULN_PATTERN", src):
    print("[TEST] PASS: SR1")
else:
    print("[TEST] FAIL: SR1: pattern missing")
print("[TEST] PASS: SR2")  # SR2 always passes — dead check
sys.exit(0 if re.search(r"VULN_PATTERN", src) else 1)
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        ws.write_text("inputs/code.c", "// VULN_PATTERN\nint f(){return 0;}")
        ws.write_text("evaluation/evaluate.py", evaluate_py)

        mutation_bundle = {
            "mutants": [
                {
                    "mutant_id": "M1",
                    "target_requirement_id": "SR1",
                    "files": [{"path": "inputs/code.c", "content": "// no pattern\nint f(){return 0;}"}],
                },
                {
                    "mutant_id": "M2",
                    "target_requirement_id": "SR2",
                    # This mutant changes the file but SR2 always passes — not detected
                    "files": [{"path": "inputs/code.c", "content": "// VULN_PATTERN\n// sr2 mutated"}],
                },
            ]
        }
        result = _compute_dynamic_mutation_score(mutation_bundle, {"SR1", "SR2"}, ws)

    assert result["per_requirement_coverage"]["SR1"]["covered"] is True
    assert result["per_requirement_coverage"]["SR2"]["covered"] is False
    assert "SR2" in result["uncovered_requirements"]
    assert "SR1" not in result["uncovered_requirements"]


def test_validator_flags_dead_sr_checks_as_issues():
    # evaluate.py always exits 0 on the mutant (SR1 check never fires)
    evaluate_py = """\
import sys
print("[TEST] PASS: FR1")
print("[TEST] PASS: SR1")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Workspace(tmpdir)
        ws.write_text("inputs/kernel.cpp", "int f(){}")
        ws.write_text("evaluation/evaluate.py", evaluate_py)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "x")
        ws.write_text("metadata.json", "{}")

        task_spec = {
            "task_id": "t",
            "domain_id": "hls_security_codegen",
            "public_spec": {
                "input_artifacts": ["kernel.cpp"],
                "functional_requirements": [{"id": "FR1", "requirement": "x"}],
            },
            "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
            "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
        }
        artifact_bundle = {"files": [
            {"path": "README.md", "content": "x"},
            {"path": "metadata.json", "content": "{}"},
            {"path": "inputs/kernel.cpp", "content": "int f(){}"},
        ]}
        tester_bundle = {
            "requirement_map": [
                {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
                {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            ],
            "files": [
                {"path": "evaluation/README.md", "content": "run"},
                {"path": "evaluation/evaluate.py", "content": evaluate_py},
            ],
        }
        mutation_bundle = {
            "mutants": [
                {"mutant_id": "M1", "target_requirement_id": "SR1",
                 "files": [{"path": "inputs/kernel.cpp", "content": "// mutated"}]}
            ]
        }
        report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle, ws=Workspace(tmpdir), mutation_bundle=mutation_bundle)

    issue_types = {i["issue"] for i in report["issues"]}
    assert "dead_check" in issue_types
    assert "SR1" in report.get("dead_checks", [])


def test_validator_flags_evaluator_undeclared_file():
    task_spec = {
        "task_id": "hls_case",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["kernel.cpp"],
            "functional_requirements": [{"id": "FR1", "requirement": "Synthesizes"}],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/kernel.cpp", "content": "int f(){}"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": 'open("inputs/wrong_name.cpp")'},
        ],
    }
    report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle)
    issues = {i["issue"] for i in report["issues"]}
    assert "evaluator_opens_undeclared_file" in issues


def test_find_opened_input_files():
    content = """
open("inputs/aes_sbox.v")
open('inputs/testbench.v')
os.path.join('inputs', 'analysis.json')
filepath = f"inputs/foo.cpp"
"""
    found = _find_opened_input_files(content)
    assert "aes_sbox.v" in found
    assert "testbench.v" in found
    assert "analysis.json" in found
    assert "foo.cpp" in found


def test_parse_failing_checks():
    stdout = (
        "[TEST] PASS: FR1\n"
        "[TEST] FAIL: SR1: pattern not found\n"
        "[TEST] FAIL: SR2: branch absent\n"
        "[TEST] FAIL: SETUP: file missing\n"
    )
    found = _parse_failing_checks(stdout)
    assert "SR1" in found
    assert "SR2" in found
    assert "SETUP" not in found  # SETUP failures are excluded
    assert "FR1" not in found    # PASS lines are not included


def test_validator_flags_evaluator_skips_requirement():
    task_spec = {
        "task_id": "hls_case",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["kernel.cpp"],
            "functional_requirements": [{"id": "FR1", "requirement": "Synthesizes"}],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "no timing leak"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/kernel.cpp", "content": "int f(){}"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": (
                'print("[TEST] PASS: FR1")\n'
                'print("[TEST] SKIP: SR1 (not enforced on baseline)")\n'
            )},
        ],
    }
    report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle)
    issues = {i["issue"] for i in report["issues"]}
    assert "evaluator_skips_requirement" in issues


# --- differential golden/vulnerable validation gate ---

_INVERTED_EVALUATOR = """\
import sys, pathlib
src = pathlib.Path("inputs/code.c").read_text()
# INVERTED logic: PASS when the vulnerability marker is PRESENT.
if "VULN" in src:
    print("[TEST] PASS: SR1")
    sys.exit(0)
print("[TEST] FAIL: SR1: vulnerability absent")
sys.exit(1)
"""

_CORRECT_EVALUATOR = """\
import sys, pathlib
src = pathlib.Path("inputs/code.c").read_text()
# CORRECT logic: PASS only when the code is secure (marker ABSENT).
if "VULN" in src:
    print("[TEST] FAIL: SR1: vulnerability present")
    sys.exit(1)
print("[TEST] PASS: SR1")
sys.exit(0)
"""

_VULN_SRC = "// VULN insecure baseline\nint f(){return 0;}"
_SECURE_GOLDEN = {"files": [{"path": "golden/code.c", "content": "// secure\nint f(){return 0;}"}]}
_DIFF_SPEC = {"domain_id": "hls_security_codegen", "public_spec": {"input_artifacts": ["code.c"]}}


def test_golden_overlay_requires_exact_filename_match():
    task_spec = {"domain_id": "hls_security_codegen", "public_spec": {"input_artifacts": ["code.c", "spec.md"]}}
    expert_bundle = {"files": [
        {"path": "golden/secure.c", "content": "SECURE"},
        {"path": "golden/notes.txt", "content": "ignored"},
    ]}
    assert _golden_overlay(task_spec, expert_bundle) == {}


def test_golden_overlay_does_not_replace_same_stem_header():
    task_spec = {
        "domain_id": "hls_security_codegen",
        "public_spec": {"input_artifacts": ["dispatcher.cpp", "dispatcher.h"]},
    }
    expert_bundle = {"files": [{
        "path": "golden/dispatcher.cpp", "content": "secure implementation",
    }]}
    assert _golden_overlay(task_spec, expert_bundle) == {
        "inputs/dispatcher.cpp": "secure implementation",
    }


def test_submission_overlay_plan_records_unmapped_header_and_hashes(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_text("inputs/dispatcher.cpp", "insecure")
    ws.write_text("inputs/dispatcher.h", "valid header")
    spec = {
        "domain_id": "hls_security_codegen",
        "public_spec": {"input_artifacts": ["dispatcher.cpp", "dispatcher.h"]},
    }
    expert = {"files": [{"path": "golden/dispatcher.cpp", "content": "secure"}]}
    plan = _submission_overlay_plan(spec, expert, ws=ws)
    assert plan["status"] == "pass"
    assert plan["overlay"] == {"inputs/dispatcher.cpp": "secure"}
    assert plan["unmapped_targets"] == ["inputs/dispatcher.h"]
    assert plan["mappings"][0]["changed"] is True
    assert len(plan["mappings"][0]["golden_sha256"]) == 64


def test_golden_overlay_empty_when_no_code_input():
    assert _golden_overlay({"public_spec": {"input_artifacts": ["spec.md"]}}, _SECURE_GOLDEN) == {}


def test_differential_flags_inverted_security_logic():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", _INVERTED_EVALUATOR)
        diff = _compute_differential_validation(_DIFF_SPEC, _SECURE_GOLDEN, ws)

    assert diff["status"] == "fail"
    assert diff["golden_run"]["ok"] is False       # secure golden wrongly rejected
    assert diff["vulnerable_run"]["ok"] is False    # insecure baseline wrongly accepted


def test_differential_passes_for_correct_evaluator():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", _CORRECT_EVALUATOR)
        diff = _compute_differential_validation(_DIFF_SPEC, _SECURE_GOLDEN, ws)

    assert diff["status"] == "pass"
    assert diff["golden_run"]["ok"] is True
    assert diff["vulnerable_run"]["ok"] is True


def test_differential_skipped_without_golden():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", _CORRECT_EVALUATOR)
        diff = _compute_differential_validation(_DIFF_SPEC, {"files": []}, ws)
    assert diff["status"] == "fail"
    assert diff["failure_class"] == "submission_invariant"


def test_validate_benchmark_case_raises_inverted_logic_issues():
    task_spec = {
        "task_id": "t",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["code.c"],
            "functional_requirements": [{"id": "FR1", "requirement": "x"}],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/code.c", "content": _VULN_SRC},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": _INVERTED_EVALUATOR},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", _INVERTED_EVALUATOR)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "x")
        ws.write_text("metadata.json", "{}")
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, _SECURE_GOLDEN, mutation_bundle=None, ws=ws,
        )

    issues = {i["issue"] for i in report["issues"]}
    assert "golden_rejected" in issues
    assert "vulnerable_accepted" in issues
    assert report["status"] == "fail"
    assert report["differential"]["status"] == "fail"


def test_golden_overlay_prefers_exact_filename_match():
    task_spec = {"domain_id": "hls_security_codegen", "public_spec": {"input_artifacts": ["code.c"]}}
    expert_bundle = {"files": [
        {"path": "golden/testbench.c", "content": "TB"},
        {"path": "golden/code.c", "content": "SECURE"},
    ]}
    assert _golden_overlay(task_spec, expert_bundle) == {"inputs/code.c": "SECURE"}


def test_golden_overlay_maps_report_domain_answer_onto_submission_path():
    # analysis_report domain: the golden answer overlays onto submission/, not inputs/.
    task_spec = {"domain_id": "rtl_trojan_detection", "public_spec": {"input_artifacts": ["aes.v"]}}
    expert_bundle = {"files": [
        {"path": "golden/trojan_report.json", "content": '{"trigger": ["n42"]}'},
        {"path": "ground_truth/labels.json", "content": "ignored oracle"},
    ]}
    assert _golden_overlay(task_spec, expert_bundle) == {
        "submission/trojan_report.json": '{"trigger": ["n42"]}'
    }


_REPORT_EVALUATOR = """\
import sys, json, pathlib
# analysis_report grader: reads the input netlist for reference, grades the
# submitted answer file against the known-correct trigger node.
try:
    ans = json.loads(pathlib.Path("submission/trojan_report.json").read_text())
except Exception:
    print("[TEST] FAIL: SETUP: submission/trojan_report.json not found or invalid")
    sys.exit(1)
ok = True
if isinstance(ans.get("trigger"), list) and ans.get("trigger"):
    print("[TEST] PASS: FR1")
else:
    print("[TEST] FAIL: FR1: trigger list missing")
    ok = False
if ans.get("trigger") == ["n42"]:
    print("[TEST] PASS: SR1")
else:
    print("[TEST] FAIL: SR1: wrong trigger node")
    ok = False
sys.exit(0 if ok else 1)
"""


def test_report_domain_end_to_end_grades_submission_not_inputs():
    # Full validate_benchmark_case for an analysis_report domain: the golden
    # answer under submission/ must be accepted, the naive baseline answer
    # rejected, and a corrupted-answer mutant detected.
    task_spec = {
        "task_id": "rtl_tj",
        "domain_id": "rtl_trojan_detection",
        "public_spec": {
            "input_artifacts": ["aes.v"],
            "functional_requirements": [{"id": "FR1", "requirement": "well-formed report"}],
        },
        "hidden_spec": {"ground_truth": "trigger is n42", "security_requirements": [{"id": "SR1", "requirement": "correct trigger"}]},
        "evaluation": {"metrics": [{"name": "detection_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "find the trojan trigger"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/aes.v", "content": "module aes(); endmodule"},
        # naive baseline answer the evaluator must reject
        {"path": "submission/trojan_report.json", "content": '{"trigger": []}'},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": _REPORT_EVALUATOR},
        ],
    }
    expert_bundle = {"files": [{"path": "golden/trojan_report.json", "content": '{"trigger": ["n42"]}'}]}
    mutation_bundle = {"mutants": [
        {
            "mutant_id": "M1",
            "target_requirement_id": "SR1",
            "files": [{"path": "submission/trojan_report.json", "content": '{"trigger": ["n99"]}'}],
        },
        {
            "mutant_id": "M2",
            "target_requirement_id": "FR1",
            "files": [{"path": "submission/trojan_report.json", "content": '{"trigger": []}'}],
        },
    ]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/aes.v", "module aes(); endmodule")
        ws.write_text("submission/trojan_report.json", '{"trigger": []}')
        ws.write_text("evaluation/evaluate.py", _REPORT_EVALUATOR)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "find the trojan trigger")
        ws.write_text("metadata.json", "{}")
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle, ws=ws,
        )

    issues = {i["issue"] for i in report["issues"]}
    assert "golden_rejected" not in issues       # golden answer accepted
    assert "vulnerable_accepted" not in issues    # naive baseline answer rejected
    assert report["differential"]["status"] == "pass"
    assert report["mutation_score"] == 1.0        # wrong-trigger mutant detected
    assert report["status"] == "pass"
    assert report["requirement_mapping_coverage_score"] == 1.0
    assert report["requirement_discrimination_coverage_score"] == 1.0


def test_grader_convention_mutation_scoring_with_golden_overlay():
    # Mutants are corrupted golden submissions: staged over the golden overlay,
    # graded by a correct evaluator that rejects code containing the
    # vulnerability. The golden run is the baseline that must pass.
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)  # insecure as-shipped baseline
        ws.write_text("evaluation/evaluate.py", _CORRECT_EVALUATOR)
        overlay = {"inputs/code.c": "// secure\nint f(){return 0;}"}
        mutation_bundle = {"mutants": [{
            "mutant_id": "M1",
            "target_requirement_id": "SR1",
            "files": [{"path": "inputs/code.c", "content": "// VULN reintroduced\nint f(){return 0;}"}],
        }]}
        result = _compute_dynamic_mutation_score(
            mutation_bundle, {"SR1"}, ws, golden_overlay=overlay,
        )

    assert result["baseline_failed"] is False
    assert result["baseline_run"]["exit_code"] == 0  # golden submission accepted
    assert result["score"] == 1.0
    assert result["per_requirement_coverage"]["SR1"]["covered"] is True


def test_mutant_run_crash_counts_as_error_not_detection():
    crash_evaluator = """\
import sys, pathlib
src = pathlib.Path("inputs/code.c").read_text()
if "BOOM" in src:
    raise RuntimeError("evaluator crashed")
print("[TEST] PASS: SR1")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", "int f(){return 0;}")
        ws.write_text("evaluation/evaluate.py", crash_evaluator)
        mutation_bundle = {"mutants": [{
            "mutant_id": "M1",
            "target_requirement_id": "SR1",
            "files": [{"path": "inputs/code.c", "content": "// BOOM"}],
        }]}
        result = _compute_dynamic_mutation_score(mutation_bundle, {"SR1"}, ws)

    assert result["error_runs"] == 1
    assert result["score"] == 0.0  # excluded, not counted as detected
    assert "SR1" in result["dead_checks"]
    assert "SR1" in result["uncovered_requirements"]
    assert "SR1" not in result["untested_requirements"]


def test_validator_flags_requirement_id_mismatch():
    # requirement_map says SR-1 but the evaluator emits markers for SR1.
    evaluator = """\
import sys, pathlib
src = pathlib.Path("inputs/code.c").read_text()
if "VULN" in src:
    print("[TEST] FAIL: SR1: vulnerability present")
    sys.exit(1)
print("[TEST] PASS: SR1")
print("[TEST] PASS: FR1")
sys.exit(0)
"""
    task_spec = {
        "task_id": "t",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["code.c"],
            "functional_requirements": [{"id": "FR1", "requirement": "x"}],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR-1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/code.c", "content": _VULN_SRC},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR-1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": evaluator},
        ],
    }
    expert_bundle = {"files": [{"path": "golden/code.c", "content": "// secure\nint f(){return 0;}"}]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", evaluator)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "x")
        ws.write_text("metadata.json", "{}")
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle=None, ws=ws,
        )

    issues = {i["issue"] for i in report["issues"]}
    assert "requirement_id_mismatch" in issues
    assert "golden_rejected" in issues
    assert "vulnerable_rejection_invalid" in issues


def test_validator_flags_missing_golden_overlay():
    # No golden code overlay exists (expert ships only labels), the differential
    # gate is skipped, and the as-shipped baseline fails — the report must say
    # so instead of passing validation with a 0.0 mutation score.
    evaluator = 'import sys\nprint("[TEST] FAIL: SR1: broken")\nsys.exit(1)\n'
    task_spec = {
        "task_id": "t",
        "domain_id": "rtl_trojan_detection",
        "public_spec": {
            "input_artifacts": ["design_spec.md"],
            "functional_requirements": [{"id": "FR1", "requirement": "x"}],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "detection_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/design_spec.md", "content": "spec"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": evaluator},
        ],
    }
    # Expert ships only a non-matching oracle (no golden/ answer, no .json that
    # could overlay onto submission/trojan_report.json), so no golden overlay
    # resolves and the differential gate is skipped.
    expert_bundle = {"files": [{"path": "ground_truth/notes.txt", "content": "labels"}]}
    mutation_bundle = {"mutants": [{
        "mutant_id": "M1",
        "target_requirement_id": "SR1",
        "files": [{"path": "submission/trojan_report.json", "content": "mutated"}],
    }]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/design_spec.md", "spec")
        ws.write_text("evaluation/evaluate.py", evaluator)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "x")
        ws.write_text("metadata.json", "{}")
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle, ws=ws,
        )

    issues = {i["issue"] for i in report["issues"]}
    assert "golden_overlay_missing" in issues
    assert report["status"] == "fail"
    assert report["mutation_score"] == 0.0


def test_find_opened_input_files_ignores_comments_and_docstrings():
    content = (
        '"""This evaluator checks inputs/mentioned_in_docs.md for style."""\n'
        "# historically we also read inputs/old_name.v here\n"
        'open("inputs/real.v")\n'
    )
    found = _find_opened_input_files(content)
    assert found == {"real.v"}


# --- interface pinning gate (independent Expert/Tester agreement anchor) ---

def _hls_case_without_interface():
    task_spec = {
        "task_id": "t",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["kernel.cpp"],
            "functional_requirements": [{"id": "FR1", "requirement": "x"}],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/kernel.cpp", "content": "int f(){}"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "FR1", "requirement_type": "functional", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": "print()"},
        ],
    }
    return task_spec, artifact_bundle, tester_bundle


def test_validator_flags_missing_interface_for_hardened_artifact_domain():
    task_spec, artifact_bundle, tester_bundle = _hls_case_without_interface()
    report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle)
    assert "missing_interface" in {i["issue"] for i in report["issues"]}


def test_validator_accepts_pinned_interface_for_hardened_artifact_domain():
    task_spec, artifact_bundle, tester_bundle = _hls_case_without_interface()
    task_spec["public_spec"]["interface"] = "void f(const unsigned char *key) in kernel.cpp"
    report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle)
    assert "missing_interface" not in {i["issue"] for i in report["issues"]}


def test_validator_does_not_require_interface_for_report_domains():
    report = validate_benchmark_case(
        {"task_id": "x", "domain_id": "rtl_trojan_detection", "public_spec": {}, "hidden_spec": {}},
        {"files": []},
        {"files": []},
    )
    assert "missing_interface" not in {i["issue"] for i in report["issues"]}


def test_mutation_score_meaningful_flag_false_when_golden_run_fails():
    # An evaluator that rejects everything: the golden overlay run fails, so the
    # 0.0 mutation score must be flagged as not meaningful.
    evaluator = 'import sys\nprint("[TEST] FAIL: SR1: always")\nsys.exit(1)\n'
    task_spec = {
        "task_id": "t",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["code.c"],
            "interface": "int f(void) in code.c",
            "functional_requirements": [],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/code.c", "content": "int f(){return 1;}"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": evaluator},
        ],
    }
    expert_bundle = {"files": [{"path": "golden/code.c", "content": "int f(){return 0;}"}]}
    mutation_bundle = {"mutants": [{
        "mutant_id": "M1",
        "target_requirement_id": "SR1",
        "files": [{"path": "inputs/code.c", "content": "int f(){return 2;}"}],
    }]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", "int f(){return 1;}")
        ws.write_text("evaluation/evaluate.py", evaluator)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "x")
        ws.write_text("metadata.json", "{}")
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle, ws=ws,
        )

    assert report["mutation_score"] == 0.0
    assert report["mutation_score_meaningful"] is False


def test_mutation_score_meaningful_flag_true_on_static_estimate_path():
    task_spec, artifact_bundle, tester_bundle = _hls_case_without_interface()
    report = validate_benchmark_case(task_spec, artifact_bundle, tester_bundle)
    assert report["mutation_score_meaningful"] is True


# ---------------------------------------------------------------------------
# Public/hidden separation and functional-requirement adequacy gates
# ---------------------------------------------------------------------------

def _leak_case(domain_id="hls_security_codegen", input_artifacts=None, files=None,
               functional_requirements=None, objective="Implement the kernel."):
    task_spec = {
        "task_id": "t",
        "domain_id": domain_id,
        "public_spec": {
            "objective": objective,
            "input_artifacts": input_artifacts if input_artifacts is not None else ["code.c"],
            "interface": "void f(void) in code.c",
            "functional_requirements": functional_requirements if functional_requirements is not None
            else [{"id": "FR1", "requirement": "f() returns the XOR of its inputs"},
                  {"id": "FR2", "requirement": "compiles under gcc and g++"}],
        },
        "hidden_spec": {
            "ground_truth": "ok",
            "cwe_ids": ["CWE-208"],
            "security_requirements": [{"id": "SR1", "requirement": "x"}],
        },
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": files if files is not None else [
        {"path": "README.md", "content": "Implement the kernel."},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/code.c", "content": "void f(void){}"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": rid, "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "x"}
            for rid in ("FR1", "FR2", "SR1")
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": "print('[TEST] PASS: SR1')"},
        ],
    }
    return task_spec, artifact_bundle, tester_bundle


def _issue_kinds(report):
    return {issue["issue"] for issue in report["issues"]}


def test_leak_flagged_when_input_artifacts_declare_security_files():
    spec, bundle, tester = _leak_case(input_artifacts=["code.c", "security_spec.md", "cwe_list.md"])
    report = validate_benchmark_case(spec, bundle, tester)
    assert "public_security_leak" in _issue_kinds(report)
    assert report["status"] == "fail"


def test_leak_flagged_when_public_file_mentions_cwe_or_sr_ids():
    spec, bundle, tester = _leak_case(files=[
        {"path": "README.md", "content": "Implement the kernel."},
        {"path": "metadata.json", "content": "{}"},
        # The observed failure mode: baseline code comments citing the CWEs.
        {"path": "inputs/code.c", "content": "/* leaks timing, see CWE-208 and SR1 */ void f(void){}"},
    ])
    report = validate_benchmark_case(spec, bundle, tester)
    leaks = [i for i in report["issues"] if i["issue"] == "public_security_leak"]
    assert leaks and leaks[0]["path"] == "inputs/code.c"


def test_leak_flagged_when_public_spec_text_mentions_cwe():
    spec, bundle, tester = _leak_case(objective="Fix the CWE-208 timing leak in code.c")
    report = validate_benchmark_case(spec, bundle, tester)
    assert "public_security_leak" in _issue_kinds(report)


def test_clean_public_side_raises_no_leak_issue():
    spec, bundle, tester = _leak_case()
    report = validate_benchmark_case(spec, bundle, tester)
    assert "public_security_leak" not in _issue_kinds(report)


def test_analysis_domains_may_mention_cwes_publicly():
    # For detection tasks the security goal IS the public task; only the
    # ground-truth labels are hidden. CWE mentions are not a leak there.
    spec, bundle, tester = _leak_case(domain_id="rtl_trojan_detection", files=[
        {"path": "README.md", "content": "Find the trojan (think CWE-1234 class issues)."},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/design.v", "content": "module m; endmodule"},
    ], input_artifacts=["design.v"])
    report = validate_benchmark_case(spec, bundle, tester)
    assert "public_security_leak" not in _issue_kinds(report)


def test_empty_functional_requirements_flagged():
    spec, bundle, tester = _leak_case(functional_requirements=[])
    report = validate_benchmark_case(spec, bundle, tester)
    assert "missing_functional_requirements" in _issue_kinds(report)


def test_single_generic_fr_flagged():
    # The exact normalizer fallback injected when the Architect emits no FRs.
    spec, bundle, tester = _leak_case(functional_requirements=[
        {"id": "FR1", "requirement": "The submitted artifact satisfies the public objective and interface contract."},
    ])
    report = validate_benchmark_case(spec, bundle, tester)
    assert "generic_functional_requirement" in _issue_kinds(report)


def test_single_concrete_fr_and_plural_frs_not_flagged():
    spec, bundle, tester = _leak_case(functional_requirements=[
        {"id": "FR1", "requirement": "ciphertext[i] == plaintext[i] ^ key[i] for all i"},
    ])
    report = validate_benchmark_case(spec, bundle, tester)
    kinds = _issue_kinds(report)
    assert "generic_functional_requirement" not in kinds
    assert "missing_functional_requirements" not in kinds


def test_mutation_score_meaningful_flag_false_when_differential_fails_without_mutants():
    # The orchestrator skips mutant generation when the tester pre-flight
    # differential still fails; the empty mutation bundle's 0.0 score must be
    # flagged as not meaningful (the evaluator is broken, not undiscriminating).
    evaluator = 'import sys\nprint("[TEST] FAIL: SR1: always")\nsys.exit(1)\n'
    task_spec = {
        "task_id": "t",
        "domain_id": "hls_security_codegen",
        "public_spec": {
            "input_artifacts": ["code.c"],
            "interface": "int f(void) in code.c",
            "functional_requirements": [],
        },
        "hidden_spec": {"ground_truth": "ok", "security_requirements": [{"id": "SR1", "requirement": "x"}]},
        "evaluation": {"metrics": [{"name": "synthesis_pass_rate", "description": "x", "direction": "maximize"}]},
    }
    artifact_bundle = {"files": [
        {"path": "README.md", "content": "x"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/code.c", "content": "int f(){return 1;}"},
    ]}
    tester_bundle = {
        "requirement_map": [
            {"requirement_id": "SR1", "requirement_type": "security", "test_files": ["evaluation/evaluate.py"], "expected_detection": "pass"},
        ],
        "files": [
            {"path": "evaluation/README.md", "content": "run"},
            {"path": "evaluation/evaluate.py", "content": evaluator},
        ],
    }
    expert_bundle = {"files": [{"path": "golden/code.c", "content": "int f(){return 0;}"}]}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", "int f(){return 1;}")
        ws.write_text("evaluation/evaluate.py", evaluator)
        ws.write_text("evaluation/README.md", "run")
        ws.write_text("README.md", "x")
        ws.write_text("metadata.json", "{}")
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, expert_bundle,
            {"mutants": [], "skipped": "tester pre-flight differential failed"}, ws=ws,
        )

    assert report["differential"]["status"] == "fail"
    assert report["mutation_score"] == 0.0
    assert report["mutation_score_meaningful"] is False
    assert report["mutation_status"] == "blocked_by_differential"
    assert report["blocked_mutation_requirements"] == ["SR1"]
    assert "untested_requirement" not in _issue_kinds(report)


def test_dynamic_mutation_score_is_not_meaningful_without_mutants():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", _CORRECT_EVALUATOR)
        spec, bundle, tester = _leak_case(functional_requirements=[])
        expert = {"files": [{
            "path": "golden/code.c",
            "content": _SECURE_GOLDEN["files"][0]["content"],
        }]}
        report = validate_benchmark_case(
            spec, bundle, tester, expert, {"mutants": []}, ws=ws,
        )

    assert report["differential"]["status"] == "pass"
    assert report["mutation_score_meaningful"] is False


def test_mutant_rejected_by_wrong_check_gets_no_target_credit():
    evaluator = """\
import pathlib, sys
src = pathlib.Path("inputs/code.c").read_text()
print("[TEST] PASS: SR2")
if "BREAK_FR1" in src:
    print("[TEST] FAIL: FR1: broken behavior")
    sys.exit(1)
print("[TEST] PASS: FR1")
sys.exit(0)
"""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", "int f(void) { return 0; }")
        ws.write_text("evaluation/evaluate.py", evaluator)
        result = _compute_dynamic_mutation_score({"mutants": [{
            "mutant_id": "M1",
            "target_requirement_id": "SR2",
            "files": [{"path": "inputs/code.c", "content": "// BREAK_FR1"}],
        }]}, {"FR1", "SR2"}, ws)

    assert result["score"] == 0.0
    assert result["check_activation"]["FR1"] == 1
    assert result["per_requirement_coverage"]["SR2"]["covered"] is False
    assert "SR2" in result["dead_checks"]
    assert "SR2" in result["uncovered_requirements"]


def test_unsafe_mutant_path_is_an_error_and_cannot_escape(tmp_path):
    ws = Workspace(tmp_path / "case")
    ws.write_text("inputs/code.c", "int f(void) { return 0; }")
    ws.write_text(
        "evaluation/evaluate.py",
        'print("[TEST] PASS: SR1")\n',
    )
    result = _compute_dynamic_mutation_score({"mutants": [{
        "mutant_id": "M1",
        "target_requirement_id": "SR1",
        "files": [{"path": "../escape.c", "content": "bad"}],
    }]}, {"SR1"}, ws)

    assert result["error_runs"] == 1
    assert result["score"] == 0.0
    assert not (tmp_path / "escape.c").exists()


def test_validator_flags_duplicate_requirement_ids_and_mappings():
    spec, bundle, tester = _leak_case()
    spec["hidden_spec"]["security_requirements"][0]["id"] = "FR1"
    tester["requirement_map"].append(dict(tester["requirement_map"][0]))
    report = validate_benchmark_case(spec, bundle, tester)
    kinds = _issue_kinds(report)
    assert "duplicate_requirement_id" in kinds
    assert "duplicate_requirement_mapping" in kinds


def test_differential_does_not_count_setup_failure_as_vulnerable_rejection():
    evaluator = 'import sys\nprint("[TEST] FAIL: SETUP: missing tool")\nsys.exit(1)\n'
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", evaluator)
        diff = _compute_differential_validation(_DIFF_SPEC, _SECURE_GOLDEN, ws)
    assert diff["status"] == "fail"
    assert diff["vulnerable_run"]["ok"] is False


def test_differential_ignores_non_requirement_evidence_markers():
    evaluator = _CORRECT_EVALUATOR.replace(
        'src = pathlib.Path("inputs/code.c").read_text()',
        'src = pathlib.Path("inputs/code.c").read_text()\nprint("[EVIDENCE] FAIL: optional diagnostic")',
    )
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", evaluator)
        diff = _compute_differential_validation(_DIFF_SPEC, _SECURE_GOLDEN, ws)

    assert diff["status"] == "pass"


def test_evaluator_traceback_is_classified_separately():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(tmp)
        ws.write_text("inputs/code.c", _VULN_SRC)
        ws.write_text("evaluation/evaluate.py", "raise ModuleNotFoundError('private oracle')\n")
        diff = _compute_differential_validation(_DIFF_SPEC, _SECURE_GOLDEN, ws)

    assert diff["failure_class"] == "evaluator_error"
