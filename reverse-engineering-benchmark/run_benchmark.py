#!/usr/bin/env python3
import argparse
from pathlib import Path

from gatelift_bench.evaluator import BenchmarkEvaluator
from gatelift_bench.models import EvalConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GateLift-Bench evaluation")
    parser.add_argument("--examples", default="examples", help="Directory containing benchmark cases")
    parser.add_argument("--submissions", default="submissions", help="Directory containing model submissions")
    parser.add_argument("--results", default="results/evaluation_report.json", help="Output JSON report path")
    parser.add_argument("--no-formal", action="store_true", help="Disable Yosys formal equivalence")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = EvalConfig(
        examples_dir=str(Path(args.examples).resolve()),
        submissions_dir=str(Path(args.submissions).resolve()),
        results_path=str(Path(args.results).resolve()),
        use_formal=not args.no_formal,
    )

    evaluator = BenchmarkEvaluator(config)
    payload = evaluator.evaluate_all()

    print(f"GateLift-Bench evaluated {payload['num_cases']} cases")
    print(f"Aggregate score: {payload['aggregate_score']}")
    print(f"Report: {config.results_path}")


if __name__ == "__main__":
    main()
