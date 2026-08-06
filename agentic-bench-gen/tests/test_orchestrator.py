import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from agentic_bench_gen.agents import FileBundleAgent, JsonAgent
import agentic_bench_gen.orchestrator as orchestrator_module
from agentic_bench_gen.workspace import Workspace
from agentic_bench_gen.orchestrator import (
    BenchGenOrchestrator,
    _build_case_manifest,
    _deterministic_report_mutant,
    _deterministic_retain,
    _normalize_task_spec,
    _plan_mutation_targets,
    _publish_staged_case,
    _preflight_diagnostic,
    _preflight_key,
    _preflight_notes,
    _reconcile_input_artifacts,
    _resolve_max_tokens,
    _restore_workspace,
    _round_quality_key,
    _scrub_public_security_ids,
    _snapshot_workspace,
    _tester_repair_paths,
    _validate_mutant_candidate,
    _validate_seed_rows,
    load_agents,
)


def _validation(status="pass", ms=0.8, cs=1.0, baseline="pass", issues=0, differential="pass"):
    return {
        "status": status,
        "mutation_score": ms,
        "coverage_score": cs,
        "issues": [{"issue": "x"} for _ in range(issues)],
        "baseline_run": {"status": baseline},
        "differential": {"status": differential},
    }


def test_quality_key_prefers_passing_validation():
    good = _round_quality_key(_validation(status="pass"), {"overall_status": "pass"})
    bad = _round_quality_key(_validation(status="fail"), {"overall_status": "pass"})
    assert good > bad


def test_quality_key_prefers_passing_baseline_and_higher_mutation_score():
    # Mirrors the AES regression: round 0 (baseline passes, ms 0.8) must outrank
    # round 2 (baseline fails, ms 0.0), even though both fail overall validation.
    r0 = _round_quality_key(_validation(status="fail", ms=0.8, baseline="pass", differential="fail"),
                            {"overall_status": "fail"})
    r2 = _round_quality_key(_validation(status="fail", ms=0.0, baseline="fail", differential="fail"),
                            {"overall_status": "fail"})
    assert r0 > r2


def test_quality_key_prefers_fewer_issues_as_tiebreak():
    fewer = _round_quality_key(_validation(issues=1), {"overall_status": "pass"})
    more = _round_quality_key(_validation(issues=5), {"overall_status": "pass"})
    assert fewer > more


def test_snapshot_and_restore_roundtrip_and_clears_stale_files():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "case"
        (ws / "spec").mkdir(parents=True)
        (ws / "spec" / "task_spec.json").write_text("ROUND0")

        snap = _snapshot_workspace(ws, None)

        # Simulate a regressing later round: change a file and add a stale one.
        (ws / "spec" / "task_spec.json").write_text("ROUND2")
        (ws / "spec" / "stale.json").write_text("garbage")

        _restore_workspace(ws, snap)

        assert (ws / "spec" / "task_spec.json").read_text() == "ROUND0"
        assert not (ws / "spec" / "stale.json").exists()


def test_resolve_max_tokens_precedence():
    spec = {"max_tokens": 48000}
    defaults = {"max_tokens": 16000}

    # pipeline.yaml agent_max_tokens override wins
    assert _resolve_max_tokens("tester", spec, defaults, {"tester": 24000}) == 24000
    # falls back to the agent spec when no override
    assert _resolve_max_tokens("tester", spec, defaults, {}) == 48000
    assert _resolve_max_tokens("tester", spec, defaults, None) == 48000
    # falls back to defaults when the spec omits max_tokens
    assert _resolve_max_tokens("architect", {}, defaults, {}) == 16000
    # the override is per-agent — a different agent's entry doesn't apply
    assert _resolve_max_tokens("expert", spec, defaults, {"tester": 24000}) == 48000
    # a null entry is ignored (treated as unset)
    assert _resolve_max_tokens("tester", spec, defaults, {"tester": None}) == 48000


