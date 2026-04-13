import json
from pathlib import Path
from typing import Dict, List

from .formal import run_formal_equivalence
from .metrics import score_sia, score_sma, score_wrr
from .models import CircuitResult, EvalConfig, MetricResult
from .parser import extract_llm_artifacts, tool_syntax_check


DEFAULT_WEIGHTS = {
    "syntax": 0.1,
    "wrr": 0.2,
    "sma": 0.25,
    "fe": 0.35,
    "sia": 0.1,
}


class BenchmarkEvaluator:
    def __init__(self, config: EvalConfig):
        self.config = config
        self.weights = dict(DEFAULT_WEIGHTS)
        if config.weights:
            self.weights.update(config.weights)

    def _load_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _metric_from_bool(self, ok: bool, notes: List[str]) -> MetricResult:
        return MetricResult(score=1.0 if ok else 0.0, notes=notes)

    def evaluate_case(self, case_dir: Path) -> CircuitResult:
        metadata = json.loads(self._load_text(case_dir / "metadata.json"))
        case_id = metadata["id"]

        gt_path = case_dir / "ground_truth_rtl.v"
        gt_verilog = self._load_text(gt_path)

        submission_path = Path(self.config.submissions_dir) / case_id / "response.md"
        notes: List[str] = []

        if not submission_path.exists():
            missing = ["Submission not found"]
            zero = MetricResult(score=0.0, notes=missing)
            return CircuitResult(
                circuit_id=case_id,
                syntax=zero,
                wrr=zero,
                sma=zero,
                fe=zero,
                sia=zero,
                total_score=0.0,
                notes=missing,
            )

        response = self._load_text(submission_path)
        parsed = extract_llm_artifacts(response)
        notes.extend(parsed.parse_notes)

        syntax_check = tool_syntax_check(parsed.verilog)
        syntax_metric = self._metric_from_bool(syntax_check.passed, syntax_check.notes)

        if not syntax_check.passed:
            # Syntax failure is a hard stop for FE.
            wrr_metric = score_wrr(gt_verilog, parsed.verilog)
            sma_metric = score_sma(gt_verilog, parsed.verilog)
            sia_metric = score_sia(parsed.summary, metadata.get("intent_summary", ""), metadata.get("semantic_keywords", []))
            fe_metric = MetricResult(score=0.0, notes=["Skipped FE due to syntax failure"])
        else:
            wrr_metric = score_wrr(gt_verilog, parsed.verilog)
            sma_metric = score_sma(gt_verilog, parsed.verilog)
            sia_metric = score_sia(parsed.summary, metadata.get("intent_summary", ""), metadata.get("semantic_keywords", []))
            if self.config.use_formal:
                formal = run_formal_equivalence(gt_verilog, parsed.verilog, metadata.get("top_module", ""))
                fe_metric = MetricResult(score=formal.score, notes=formal.notes, details={"passed": 1.0 if formal.passed else 0.0})
            else:
                fe_metric = MetricResult(score=0.0, notes=["Formal check disabled by config"])

        total = (
            self.weights["syntax"] * syntax_metric.score
            + self.weights["wrr"] * wrr_metric.score
            + self.weights["sma"] * sma_metric.score
            + self.weights["fe"] * fe_metric.score
            + self.weights["sia"] * sia_metric.score
        )

        return CircuitResult(
            circuit_id=case_id,
            syntax=syntax_metric,
            wrr=wrr_metric,
            sma=sma_metric,
            fe=fe_metric,
            sia=sia_metric,
            total_score=round(total, 4),
            notes=notes,
        )

    def evaluate_all(self) -> Dict[str, object]:
        example_root = Path(self.config.examples_dir)
        case_dirs = sorted([p for p in example_root.iterdir() if p.is_dir()])

        results = [self.evaluate_case(case_dir) for case_dir in case_dirs]
        aggregate = round(sum(r.total_score for r in results) / len(results), 4) if results else 0.0

        payload = {
            "benchmark": "GateLift-Bench",
            "num_cases": len(results),
            "aggregate_score": aggregate,
            "weights": self.weights,
            "results": [
                {
                    "circuit_id": r.circuit_id,
                    "total_score": r.total_score,
                    "syntax": {"score": r.syntax.score, "notes": r.syntax.notes, "details": r.syntax.details},
                    "wrr": {"score": r.wrr.score, "notes": r.wrr.notes, "details": r.wrr.details},
                    "sma": {"score": r.sma.score, "notes": r.sma.notes, "details": r.sma.details},
                    "fe": {"score": r.fe.score, "notes": r.fe.notes, "details": r.fe.details},
                    "sia": {"score": r.sia.score, "notes": r.sia.notes, "details": r.sia.details},
                    "notes": r.notes,
                }
                for r in results
            ],
        }

        out_path = Path(self.config.results_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
