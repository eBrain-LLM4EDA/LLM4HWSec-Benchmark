from __future__ import annotations

import argparse
from pathlib import Path

from .orchestrator import BenchGenOrchestrator
from .utils import read_json, read_yaml
from .validator import validate_benchmark_case
from .workspace import Workspace
from .logio import console

def main() -> None:
    parser = argparse.ArgumentParser(prog="agentic-bench-gen")
    parser.add_argument("--config", default="config/pipeline.yaml", help="Pipeline YAML path.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="Generate benchmark cases from seed YAML.")
    gen.add_argument("--seed", required=True, help="Seed YAML file.")
    gen.add_argument("--out", required=True, help="Output directory.")

    val = sub.add_parser("validate", help="Validate an existing generated case.")
    val.add_argument("--case", required=True, help="Generated case directory.")

    args = parser.parse_args()
    if args.cmd == "generate":
        orch = BenchGenOrchestrator(args.config)
        paths = orch.generate(args.seed, args.out)
        for path in paths:
            console.print(f"[green]Generated:[/green] {path}")
    elif args.cmd == "validate":
        root = Path(args.case).resolve()
        task_spec = read_json(root / "spec" / "task_spec.json")
        artifact_bundle = read_json(root / "artifacts" / "artifact_bundle.json")
        expert_bundle = read_json(root / "expert" / "expert_bundle.json")
        tester_bundle = read_json(root / "tests" / "tester_bundle.json")
        mutation_path = root / "mutants" / "mutation_bundle.json"
        mutation_bundle = read_json(mutation_path) if mutation_path.exists() else None
        # Build the same runner the generation pipeline uses so `validate`
        # reproduces the dynamic (baseline/differential/mutation) verdict rather
        # than the static estimate.
        cfg_path = Path(args.config)
        exec_cfg = read_yaml(cfg_path).get("execution", {}) if cfg_path.exists() else {}
        runner = BenchGenOrchestrator._build_runner(exec_cfg)
        runner.check_available()
        report = validate_benchmark_case(
            task_spec, artifact_bundle, tester_bundle, expert_bundle, mutation_bundle,
            ws=Workspace(root), runner=runner,
        )
        console.print_json(data=report)


if __name__ == "__main__":
    main()