def test_load_agents_selects_bundle_mode_and_reasoning(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "prompts" / "p.md").write_text("prompt {{x}}")
    (tmp_path / "schemas" / "s.json").write_text(json.dumps({"type": "object"}))
    cfg = tmp_path / "config" / "agents.yaml"
    cfg.write_text(
        "defaults:\n  temperature: 0.1\n  max_tokens: 1000\n"
        "agents:\n"
        "  bundler:\n"
        "    model: m\n    prompt: prompts/p.md\n    schema: schemas/s.json\n"
        "    per_file: true\n"
        "  thinker:\n"
        "    model: m\n    prompt: prompts/p.md\n    schema: schemas/s.json\n"
        "    reasoning: {max_tokens: 8000}\n"
        "  plain:\n"
        "    model: m\n    prompt: prompts/p.md\n    schema: schemas/s.json\n"
    )

    agents = load_agents(object(), cfg, {})

    assert isinstance(agents["bundler"], FileBundleAgent)
    assert isinstance(agents["thinker"], JsonAgent)
    assert not isinstance(agents["thinker"], FileBundleAgent)
    assert agents["thinker"].config.reasoning == {"max_tokens": 8000}
    assert agents["plain"].config.reasoning is None


def test_all_repository_agent_configs_disable_reasoning():
    root = Path(__file__).resolve().parents[1]
    pipeline = yaml.safe_load((root / "config" / "pipeline.yaml").read_text())
    assert pipeline["openrouter"]["reasoning"] == {"enabled": False}

    for filename in ("agents.yaml", "agents_free.yaml", "agents_deepseek_v4_pro.yaml"):
        config = yaml.safe_load((root / "config" / filename).read_text())
        assert config["defaults"]["reasoning"] == {"enabled": False}
        assert all("reasoning" not in agent for agent in config["agents"].values())


def test_deepseek_v4_pro_config_uses_one_model_and_compatible_routing():
    root = Path(__file__).resolve().parents[1]
    agents = yaml.safe_load((root / "config" / "agents_deepseek_v4_pro.yaml").read_text())
    pipeline = yaml.safe_load((root / "config" / "deepseek_pipeline.yaml").read_text())

    assert {agent["model"] for agent in agents["agents"].values()} == {
        "deepseek/deepseek-v4-pro"
    }
    assert pipeline["agents_config"] == "config/agents_deepseek_v4_pro.yaml"
    assert pipeline["openrouter"]["reasoning"] == {"enabled": False}
    assert pipeline["openrouter"]["provider"] == {
        "sort": "price",
        "allow_fallbacks": True,
    }


def test_plan_mutation_targets_covers_every_sr_at_least_once():
    srs = ["SR1", "SR2", "SR3", "SR4", "SR5", "SR6", "SR7"]
    targets = _plan_mutation_targets(srs, ["FR1", "FR2"], requested=5)
    # requested is a floor, not a cap: all 7 SRs plus 2 FR slots.
    assert len(targets) == 9
    for sr in srs:
        assert sr in targets
    assert "FR1" in targets and "FR2" in targets


def test_plan_mutation_targets_fills_remaining_slots_with_frs():
    targets = _plan_mutation_targets(["SR1", "SR2"], ["FR1", "FR2", "FR3"], requested=5)
    assert len(targets) == 5
    assert targets[:2] == ["SR1", "SR2"]
    assert set(targets[2:]) <= {"FR1", "FR2", "FR3"}


def test_plan_mutation_targets_covers_every_fr_at_least_once():
    # Regression: the fill used to take min(2, len(FRs)) slots always starting
    # at FR1, so FR3/FR4 never received a targeting mutant in ANY case of a
    # run (seen as untested_requirements=['FR3','FR4'] on 19/21 cases).
    targets = _plan_mutation_targets(
        ["SR1", "SR2", "SR3", "SR4"], ["FR1", "FR2", "FR3", "FR4"], requested=5,
    )
    assert len(targets) == 8                      # every SR + every FR, once each
    for rid in ("FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"):
        assert rid in targets


def test_plan_mutation_targets_requested_beyond_full_coverage_cycles_frs():
    targets = _plan_mutation_targets(["SR1"], ["FR1", "FR2"], requested=5)
    assert targets == ["SR1", "FR1", "FR2", "FR1", "FR2"]


def test_plan_mutation_targets_without_frs_cycles_srs():
    targets = _plan_mutation_targets(["SR1"], [], requested=3)
    assert targets == ["SR1", "SR1", "SR1"]


def test_plan_mutation_targets_without_srs_uses_frs():
    targets = _plan_mutation_targets([], ["FR1", "FR2"], requested=3)
    assert len(targets) == 3
    assert set(targets) == {"FR1", "FR2"}


def test_plan_mutation_targets_empty_when_no_requirements():
    assert _plan_mutation_targets([], [], requested=5) == []


