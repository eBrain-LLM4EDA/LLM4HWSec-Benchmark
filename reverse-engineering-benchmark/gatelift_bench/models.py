from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ParseResult:
    verilog: str
    summary: str
    parse_notes: List[str] = field(default_factory=list)


@dataclass
class SyntaxResult:
    passed: bool
    notes: List[str] = field(default_factory=list)
    tool: str = "builtin"


@dataclass
class MetricResult:
    score: float
    notes: List[str] = field(default_factory=list)
    details: Dict[str, float] = field(default_factory=dict)


@dataclass
class FormalResult:
    score: float
    passed: bool
    notes: List[str] = field(default_factory=list)
    tool: str = "yosys"


@dataclass
class CircuitResult:
    circuit_id: str
    syntax: MetricResult
    wrr: MetricResult
    sma: MetricResult
    fe: MetricResult
    sia: MetricResult
    total_score: float
    notes: List[str] = field(default_factory=list)


@dataclass
class EvalConfig:
    examples_dir: str
    submissions_dir: str
    results_path: str
    use_formal: bool = True
    weights: Optional[Dict[str, float]] = None
