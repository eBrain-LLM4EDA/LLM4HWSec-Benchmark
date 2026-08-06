#!/usr/bin/env python3
"""Top up a published case's mutation bundle so every requirement has a
targeting mutant, then re-validate.

Why this exists
---------------
`_plan_mutation_targets` in the orchestrator guarantees one mutant per SR and
per FR ("mutants_per_case acts as a floor, never a cap"). Cases generated before
that fix used a planner that filled only min(2, len(FRs)) FR slots starting at
FR1, deterministically starving FR3+. Those cases ship with fewer mutants than
requirements, so the starved requirements can never demonstrate discrimination
and validation permanently reports `untested_requirement`.

This script re-runs ONLY the Mutator for the missing targets. Existing mutants
are kept as-is, so nothing that already discriminates is put at risk.

Usage
-----
  python tools/topup_mutants.py --case testcases/B__foo            # dry run
  python tools/topup_mutants.py --case testcases/B__foo --apply
  python tools/topup_mutants.py --all-b --apply                    # every B__ case
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agentic_bench_gen.domains import get_domain_profile, profile_as_prompt_context, submission_paths
from agentic_bench_gen.logio import console
from agentic_bench_gen.orchestrator import (
    BenchGenOrchestrator,
    _deterministic_report_mutant,
    _plan_mutation_targets,
    _requirement_id_list,
    _slim_artifact_for_prompt,
    _slim_expert_for_prompt,
    _validate_mutant_candidate,
)
from agentic_bench_gen.utils import read_json
from agentic_bench_gen.validator import validate_benchmark_case
from agentic_bench_gen.workspace import Workspace


def load_env(root: Path) -> None:
    """Populate OPENROUTER_* from .env when not already exported."""
    env = root / ".env"
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def plan_for(case: Path):
    ts = read_json(case / "spec/task_spec.json")
    mb = (read_json(case / "mutants/mutation_bundle.json")
          if (case / "mutants/mutation_bundle.json").exists() else {"mutants": []})
    existing = mb.get("mutants") or []
    have = [str(m.get("target_requirement_id", "")) for m in existing]
    sr = _requirement_id_list(ts, "hidden_spec", "security_requirements")
    fr = _requirement_id_list(ts, "public_spec", "functional_requirements")
    want = _plan_mutation_targets(sr, fr, 0)          # floor 0 => exactly one per requirement
    missing = [t for t in want if t not in have]
    return ts, mb, existing, want, missing


def topup(orch, case: Path, apply: bool) -> bool:
    ts, mb, existing, want, missing = plan_for(case)
    print(f"\n=== {case.relative_to(ROOT)}")
    print(f"    requirements={len(want)} existing_mutants={len(existing)} missing={missing or 'none'}")
    if not missing:
        print("    nothing to do")
        return False
    if not apply:
        print(f"    DRY RUN: would generate {len(missing)} mutant(s) for {missing}")
        return False

    domain_id = ts.get("domain_id", "")
    dctx = profile_as_prompt_context(domain_id)
    artifact_bundle = read_json(case / "artifacts/artifact_bundle.json")
    expert_bundle = read_json(case / "expert/expert_bundle.json")
    tester_bundle = read_json(case / "tests/tester_bundle.json")
    allowed = set(submission_paths(
        get_domain_profile(domain_id),
        [str(x) for x in ts.get("public_spec", {}).get("input_artifacts", [])],
    ))
    bundle = {"mutants": list(existing)}
    used = {(str(m.get("operator", "")), str(m.get("target_requirement_id", ""))) for m in existing}

    for i, target in enumerate(missing, 1):
        print(f"    -> mutant {i}/{len(missing)} target={target}")
        fb = _deterministic_report_mutant(ts, target, allowed)
        if fb is not None and (fb["operator"], target) not in used:
            bundle["mutants"].append(fb)
            used.add((fb["operator"], target))
            print("       deterministic malformed-report mutant")
            continue
        for attempt in range(3):
            try:
                out = orch.agents["mutator"].run({
                    "task_spec_json": ts,
                    "submission_contract": dctx.get("submission_contract", ""),
                    "artifact_bundle_json": _slim_artifact_for_prompt(artifact_bundle),
                    "expert_bundle_json": _slim_expert_for_prompt(expert_bundle),
                    "requirement_map_json": [
                        {"requirement_id": m.get("requirement_id"),
                         "requirement_type": m.get("requirement_type")}
                        for m in (tester_bundle or {}).get("requirement_map", [])
                    ],
                    "required_target_requirement_id": target,
                    "repair_notes": "",
                    "previous_mutations": [
                        {"mutant_id": m.get("mutant_id"), "operator": m.get("operator"),
                         "target_requirement_id": m.get("target_requirement_id")}
                        for m in bundle["mutants"]
                    ],
                    "forbidden_combinations": [
                        {"operator": o, "target_requirement_id": t} for o, t in used
                    ],
                })
                mut = _validate_mutant_candidate(out, target, allowed)
            except Exception as exc:
                print(f"       attempt {attempt+1} failed: {str(exc)[:110]}")
                continue
            pair = (str(mut.get("operator", "")), str(mut.get("target_requirement_id", "")))
            if pair in used and attempt < 2:
                continue
            used.add(pair)
            bundle["mutants"].append(mut)
            break
        else:
            bundle.setdefault("generation_failures", []).append(
                {"target_requirement_id": target, "error": "3 attempts failed"})
            print(f"       GAVE UP on {target}")

    ws = Workspace(case)
    ws.write_json("mutants/mutation_bundle.json", bundle)
    rep = validate_benchmark_case(ts, artifact_bundle, tester_bundle, expert_bundle,
                                  bundle, ws, runner=orch.runner)
    ws.write_json("reports/validation_report.json", rep)
    d = rep.get("differential") or {}
    print(f"    RESULT status={rep.get('status')} diff={d.get('status')} "
          f"mutation={rep.get('mutation_score')} meaningful={rep.get('mutation_score_meaningful')}")
    print(f"    issues={sorted({i.get('issue') for i in (rep.get('issues') or [])}) or 'none'}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=[])
    ap.add_argument("--all-b", action="store_true", help="every testcases/B__* case")
    ap.add_argument("--config", default="config/pipeline.yaml")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    cases = [ROOT / c for c in a.case]
    if a.all_b:
        cases += sorted(d for d in (ROOT / "testcases").iterdir()
                        if d.is_dir() and d.name.startswith("B__"))
    if not cases:
        ap.error("pass --case <path> or --all-b")

    load_env(ROOT)
    if a.apply and not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("OPENROUTER_API_KEY not set (and not found in .env)")

    orch = BenchGenOrchestrator(ROOT / a.config) if a.apply else None
    if orch:
        orch.runner.check_available()

    changed = 0
    for c in cases:
        if not (c / "spec/task_spec.json").is_file():
            print(f"skip (not a case): {c}")
            continue
        changed += bool(topup(orch, c, a.apply))
    print(f"\n{'updated' if a.apply else 'would update'} {changed} case(s)")


if __name__ == "__main__":
    main()