def test_snapshot_discards_previous_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "case"
        ws.mkdir(parents=True)
        (ws / "a.txt").write_text("v1")
        first = _snapshot_workspace(ws, None)
        (ws / "a.txt").write_text("v2")
        second = _snapshot_workspace(ws, first)
        # The first snapshot's holder is removed; the second reflects v2.
        assert not first.parent.exists()
        assert (second / "a.txt").read_text() == "v2"


def test_deterministic_retain_requires_all_gates():
    passing = _validation(status="pass", ms=0.8, cs=0.9)
    assert _deterministic_retain(passing, {"overall_status": "pass"}, 0.5, 0.8) is True
    # A synthetic 'warning' analyzer report (LLM call failed) still retains.
    assert _deterministic_retain(passing, {"overall_status": "warning"}, 0.5, 0.8) is True
    assert _deterministic_retain(passing, {"overall_status": "fail"}, 0.5, 0.8) is False
    assert _deterministic_retain(_validation(status="fail"), {"overall_status": "pass"}, 0.5, 0.8) is False
    assert _deterministic_retain(_validation(ms=0.4), {"overall_status": "pass"}, 0.5, 0.8) is False
    assert _deterministic_retain(_validation(cs=0.7), {"overall_status": "pass"}, 0.5, 0.8) is False
    # Missing analyzer report or scores rank as failing, not as a crash.
    assert _deterministic_retain(_validation(ms=None), {"overall_status": "pass"}, 0.5, 0.8) is False
    assert _deterministic_retain(passing, None, 0.5, 0.8) is False


def test_preflight_key_prefers_golden_acceptance_over_baseline_rejection():
    both = _preflight_key({"golden_run": {"ok": True}, "vulnerable_run": {"ok": True}})
    golden_only = _preflight_key({"golden_run": {"ok": True}, "vulnerable_run": {"ok": False}})
    vuln_only = _preflight_key({"golden_run": {"ok": False}, "vulnerable_run": {"ok": True}})
    neither = _preflight_key({"golden_run": {"ok": False}, "vulnerable_run": {"ok": False}})
    assert both > golden_only > vuln_only > neither
    # Missing arms rank lowest rather than raising.
    assert _preflight_key({}) == neither


def test_preflight_key_keeps_partial_repair_that_removes_crash():
    crashing = {
        "golden_run": {"ok": False, "status": "fail", "stderr": "Traceback (most recent call last)"},
        "vulnerable_run": {"ok": False, "status": "fail", "stderr": "Traceback (most recent call last)"},
    }
    repaired = {
        "golden_run": {"ok": False, "status": "pass", "stdout": "[TEST] PASS: FR1"},
        "vulnerable_run": {"ok": False, "status": "fail", "stdout": "[TEST] FAIL: SR1: bad"},
    }
    assert _preflight_key(repaired) > _preflight_key(crashing)


def test_preflight_key_prefers_more_passes_with_same_marker_count():
    initial = {
        "golden_run": {"ok": False, "status": "fail", "stdout": (
            "[TEST] PASS: FR1\n[TEST] FAIL: SR1: bad\n[TEST] FAIL: SR2: bad"
        )},
        "vulnerable_run": {"ok": True},
    }
    repaired = {
        "golden_run": {"ok": False, "status": "fail", "stdout": (
            "[TEST] PASS: FR1\n[TEST] PASS: SR1\n[TEST] FAIL: SR2: bad"
        )},
        "vulnerable_run": {"ok": True},
    }
    assert _preflight_key(repaired) > _preflight_key(initial)


def test_preflight_stops_after_repeated_failure_signature(tmp_path, monkeypatch):
    failure = {
        "status": "fail",
        "failure_class": "golden_rejected",
        "failure_signature": "same",
        "golden_run": {"ok": False},
        "vulnerable_run": {"ok": True},
    }
    monkeypatch.setattr(orchestrator_module, "_compute_differential_validation", lambda *args, **kwargs: failure)
    monkeypatch.setattr(orchestrator_module, "_write_tester_bundle", lambda *args, **kwargs: None)

    class Tester:
        calls = 0

        def run(self, variables):
            self.calls += 1
            return {"manifest": [{"path": "evaluation/evaluate.py", "purpose": "x"}], "files": []}

    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {"tester_preflight_retries": 3}}
    orch.runner = object()
    tester = Tester()
    orch.agents = {"tester": tester}
    ws = Workspace(tmp_path)
    bundle, ok, meta = orch._tester_preflight(ws, {}, {}, {"files": []}, {})
    assert bundle is not None
    assert ok is False
    assert tester.calls == 1
    assert meta["repeated_signature"] is True


