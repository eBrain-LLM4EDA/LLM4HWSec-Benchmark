# GateLift-Bench — Evaluation Framework Technical Reference

## 1. Overview

The evaluation framework scores an LLM's ability to lift a flattened **gate-level netlist** back to a functionally equivalent **word-level RTL** (Verilog). Given a synthesized, bit-level netlist, the LLM must produce two artifacts:

- **Verilog code block** — a functionally equivalent word-level RTL module (fenced `` ```verilog `` block in the response)
- **Functional summary** — a one-sentence natural-language description of the circuit's intent

The framework compares these artifacts against gold-standard references across five scoring dimensions, producing a weighted per-case score and an arithmetic-mean aggregate across all benchmark cases.

---

## 2. Benchmark Structure

### 2.1 Reference Cases

Each benchmark case lives under `examples/<case-id>/` and contains three files:

| File | Purpose |
|------|---------|
| `prompt_netlist.v` | Flattened gate-level Verilog (Yosys output) given to the LLM |
| `ground_truth_rtl.v` | Gold-standard word-level RTL |
| `metadata.json` | Case ID, tier, top module name, intent summary, semantic keywords |

### 2.2 Metadata Schema

```json
{
  "id": "tier2_fsm_counter",
  "tier": 2,
  "top_module": "fsm_counter",
  "intent_summary": "A sequential FSM with enable and reset controlling a 2-bit state and count output.",
  "semantic_keywords": ["fsm", "sequential", "state", "counter", "enable"]
}
```

`tier` determines the expected difficulty. `top_module` is passed to the Yosys equivalence script. `intent_summary` and `semantic_keywords` are used in Dimension 5 (SIA) scoring.

### 2.3 Difficulty Tiers

| Tier | Category | Reconstruction task | Included examples |
|------|----------|--------------------|--------------------|
| 1 | Combinational Arithmetic | Regroup flat bit-level gates into word-level operators (`+`, `*`) | `tier1_adder` |
| 2 | Sequential Logic / FSMs | Identify state registers, isolate next-state logic, reconstruct state machine | `tier2_fsm_counter` |
| 3 | Complex Datapaths & Control | Identify architectural intent (ALU decoder, crypto S-box, RISC-V submodule) | `tier3_alu_control` |

### 2.4 Submissions

Model responses are placed as `submissions/<case-id>/response.md`. The evaluator reads only the **first** fenced `` ```verilog `` block from this file; all surrounding text is treated as the natural-language summary.

---

## 3. Evaluation Pipeline

### 3.1 Entry Point

Invoked via `run_benchmark.py`:

```bash
python run_benchmark.py \
    --examples examples \
    --submissions submissions \
    --results results/evaluation_report.json
```

Disable Yosys formal checks when the tool is unavailable:

```bash
python run_benchmark.py --no-formal
```

Or via Docker (recommended — includes Yosys, Verilator, Icarus Verilog):

```bash
docker compose run --rm benchmark
docker compose run --rm benchmark bench --no-formal
```

### 3.2 Modes

| Flag | Dependency | Effect |
|------|-----------|--------|
| *(default)* | Yosys | Full pipeline including SAT-based formal equivalence |
| `--no-formal` | None | Skips Yosys; FE metric reported as 0.0 |

The syntax gate gracefully degrades: it tries `verilator --lint-only`, then `iverilog -tnull`, then falls back to a built-in heuristic checker.

### 3.3 Main Loop

```
┌─────────────────────────────────────────────────────┐
│  main()                                             │
│  1. Parse CLI arguments into EvalConfig             │
│  2. Discover all subdirectories under examples/     │
│  3. For each case:                                  │
│     a. Load metadata.json + ground_truth_rtl.v      │
│     b. Load submissions/<case-id>/response.md       │
│     c. Parse response → Verilog block + summary     │
│     d. Run syntax gate                              │
│     e. Score WRR, SMA, SIA                          │
│     f. If syntax passed and formal enabled: run FE  │
│     g. Compute weighted total                       │
│  4. Compute arithmetic mean aggregate               │
│  5. Write results/evaluation_report.json            │
└─────────────────────────────────────────────────────┘
```

The relevant code in `gatelift_bench/evaluator.py`:

```python
total = (
    weights["syntax"] * syntax_metric.score
    + weights["wrr"]   * wrr_metric.score
    + weights["sma"]   * sma_metric.score
    + weights["fe"]    * fe_metric.score
    + weights["sia"]   * sia_metric.score
)

aggregate = sum(r.total_score for r in results) / len(results)
```

---

## 4. The Five Scoring Dimensions

### 4.1 Dimension 1: Syntax (weight = 0.10)

**Question answered:** Does the LLM's generated Verilog compile without errors?

**Input:** extracted Verilog block from `response.md`

**How it works:**

`tool_syntax_check()` in `parser.py` tries tools in order:

1. **Verilator** — `verilator --lint-only candidate.v`
2. **Icarus Verilog** — `iverilog -tnull candidate.v`
3. **Built-in heuristic** — if neither tool is installed:
   - Checks that at least one `module` declaration exists
   - Verifies `module`/`endmodule` counts match
   - Scans each line for likely missing semicolons on `assign`, `wire`, `reg`, `logic`, `input`, `output`, `inout` statements

**Score:** Binary 1.0 (pass) or 0.0 (fail).

**Effect of failure:** FE is unconditionally set to 0.0 and skipped. WRR, SMA, and SIA still run on the malformed text.

---

### 4.2 Dimension 2: Word-Recovery Rate (weight = 0.20)

**Question answered:** Did the LLM correctly regroup flat bit-level signals into word-level buses?

**Input files:**
- `ground_truth_rtl.v`
- LLM's extracted Verilog block

**How it works:**

`score_wrr()` in `metrics.py` extracts bus-signature sets from both files using `extract_bus_declarations()` in `verilog_utils.py`. Each bus declaration becomes a 3-tuple `(signal_name, width_in_bits, direction_or_type)`:

```python
pattern = re.compile(
    r"\b(input|output|inout|wire|reg|logic)\b"
    r"\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*([^;]+);"
)
# width = abs(msb - lsb) + 1  (defaults to 1 if no range)
# e.g. "input [7:0] a" → ("a", 8, "input")
```

F1 is then computed over the two signature sets:

```
precision = |gt ∩ cand| / |cand|
recall    = |gt ∩ cand| / |gt|
WRR       = 2 × precision × recall / (precision + recall)
```

**Example (tier1_adder):** The ground truth has `(a, 8, input)`, `(b, 8, input)`, `(sum, 8, output)`. If the LLM maps all three correctly, WRR = 1.0.

**Why two components:** A model could declare many narrow buses (high recall, low precision) or few wide ones (high precision, low recall). F1 penalizes both extremes.

---

### 4.3 Dimension 3: Structural Match Accuracy (weight = 0.25)

**Question answered:** Did the LLM recognise the *type* of hardware structure (e.g., an adder vs. a random boolean equation)?

**Input files:**
- `ground_truth_rtl.v`
- LLM's extracted Verilog block

**How it works:**

`score_sma()` in `metrics.py` combines two sub-scores with weights 0.7 and 0.3.

#### 4.3.1 Operator Profile F1 (weight 0.7)

`extract_operator_counter()` counts operator/gate tokens in the Verilog source:

| Token | Counted as |
|-------|-----------|
| `+` | `add` |
| `-` | `sub` |
| `*` | `mul` |
| `^` | `xor` |
| `&` | `and` |
| `\|` | `or` |
| `<<` | `shl` |
| `>>` | `shr` |
| `==` | `eq` |
| `!=` | `neq` |
| `<` | `lt` |
| `>` | `gt` |
| `?` | `mux` |
| `and`/`or`/`xor`/`xnor`/`nand`/`nor`/`not`/`buf` (keyword) | gate primitive |

F1 is computed over the multiset (Counter) overlap:

```python
overlap = sum(min(gt[k], cand[k]) for k in gt)
precision = overlap / sum(cand.values())
recall    = overlap / sum(gt.values())
```

#### 4.3.2 Graph-Shape Proxy (weight 0.3)

`extract_graph_shape()` extracts three integer features:

| Feature | How extracted |
|---------|--------------|
| `gate_instances` | Regex: module instantiation patterns `identifier identifier (` |
| `assign_count` | Count of `assign` keywords |
| `wire_count` | Count of `wire` keywords |

For each feature, per-axis similarity = `max(0, 1 - |gt - cand| / max(gt, 1))`. The shape score is the mean across all three axes.

**Final SMA = 0.7 × operator_F1 + 0.3 × shape_score**

---

### 4.4 Dimension 4: Functional Equivalence (weight = 0.35)

**Question answered:** Is the LLM's RTL *mathematically equivalent* to the input netlist?

This is the gold-standard metric with the highest weight.

**Input files:**
- `ground_truth_rtl.v`
- LLM's extracted Verilog block
- `metadata.json` (`top_module` field)

**How it works:**

`run_formal_equivalence()` in `formal.py` writes both files to a temporary directory and runs a Yosys equivalence script:

```
read_verilog gold.v
prep -top <top_module>
design -stash gold

read_verilog candidate.v
prep -top <top_module>
design -stash gate

design -copy-from gold -as gold <top_module>
design -copy-from gate -as gate <top_module>

equiv_make gold gate equiv
prep -top equiv
equiv_simple
equiv_status -assert
```

`equiv_make` builds a miter circuit connecting matching outputs with `$equiv` cells. `equiv_simple` runs a SAT-based solver to prove or disprove each cell. `equiv_status -assert` returns a non-zero exit code if any cell remains unproven.

**Scoring:** Binary — 1.0 if `yosys` exits with code 0, 0.0 otherwise. The error message from `proc.stderr` is captured in `notes` for diagnostics.

**Prerequisite:** If Yosys is not installed (`shutil.which("yosys")` returns None), the metric is reported as 0.0 with a note and the Yosys invocation is skipped entirely.

---

### 4.5 Dimension 5: Semantic Intent Accuracy (weight = 0.10)

**Question answered:** Did the LLM correctly label the circuit's purpose (e.g., "8-bit adder" vs. "32-bit multiplier")?

**Input:**
- LLM's natural-language summary (text outside the Verilog block in `response.md`)
- `metadata.json` (`intent_summary`, `semantic_keywords`)

**How it works:**

`score_sia()` in `metrics.py` combines two sub-scores with weights 0.6 and 0.4.

#### 4.5.1 Keyword Coverage (weight 0.6)

```python
kw_hits = sum(1 for k in semantic_keywords if k.lower() in summary.lower())
kw_score = kw_hits / len(semantic_keywords)
```

**Example (tier3_alu_control):** Keywords are `["alu", "opcode", "datapath", "logic", "arithmetic", "zero"]`. If the summary mentions 5 of 6, keyword score = 5/6 = 0.833.

#### 4.5.2 Token Jaccard (weight 0.4)

```python
summary_tokens = set(summary.lower().split())
ref_tokens     = set(intent_summary.lower().split())
jaccard = |summary_tokens ∩ ref_tokens| / |summary_tokens ∪ ref_tokens|
```

**Final SIA = 0.6 × keyword_score + 0.4 × jaccard**

---

## 5. Composite Score

### 5.1 Per-Case Total

```python
total = (0.10 * syntax
       + 0.20 * wrr
       + 0.25 * sma
       + 0.35 * fe
       + 0.10 * sia)
```

Weights can be overridden by passing a custom `weights` dict to `EvalConfig`.

### 5.2 Benchmark Aggregate

```python
aggregate = sum(case.total_score for case in results) / len(results)
```

The aggregate is the arithmetic mean — no difficulty weighting is applied in the current implementation. All cases contribute equally regardless of tier.

### 5.3 Example Scores (from `results/evaluation_report.json`)

| Case | Syntax | WRR | SMA | FE | SIA | Total |
|------|--------|-----|-----|-----|-----|-------|
| `tier1_adder` | 1.0 | 0.0 | 0.90 | 1.0 | 0.704 | 0.7454 |
| `tier2_fsm_counter` | 1.0 | 1.0 | 1.0 | 0.0 | 0.664 | 0.6164 |
| `tier3_alu_control` | 1.0 | 1.0 | 1.0 | 1.0 | 0.72 | 0.972 |
| **Aggregate** | | | | | | **0.7779** |

`tier1_adder` has WRR = 0 because the ground truth uses bus notation (`[7:0] a`) while the reference submission uses the same notation — the mismatch was between the flat netlist port names and the ground truth's bus signatures. FE still passes because the Yosys equivalence check proved functional identity regardless of signal naming.

`tier2_fsm_counter` has FE = 0 because 6 `$equiv` cells remained unproven, indicating a behavioral difference in the reconstructed state machine.

---

## 6. Verilog Analysis Layer

### 6.1 `verilog_utils.py` — Helper Functions

All structural extraction uses Python `re` (no external parser or AST library).

#### `get_module_name(verilog_text)`

```python
re.search(r"\bmodule\s+([a-zA-Z_][a-zA-Z0-9_$]*)", verilog_text)
```

Returns the first module name found, defaulting to `"top"` if none.

#### `extract_bus_declarations(verilog_text)`

Returns `Set[Tuple[str, int, str]]` — a set of `(signal_name, width, kind)` signatures. The regex matches `input`, `output`, `inout`, `wire`, `reg`, `logic` declarations, with or without a range specifier. Comma-separated signal lists on a single line are split and each name is added individually.

#### `extract_operator_counter(verilog_text)`

Returns a `Counter` mapping operator names to occurrence counts. String counting (e.g., `verilog_text.count("+")`) is used for operator tokens; a regex is used for gate primitives.

**Known limitation:** `&` is counted every time it appears — including in `&&` (logical AND), which increments both `and` and itself. Similarly `<` is counted inside `<=` and `<<`. This is conservative (over-counts) but consistent between ground truth and candidate, so the F1 score is robust.

#### `extract_graph_shape(verilog_text)`

Returns `Dict[str, int]` with three keys: `gate_instances`, `assign_count`, `wire_count`.

#### `keyword_overlap(summary, keywords)`

Returns `(hits, total)` — simple substring search, case-insensitive.

---

## 7. Parser Layer

### 7.1 `parser.py` — LLM Response Parsing

#### `extract_llm_artifacts(response_text)`

```python
VERILOG_BLOCK_RE = re.compile(r"```(?:verilog|systemverilog)?\s*(.*?)```",
                               re.IGNORECASE | re.DOTALL)
```

- Extracts the **first** fenced Verilog block (language tag `verilog`, `systemverilog`, or absent).
- If no block is found, the entire response is used as the Verilog payload and the summary is empty.
- Summary is the response text with all code blocks removed, collapsed to a single space-separated string.
- Multiple code blocks: only the first is used; a warning note is added.

#### `tool_syntax_check(verilog_text)` / `builtin_syntax_check(verilog_text)`

See [Section 4.1](#41-dimension-1-syntax-weight--010). The tool chain is: Verilator → Icarus Verilog → built-in. The built-in heuristic writes no temp files and has no external dependencies.

---

## 8. Formal Equivalence Layer

### 8.1 `formal.py` — Yosys SAT Flow

`run_formal_equivalence(ground_truth_verilog, candidate_verilog, top_module)`:

1. Checks `shutil.which("yosys")` — returns score 0.0 immediately if absent.
2. Writes both Verilog strings to a `tempfile.TemporaryDirectory`.
3. Writes an equivalence script (`equiv.ys`) and invokes `yosys -q equiv.ys`.
4. Returns `FormalResult(score=1.0, passed=True)` on exit code 0, else `FormalResult(score=0.0, passed=False, notes=[stderr])`.

The `-q` flag suppresses Yosys banner output. Errors from `stderr` are captured and surfaced in the JSON report's `notes` field for debugging.

**Common failure messages:**

| Yosys message | Meaning |
|--------------|---------|
| `Found N unproven $equiv cells` | Behavioral difference in N output bits — FE = 0 |
| `ERROR: Module not found` | `top_module` in metadata does not match either file's module name |
| `ERROR: ... syntax error` | Candidate Verilog has a syntax error that passed the heuristic gate but failed Yosys read |

---

## 9. Data Models

Defined in `gatelift_bench/models.py` using Python `dataclasses`:

```python
@dataclass
class EvalConfig:
    examples_dir:    str
    submissions_dir: str
    results_path:    str
    use_formal:      bool = True
    weights:         Optional[Dict[str, float]] = None

@dataclass
class ParseResult:
    verilog:     str
    summary:     str
    parse_notes: List[str]

@dataclass
class SyntaxResult:
    passed: bool
    notes:  List[str]
    tool:   str       # "verilator" | "iverilog" | "builtin"

@dataclass
class MetricResult:
    score:   float
    notes:   List[str]
    details: Dict[str, float]   # sub-scores (precision, recall, f1, …)

@dataclass
class FormalResult:
    score:  float
    passed: bool
    notes:  List[str]
    tool:   str       # always "yosys"

@dataclass
class CircuitResult:
    circuit_id:  str
    syntax:      MetricResult
    wrr:         MetricResult
    sma:         MetricResult
    fe:          MetricResult
    sia:         MetricResult
    total_score: float
    notes:       List[str]
```

---

## 10. Output Format

### 10.1 Console

```
GateLift-Bench evaluated 3 cases
Aggregate score: 0.7779
Report: /path/to/results/evaluation_report.json
```

### 10.2 JSON Report (`results/evaluation_report.json`)

```json
{
  "benchmark": "GateLift-Bench",
  "num_cases": 3,
  "aggregate_score": 0.7779,
  "weights": {
    "syntax": 0.1,
    "wrr": 0.2,
    "sma": 0.25,
    "fe": 0.35,
    "sia": 0.1
  },
  "results": [
    {
      "circuit_id": "tier1_adder",
      "total_score": 0.7454,
      "syntax": { "score": 1.0, "notes": [], "details": {} },
      "wrr": {
        "score": 0.0,
        "notes": ["Recovered 0/3 ground-truth bus signatures"],
        "details": { "precision": 0.0, "recall": 0.0, "f1": 0.0 }
      },
      "sma": {
        "score": 0.9,
        "notes": [],
        "details": { "operator_f1": 1.0, "shape_score": 0.6667, "precision": 1.0, "recall": 1.0 }
      },
      "fe": {
        "score": 1.0,
        "notes": ["Formal equivalence proven"],
        "details": { "passed": 1.0 }
      },
      "sia": {
        "score": 0.7043,
        "notes": [],
        "details": { "jaccard": 0.2609, "keyword_score": 1.0 }
      },
      "notes": []
    }
  ]
}
```

---

## 11. Generating New Cases

```bash
python tools/generate_case_from_rtl.py \
    --source path/to/design.v \
    --top top_module_name \
    --case-id tier2_my_case \
    --tier 2 \
    --intent "A sequential FSM controller for ..."
```

This creates under `examples/<case-id>/`:
1. `ground_truth_rtl.v` — copied from `--source`
2. `prompt_netlist.v` — Yosys `synth; flatten; opt` output
3. `metadata.json` — populated with the provided arguments and inferred keywords

Requires Yosys in `PATH`. The generated netlist is the direct evaluation input; the source RTL is the ground truth.

---

## 12. File Manifest

```
reverse-engineering-benchmark/
├── Dockerfile                          # Docker image (Python + Yosys + Verilator + iverilog)
├── docker-compose.yml
├── docker-entrypoint.sh                # Entrypoint: bench / test / shell subcommands
├── requirements.txt
├── run_benchmark.py                    # CLI entry point
│
├── gatelift_bench/
│   ├── __init__.py
│   ├── evaluator.py                    # Orchestrates per-case and aggregate scoring
│   ├── formal.py                       # Yosys SAT equivalence check
│   ├── metrics.py                      # WRR, SMA, SIA scoring functions
│   ├── models.py                       # Dataclasses: EvalConfig, CircuitResult, …
│   ├── parser.py                       # LLM response parsing + syntax gate
│   └── verilog_utils.py                # Bus/operator/shape extraction helpers
│
├── examples/                           # Benchmark cases (ground truth)
│   └── <case-id>/
│       ├── metadata.json
│       ├── prompt_netlist.v            # Yosys-flattened netlist (LLM input)
│       └── ground_truth_rtl.v          # Word-level RTL (reference)
│
├── submissions/                        # Model responses (one dir per case)
│   └── <case-id>/
│       └── response.md                 # LLM output: summary + fenced Verilog block
│
├── results/
│   └── evaluation_report.json          # Written by run_benchmark.py
│
├── tools/
│   └── generate_case_from_rtl.py       # Case generation from source RTL via Yosys
│
├── tests/
│   └── test_benchmark.py               # Parser, metric, and end-to-end tests
│
└── docs/
    └── OPERATOR_MANUAL.md              # Execution flowchart and extension guide
```