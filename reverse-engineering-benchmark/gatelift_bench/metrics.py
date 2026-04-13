from collections import Counter
from typing import Dict, List, Tuple

from .models import MetricResult
from .verilog_utils import (
    extract_bus_declarations,
    extract_graph_shape,
    extract_operator_counter,
    keyword_overlap,
)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def score_wrr(ground_truth_verilog: str, candidate_verilog: str) -> MetricResult:
    """Word-Recovery Rate using bus signature F1."""
    gt = extract_bus_declarations(ground_truth_verilog)
    cand = extract_bus_declarations(candidate_verilog)

    if not gt and not cand:
        return MetricResult(score=1.0, details={"precision": 1.0, "recall": 1.0, "f1": 1.0})

    tp = len(gt & cand)
    precision = tp / len(cand) if cand else 0.0
    recall = tp / len(gt) if gt else 0.0
    f1 = _f1(precision, recall)
    notes: List[str] = []
    if f1 < 1.0:
        notes.append(f"Recovered {tp}/{len(gt)} ground-truth bus signatures")

    return MetricResult(score=round(f1, 4), notes=notes, details={"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)})


def _counter_f1(gt: Counter, cand: Counter) -> Tuple[float, float, float]:
    gt_total = sum(gt.values())
    cand_total = sum(cand.values())
    if gt_total == 0 and cand_total == 0:
        return 1.0, 1.0, 1.0

    overlap = 0
    for key in gt:
        overlap += min(gt[key], cand.get(key, 0))

    precision = overlap / cand_total if cand_total else 0.0
    recall = overlap / gt_total if gt_total else 0.0
    return precision, recall, _f1(precision, recall)


def score_sma(ground_truth_verilog: str, candidate_verilog: str) -> MetricResult:
    """Structural Match Accuracy via operator/gate profile similarity."""
    gt_ops = extract_operator_counter(ground_truth_verilog)
    cand_ops = extract_operator_counter(candidate_verilog)
    precision, recall, f1 = _counter_f1(gt_ops, cand_ops)

    gt_shape = extract_graph_shape(ground_truth_verilog)
    cand_shape = extract_graph_shape(candidate_verilog)
    shape_terms = []
    for k in gt_shape:
        g = gt_shape[k]
        c = cand_shape[k]
        if g == 0 and c == 0:
            shape_terms.append(1.0)
        elif g == 0:
            shape_terms.append(0.0)
        else:
            shape_terms.append(max(0.0, 1.0 - abs(g - c) / max(g, 1)))

    shape_score = sum(shape_terms) / len(shape_terms)
    score = 0.7 * f1 + 0.3 * shape_score
    return MetricResult(
        score=round(score, 4),
        notes=[] if score >= 0.7 else ["Operator or graph profile differs from reference"],
        details={
            "operator_f1": round(f1, 4),
            "shape_score": round(shape_score, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        },
    )


def score_sia(summary: str, reference_summary: str, semantic_keywords: List[str]) -> MetricResult:
    """Semantic Intent Accuracy using keyword coverage and token Jaccard."""
    summary_tokens = set(summary.lower().split())
    ref_tokens = set(reference_summary.lower().split())

    if not summary_tokens and not ref_tokens:
        jaccard = 1.0
    else:
        union = summary_tokens | ref_tokens
        jaccard = len(summary_tokens & ref_tokens) / len(union) if union else 0.0

    kw_hits, kw_total = keyword_overlap(summary, semantic_keywords)
    kw_score = kw_hits / kw_total if kw_total else 1.0
    score = 0.6 * kw_score + 0.4 * jaccard

    notes: List[str] = []
    if kw_hits < kw_total:
        notes.append(f"Keyword coverage {kw_hits}/{kw_total}")

    return MetricResult(
        score=round(score, 4),
        notes=notes,
        details={"jaccard": round(jaccard, 4), "keyword_score": round(kw_score, 4)},
    )