def test_preflight_keeps_targeted_repair_that_fixes_crash(tmp_path, monkeypatch):
    crashing = {
        "status": "fail", "failure_class": "evaluator_error", "failure_signature": "crash",
        "golden_run": {"ok": False, "status": "fail", "stderr": "Traceback (most recent call last)"},
        "vulnerable_run": {"ok": False, "status": "fail", "stderr": "Traceback (most recent call last)"},
    }
    partial = {
        "status": "fail", "failure_class": "golden_rejected", "failure_signature": "requirements",
        "golden_run": {"ok": False, "status": "pass", "stdout": "[TEST] PASS: FR1"},
        "vulnerable_run": {"ok": False, "status": "fail", "stdout": "[TEST] FAIL: SR1: bad"},
    }
    results = iter([crashing, partial])
    monkeypatch.setattr(orchestrator_module, "_compute_differential_validation", lambda *args, **kwargs: next(results))
    monkeypatch.setattr(orchestrator_module, "_write_tester_bundle", lambda *args, **kwargs: None)
    initial = {
        "manifest": [{"path": "evaluation/evaluate.py", "purpose": "grader"}],
        "files": [{"path": "evaluation/evaluate.py", "content": "broken"}],
    }
    candidate = {**initial, "files": [{"path": "evaluation/evaluate.py", "content": "repaired"}]}

    class Tester:
        def repair_files(self, variables, previous, paths):
            assert paths == ["evaluation/evaluate.py"]
            return candidate

    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {"tester_preflight_retries": 1}}
    orch.runner = object()
    orch.agents = {"tester": Tester()}
    bundle, ok, meta = orch._tester_preflight(Workspace(tmp_path), {}, {}, initial, {})
    assert ok is False
    assert bundle == candidate
    assert meta["failure_class"] == "golden_rejected"


def test_preflight_does_not_retry_submission_invariant(tmp_path, monkeypatch):
    failure = {
        "status": "fail",
        "failure_class": "submission_invariant",
        "failure_signature": "invariant",
        "golden_run": None,
        "vulnerable_run": None,
    }
    monkeypatch.setattr(orchestrator_module, "_compute_differential_validation", lambda *args, **kwargs: failure)

    class Tester:
        def run(self, variables):
            raise AssertionError("Tester must not be called")

    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {"tester_preflight_retries": 3}}
    orch.runner = object()
    orch.agents = {"tester": Tester()}
    _, ok, meta = orch._tester_preflight(Workspace(tmp_path), {}, {}, {"files": []}, {})
    assert ok is False
    assert meta["attempts"] == 0


def test_preflight_retries_tester_owned_setup_error(tmp_path, monkeypatch):
    failure = {
        "status": "fail",
        "failure_class": "setup_error",
        "failure_signature": "setup",
        "golden_run": {"ok": False, "status": "fail", "stdout": "[TEST] FAIL: SETUP: import failed"},
        "vulnerable_run": {"ok": False, "status": "fail", "stdout": "[TEST] FAIL: SETUP: import failed"},
    }
    monkeypatch.setattr(orchestrator_module, "_compute_differential_validation", lambda *args, **kwargs: failure)
    monkeypatch.setattr(orchestrator_module, "_write_tester_bundle", lambda *args, **kwargs: None)

    class Tester:
        calls = 0

        def run(self, variables):
            self.calls += 1
            return {"manifest": [{"path": "evaluation/evaluate.py", "purpose": "grader"}], "files": []}

    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {"tester_preflight_retries": 1}}
    orch.runner = object()
    tester = Tester()
    orch.agents = {"tester": tester}
    _, ok, meta = orch._tester_preflight(Workspace(tmp_path), {}, {}, {"files": []}, {})
    assert ok is False
    assert tester.calls == 1
    assert meta["attempts"] == 1


def test_preflight_notes_include_stderr():
    diff = {
        "failure_class": "evaluator_error",
        "golden_run": {"ok": False, "stdout": "", "stderr": "ModuleNotFoundError: private"},
        "vulnerable_run": {"ok": False, "stdout": "[TEST] FAIL: SR1: bad", "stderr": ""},
    }
    notes = _preflight_notes(diff)
    assert "ModuleNotFoundError: private" in notes
    assert "did not CLEANLY REJECT" in notes
    assert _preflight_diagnostic(diff) == "ModuleNotFoundError: private"


