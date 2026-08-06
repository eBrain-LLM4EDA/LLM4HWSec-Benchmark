from agentic_bench_gen.runner import EvaluationRunner


def test_runner_does_not_expose_private_generation_artifacts(tmp_path):
    case = tmp_path / "case"
    for rel, content in {
        "inputs/code.c": "public",
        "submission/answer.json": "{}",
        "tests/private/check.txt": "harness",
        "golden/code.c": "secret golden",
        "ground_truth/labels.json": "secret labels",
        "expert/expert_bundle.json": "secret bundle",
        "reports/validation_report.json": "secret report",
        "artifacts/artifact_bundle.json": "generation metadata",
    }.items():
        path = case / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    evaluator = case / "evaluation" / "evaluate.py"
    evaluator.parent.mkdir(parents=True)
    evaluator.write_text("""\
from pathlib import Path
assert Path("inputs/code.c").is_file()
assert Path("submission/answer.json").is_file()
assert Path("tests/private/check.txt").is_file()
for private in ("golden", "ground_truth", "expert", "reports", "artifacts"):
    assert not Path(private).exists(), private
print("[TEST] PASS: FR1")
""")

    result = EvaluationRunner().run_evaluator(case)
    assert result["status"] == "pass", result


def test_overlay_copy_does_not_replace_sandbox_root_permissions(tmp_path):
    source = tmp_path / "overlay"
    destination = tmp_path / "sandbox"
    source.mkdir(mode=0o700)
    destination.mkdir(mode=0o755)
    (source / "inputs").mkdir()
    (source / "inputs" / "code.c").write_text("mutant")

    EvaluationRunner._copy_overlay(source, destination)

    assert destination.stat().st_mode & 0o777 == 0o755
    assert (destination / "inputs" / "code.c").read_text() == "mutant"


def test_runner_supports_workspace_root_package_imports(tmp_path):
    case = tmp_path / "case"
    helper = case / "evaluation" / "private" / "oracle.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("VALUE = 7\n")
    evaluator = case / "evaluation" / "evaluate.py"
    evaluator.write_text(
        "from evaluation.private.oracle import VALUE\n"
        "assert VALUE == 7\n"
        "print('[TEST] PASS: FR1')\n"
    )

    result = EvaluationRunner().run_evaluator(case)
    assert result["status"] == "pass", result
