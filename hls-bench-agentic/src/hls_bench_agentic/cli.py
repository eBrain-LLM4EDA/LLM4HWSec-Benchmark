from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

console = Console()


def _cmd_generate(args: argparse.Namespace) -> None:
    from .orchestrator import HLSBenchOrchestrator
    orch = HLSBenchOrchestrator(args.config)
    paths = orch.generate(args.seed, args.out)
    console.print(f"\n[bold green]Generated {len(paths)} task workspace(s).[/bold green]")


def _cmd_evaluate(args: argparse.Namespace) -> None:
    from .evaluator import evaluate_target_model
    out = evaluate_target_model(
        task_dir=args.task,
        model=args.model,
        out_dir=args.out,
        config_path=args.config,
    )
    console.print(f"\n[bold green]Evaluation written to:[/bold green] {out}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="hlsbench",
        description="HLS Secure Benchmark — agentic dataset generator and evaluator.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # -- generate ---------------------------------------------------------
    gen = sub.add_parser("generate", help="Generate HLS security benchmark tasks from seeds.")
    gen.add_argument("--seed", required=True, metavar="FILE", help="YAML seed file (see examples/cwe_seeds.yaml).")
    gen.add_argument("--out", required=True, metavar="DIR", help="Output directory for task workspaces.")
    gen.add_argument(
        "--config",
        default=str(Path(__file__).parent.parent.parent.parent / "config" / "pipeline.yaml"),
        metavar="FILE",
        help="Pipeline YAML config (default: config/pipeline.yaml relative to project root).",
    )

    # -- evaluate ---------------------------------------------------------
    ev = sub.add_parser("evaluate", help="Evaluate a target model on a generated task.")
    ev.add_argument("--task", required=True, metavar="DIR", help="Generated task directory.")
    ev.add_argument("--model", required=True, metavar="MODEL_ID", help="OpenRouter model id (e.g. anthropic/claude-3.5-sonnet).")
    ev.add_argument("--out", required=True, metavar="DIR", help="Evaluation output directory.")
    ev.add_argument(
        "--config",
        default=str(Path(__file__).parent.parent.parent.parent / "config" / "pipeline.yaml"),
        metavar="FILE",
        help="Pipeline YAML config.",
    )

    args = parser.parse_args()

    try:
        if args.cmd == "generate":
            _cmd_generate(args)
        elif args.cmd == "evaluate":
            _cmd_evaluate(args)
    except RuntimeError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