def test_tester_repair_paths_select_only_evaluator():
    bundle = {"manifest": [
        {"path": "evaluation/README.md", "purpose": "docs"},
        {"path": "evaluation/evaluate.py", "purpose": "grader"},
        {"path": "evaluation/private/ground_truth.py", "purpose": "oracle constants"},
        {"path": "evaluation/private/tb.v", "purpose": "simulation evidence testbench"},
    ]}
    paths = _tester_repair_paths({"failure_class": "golden_rejected"}, bundle)
    assert paths == ["evaluation/evaluate.py"]


def test_tester_repair_paths_include_implicated_testbench():
    bundle = {"manifest": [
        {"path": "evaluation/evaluate.py", "purpose": "grader"},
        {"path": "evaluation/tb_mac_top.v", "purpose": "behavioral testbench"},
        {"path": "evaluation/private/oracle.py", "purpose": "reference"},
    ]}
    diff = {
        "golden_run": {"stdout": "[TEST] FAIL: FR1: compile failed: evaluation/tb_mac_top.v:178: syntax error"},
        "vulnerable_run": {},
    }
    assert _tester_repair_paths(diff, bundle) == [
        "evaluation/tb_mac_top.v", "evaluation/evaluate.py",
    ]


def test_deterministic_report_mutant_handles_json_validity_requirement():
    spec = {"public_spec": {"functional_requirements": [{
        "id": "FR1", "requirement": "The submitted report must be valid, parseable JSON.",
    }]}}
    mutant = _deterministic_report_mutant(spec, "FR1", {"submission/report.json"})
    assert mutant is not None
    assert mutant["target_requirement_id"] == "FR1"
    assert mutant["files"] == [{"path": "submission/report.json", "content": "{\n"}]


def test_deterministic_report_mutant_does_not_guess_other_requirements():
    spec = {"public_spec": {"functional_requirements": [{
        "id": "FR2", "requirement": "The report identifies the correct node.",
    }]}}
    assert _deterministic_report_mutant(spec, "FR2", {"submission/report.json"}) is None


def test_publish_staged_case_is_atomic_and_collision_safe(tmp_path):
    staging = tmp_path / ".case.staging-1"
    staging.mkdir()
    (staging / "case_manifest.json").write_text("{}")
    desired = tmp_path / "case"
    published = _publish_staged_case(staging, desired)
    assert published == desired
    assert published.is_dir()
    assert not staging.exists()

    second = tmp_path / ".case.staging-2"
    second.mkdir()
    collision = _publish_staged_case(second, desired)
    assert collision.name == "case_gen001"
    assert desired.is_dir() and collision.is_dir()


def test_case_manifest_distinguishes_quality_failure(tmp_path):
    ws = Workspace(tmp_path)
    ws.write_json("reports/quality_report.json", {"overall_status": "fail"})
    manifest = _build_case_manifest(
        ws, {"task_id": "case", "domain_id": "rtl_trojan_detection"},
        {"source_round": 0, "final_attempted_round": 2},
    )
    assert manifest["status"] == "quality_failed"
    assert manifest["quality_status"] == "fail"


def test_case_budget_stops_before_next_llm_call():
    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {
        "max_llm_calls_per_case": 2,
        "max_total_tokens_per_case": 100,
    }}
    orch._active_case_usage_start = {"calls": 5, "tokens": 1000}
    orch.llm = SimpleNamespace(usage_totals={
        "calls": 6, "prompt_tokens": 1020, "completion_tokens": 10,
    })
    orch._enforce_case_budget()

    orch.llm.usage_totals["calls"] = 7
    with pytest.raises(RuntimeError, match="call budget exceeded"):
        orch._enforce_case_budget()

    orch.llm.usage_totals.update(calls=6, prompt_tokens=1080, completion_tokens=20)
    with pytest.raises(RuntimeError, match="token budget exceeded"):
        orch._enforce_case_budget()


