from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from .evaluator import evaluate_target_model
from .orchestrator import HLSBenchmarkOrchestrator


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="hlssecbench")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="Generate HLS security benchmark tasks.")
    gen.add_argument("--seed", required=True, help="YAML seed file.")
    gen.add_argument("--out", required=True, help="Output directory.")
    gen.add_argument("--config", default="config/pipeline.yaml", help="Pipeline YAML config.")

    ev = sub.add_parser("evaluate", help="Evaluate a target model on a generated task.")
    ev.add_argument("--task", required=True, help="Generated task directory.")
    ev.add_argument("--model", required=True, help="OpenRouter model id.")
    ev.add_argument("--out", required=True, help="Evaluation output directory.")
    ev.add_argument("--config", default="config/pipeline.yaml", help="Pipeline YAML config.")

    args = parser.parse_args()

    if args.cmd == "generate":
        orch = HLSBenchmarkOrchestrator(args.config)
        orch.generate(args.seed, args.out)
    elif args.cmd == "evaluate":
        evaluate_target_model(
            task_dir=args.task,
            model=args.model,
            out_dir=args.out,
            config_path=args.config,
        )


if __name__ == "__main__":
    main()