def test_generate_records_failed_attempt_in_run_manifest(tmp_path):
    seed_path = tmp_path / "seeds.yaml"
    seed_path.write_text(yaml.safe_dump([{
        "seed_id": "broken", "domain_id": "hls_security_codegen", "title": "Broken",
        "objective": "test failure", "constraints": ["remain deterministic"], "threat_model": "none",
        "ground_truth": "none",
    }]))
    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {"expand_seeds": False, "max_repair_rounds": 0}}
    orch.config_path = tmp_path / "pipeline.yaml"
    orch.llm = SimpleNamespace(usage_totals={
        "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
    })

    def fail_generation(*args, **kwargs):
        raise RuntimeError("synthetic generation failure")

    orch._generate_one = fail_generation
    output = tmp_path / "output"
    with pytest.raises(RuntimeError, match="All 1 case generation attempt"):
        orch.generate(seed_path, output)

    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["cases"] == [{
        "label": "broken",
        "status": "failed",
        "published_path": None,
        "quality_status": None,
        "error": "synthetic generation failure",
    }]


def test_generate_marks_quality_failed_publication_and_partial_run(tmp_path):
    seed_path = tmp_path / "seeds.yaml"
    seed_path.write_text(yaml.safe_dump([{
        "seed_id": "weak", "domain_id": "hls_security_codegen", "title": "Weak",
        "objective": "test quality status", "constraints": ["remain deterministic"],
        "threat_model": "none", "ground_truth": "none",
    }]))
    orch = object.__new__(BenchGenOrchestrator)
    orch.pipeline_cfg = {"pipeline": {"expand_seeds": False, "max_repair_rounds": 0}}
    orch.config_path = tmp_path / "pipeline.yaml"
    orch.llm = SimpleNamespace(usage_totals={
        "calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
    })
    output = tmp_path / "output"

    def generate_quality_failure(idea, out_root, max_repair):
        case = out_root / "weak"
        (case / "reports").mkdir(parents=True)
        (case / "reports" / "quality_report.json").write_text('{"overall_status":"fail"}')
        (case / "reports" / "selection.json").write_text(
            '{"source_round":0,"final_attempted_round":0}'
        )
        return case

    orch._generate_one = generate_quality_failure
    assert orch.generate(seed_path, output) == [output / "weak"]
    manifest = json.loads((output / "run_manifest.json").read_text())
    assert manifest["status"] == "partial"
    assert manifest["cases"][0]["status"] == "published_quality_failed"


def test_load_agents_reads_plan_max_tokens(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "prompts" / "p.md").write_text("prompt {{x}}")
    (tmp_path / "schemas" / "s.json").write_text(json.dumps({"type": "object"}))
    cfg = tmp_path / "config" / "agents.yaml"
    cfg.write_text(
        "defaults:\n  temperature: 0.1\n  max_tokens: 1000\n"
        "agents:\n"
        "  planner:\n"
        "    model: m\n    prompt: prompts/p.md\n    schema: schemas/s.json\n"
        "    per_file: true\n    plan_max_tokens: 9000\n"
        "  vanilla:\n"
        "    model: m\n    prompt: prompts/p.md\n    schema: schemas/s.json\n"
    )
    agents = load_agents(object(), cfg, {})
    assert agents["planner"].config.plan_max_tokens == 9000
    assert agents["vanilla"].config.plan_max_tokens is None


def test_reconcile_input_artifacts_uses_shipped_inputs():
    # The gen001 failure mode: the spec declared the case-root README.md as an
    # input artifact, so evaluate.py opened inputs/README.md and died at SETUP.
    spec = {"public_spec": {"input_artifacts": ["sbox_kernel.c", "README.md"]}}
    bundle = {"files": [
        {"path": "README.md", "content": "case readme"},
        {"path": "metadata.json", "content": "{}"},
        {"path": "inputs/sbox_kernel.c", "content": "int f;"},
    ]}
    out = _reconcile_input_artifacts(spec, bundle)
    assert out["public_spec"]["input_artifacts"] == ["sbox_kernel.c"]


def test_reconcile_input_artifacts_keeps_spec_when_nothing_shipped():
    spec = {"public_spec": {"input_artifacts": ["kernel.c"]}}
    out = _reconcile_input_artifacts(spec, {"files": [{"path": "README.md", "content": ""}]})
    assert out["public_spec"]["input_artifacts"] == ["kernel.c"]


def test_scrub_public_security_ids_strips_cwe_and_sr_tokens():
    removed: list[str] = []
    text = ("The specific CWE identifiers targeted (e.g., CWE-226 sensitive information "
            "uncleared, CWE-668 exposure) must stay hidden; see SR2 for details.")
    scrubbed = _scrub_public_security_ids(text, removed)
    assert "CWE-226" not in scrubbed and "CWE-668" not in scrubbed and "SR2" not in scrubbed
    assert "sensitive information uncleared" in scrubbed
    assert set(removed) == {"CWE-226", "CWE-668", "SR2"}


def test_scrub_public_security_ids_recurses_and_preserves_clean_values():
    removed: list[str] = []
    value = {"constraints": ["no CWE-208 timing leak", "plain constraint"], "count": 3}
    scrubbed = _scrub_public_security_ids(value, removed)
    assert scrubbed["constraints"][0] == "no timing leak"
    assert scrubbed["constraints"][1] == "plain constraint"
    assert scrubbed["count"] == 3
    assert removed == ["CWE-208"]


def test_normalize_task_spec_scrubs_public_but_not_hidden_or_filenames():
    from agentic_bench_gen.domains import profile_as_prompt_context

    ctx = profile_as_prompt_context("hls_security_codegen")
    raw = {
        "task_id": "t",
        "public_spec": {
            "objective": "Harden the kernel (relates to CWE-208).",
            "input_artifacts": ["kernel.c"],
            "functional_requirements": [{"id": "FR1", "requirement": "correct output"}],
            "constraints": ["avoid the CWE-200 exposure pattern"],
        },
        "hidden_spec": {"cwe_ids": ["CWE-208"], "security_requirements": [
            {"id": "SR1", "requirement": "no leak", "detection_strategy": "harness"}
        ]},
    }
    spec = _normalize_task_spec(raw, {"seed_id": "t"}, ctx)
    public_text = json.dumps(spec["public_spec"])
    assert "CWE" not in public_text
    assert spec["public_spec"]["input_artifacts"] == ["kernel.c"]
    assert spec["hidden_spec"]["cwe_ids"] == ["CWE-208"]


def test_restore_workspace_preserves_round_stamped_reports():
    # Keep-best restores an earlier snapshot; the later rounds' round-stamped
    # reports (the evidence of WHY they regressed) must survive the wipe.
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "case"
        (ws / "reports").mkdir(parents=True)
        (ws / "reports" / "validation_report.json").write_text('{"round": 0}')
        (ws / "reports" / "validation_report_r0.json").write_text('{"round": 0}')
        (ws / "reports" / "arbiter_decision_r0.json").write_text('{"round": 0}')

        snap = _snapshot_workspace(ws, None)

        # Later rounds overwrite canonical reports and add their stamped ones.
        (ws / "reports" / "validation_report.json").write_text('{"round": 2}')
        (ws / "reports" / "validation_report_r1.json").write_text('{"round": 1}')
        (ws / "reports" / "validation_report_r2.json").write_text('{"round": 2}')
        (ws / "reports" / "arbiter_decision_r1.json").write_text('{"round": 1}')
        (ws / "reports" / "arbiter_decision_r2.json").write_text('{"round": 2}')

        _restore_workspace(ws, snap)

        # Canonical report reflects the restored round...
        assert json.loads((ws / "reports" / "validation_report.json").read_text()) == {"round": 0}
        # ...while every round's stamped history survives.
        for name, expected in [
            ("validation_report_r0.json", 0), ("validation_report_r1.json", 1),
            ("validation_report_r2.json", 2), ("arbiter_decision_r0.json", 0),
            ("arbiter_decision_r1.json", 1), ("arbiter_decision_r2.json", 2),
        ]:
            assert json.loads((ws / "reports" / name).read_text()) == {"round": expected}, name


def _prior_mutants():
    return [
        {"mutant_id": "m_sr1", "operator": "condition_negation", "target_requirement_id": "SR1",
         "expected_detection": "x", "files": [{"path": "inputs/a.c", "content": "sr1"}]},
        {"mutant_id": "m_sr2", "operator": "constant_change", "target_requirement_id": "SR2",
         "expected_detection": "y", "files": [{"path": "inputs/a.c", "content": "sr2"}]},
        {"mutant_id": "m_fr1", "operator": "operator_swap", "target_requirement_id": "FR1",
         "expected_detection": "z", "files": [{"path": "inputs/a.c", "content": "fr1"}]},
    ]


def test_plan_mutant_repair_keeps_detected_and_regenerates_flagged():
    from agentic_bench_gen.orchestrator import _plan_mutant_repair

    validation = {"uncovered_requirements": ["SR1"], "dead_checks": [], "untested_requirements": ["SR3"]}
    kept, targets, failed_pairs = _plan_mutant_repair(_prior_mutants(), validation)
    assert [m["mutant_id"] for m in kept] == ["m_sr2", "m_fr1"]
    assert targets == ["SR1", "SR3"]
    # The defective SR1 mutant's combination is forbidden; SR3 never had one.
    assert failed_pairs == {("condition_negation", "SR1")}


def test_plan_mutant_repair_falls_back_to_full_regen():
    from agentic_bench_gen.orchestrator import _plan_mutant_repair

    # Nothing flagged, no prior mutants, or no validation: selective repair
    # does not apply and the caller regenerates everything.
    assert _plan_mutant_repair(_prior_mutants(), {"uncovered_requirements": []}) is None
    assert _plan_mutant_repair([], {"uncovered_requirements": ["SR1"]}) is None
    assert _plan_mutant_repair(_prior_mutants(), None) is None


def test_slim_mutation_for_arbiter_ships_files_only_for_flagged_targets():
    from agentic_bench_gen.orchestrator import _slim_mutation_for_arbiter

    bundle = {"mutants": _prior_mutants(), "generation_failures": [{"target_requirement_id": "SR4", "error": "e"}]}
    validation = {"uncovered_requirements": ["SR1"], "dead_checks": ["SR2"]}
    slim = _slim_mutation_for_arbiter(bundle, validation)
    by_id = {m["mutant_id"]: m for m in slim["mutants"]}
    assert "files" in by_id["m_sr1"] and "files" in by_id["m_sr2"]
    assert "files" not in by_id["m_fr1"] and "expected_detection" not in by_id["m_fr1"]
    assert by_id["m_fr1"]["target_requirement_id"] == "FR1"
    assert slim["generation_failures"] == bundle["generation_failures"]


def test_arbiter_schema_accepts_mutants_revision():
    from agentic_bench_gen.schemas import load_schema, validate_or_raise

    schema = load_schema(Path(__file__).resolve().parents[1] / "schemas" / "arbiter_decision.schema.json")
    validate_or_raise({
        "retain_case": False,
        "observed_mutation_score": 0.833,
        "artifact_to_revise": "mutants",
        "root_cause": "mutation_issue",
        "rationale": "the SR1 mutant is semantically equivalent to the golden",
        "revision_instructions": "regenerate the SR1 mutant with an observable defect",
    }, schema)


def test_seed_validation_rejects_duplicate_ids_and_unknown_domains():
    seed = {
        "seed_id": "s1", "domain_id": "hls_security_codegen", "title": "t",
        "objective": "o", "constraints": ["c"], "threat_model": "tm", "ground_truth": "gt",
    }
    assert _validate_seed_rows([seed]) == [seed]
    try:
        _validate_seed_rows([seed, dict(seed)])
    except ValueError as exc:
        assert "Duplicate seed_id" in str(exc)
    else:
        raise AssertionError("duplicate seed_id was accepted")

    bad = dict(seed, seed_id="s2", domain_id="not_a_domain")
    try:
        _validate_seed_rows([bad])
    except ValueError as exc:
        assert "Unknown domain" in str(exc)
    else:
        raise AssertionError("unknown domain was accepted")


def test_mutator_candidate_must_match_target_and_submission_path():
    valid = {"mutants": [{
        "mutant_id": "m1", "operator": "constant_change",
        "target_requirement_id": "SR1", "expected_detection": "x",
        "files": [{"path": "inputs/code.c", "content": "bad"}],
    }]}
    assert _validate_mutant_candidate(valid, "SR1", {"inputs/code.c"})["mutant_id"] == "m1"

    wrong_target = {"mutants": [dict(valid["mutants"][0], target_requirement_id="FR1")]}
    try:
        _validate_mutant_candidate(wrong_target, "SR1", {"inputs/code.c"})
    except ValueError as exc:
        assert "required target" in str(exc)
    else:
        raise AssertionError("wrong target was accepted")

    unsafe = {"mutants": [dict(valid["mutants"][0], files=[{"path": "../code.c", "content": "bad"}])]}
    try:
        _validate_mutant_candidate(unsafe, "SR1", {"inputs/code.c"})
    except ValueError as exc:
        assert "unsafe path" in str(exc)
    else:
        raise AssertionError("unsafe mutant path was accepted")
