# Evaluation Framework: HLS Security-Aware Code Generation Benchmark

## Overview

This framework evaluates an LLM's ability to (1) identify security vulnerabilities in HLS C/C++ code, and (2) generate security-hardened replacements. Evaluation covers five dimensions scored independently, then combined into a composite score.

---

## 1. Evaluation Dimensions

### 1.1 CWE Violation Detection Rate (Weight: 25%)

Measures how many known vulnerabilities the LLM identifies in its vulnerability report.

| Score | Criteria |
|-------|----------|
| 1.0 | All expected vulnerabilities found with correct CWE classification |
| 0.75 | All vulnerabilities found, some CWE misclassification |
| 0.5 | ≥ 50% of vulnerabilities found |
| 0.25 | < 50% of vulnerabilities found |
| 0.0 | No vulnerabilities identified |

**Scoring formula:**
```
detection_score = (true_positives / expected_vulnerabilities) * cwe_accuracy_factor
cwe_accuracy_factor = correctly_classified / total_reported
```

**False positive penalty:** Subtract 0.05 per false positive (vulnerability reported that does not exist), floor at 0.0.

### 1.2 Information Flow Correctness (Weight: 25%)

Measures whether the hardened code correctly implements taint/label tracking when the security spec requires it. Applicable to examples with `security_domain: information_flow_tracking`.

| Criterion | Points |
|-----------|--------|
| Taint-tracked data type defined | 0.2 |
| Labels assigned correctly at inputs (SECRET/PUBLIC) | 0.2 |
| Taint propagates through all arithmetic ops (XOR, ADD, shift) | 0.2 |
| Taint propagates through lookup tables (S-box) | 0.1 |
| Declassification is explicit and gated | 0.15 |
| No untracked SECRET→PUBLIC flow paths | 0.15 |

For examples without IFT requirements, score the access control or sanitization correctness using domain-specific criteria:

**Access Control correctness** (for `security_domain: access_control`):

| Criterion | Points |
|-----------|--------|
| Access policy function implemented | 0.25 |
| Policy matches specification exactly | 0.25 |
| Denied access returns safe default (zero) | 0.2 |
| Denial feedback in response | 0.15 |
| No bypass mechanisms (debug mode removed) | 0.15 |

**Side-Channel correctness** (for `security_domain: side_channel`):

| Criterion | Points |
|-----------|--------|
| No data-dependent branches on secrets | 0.3 |
| Fixed iteration count | 0.2 |
| Constant number of operations per iteration | 0.2 |
| Branchless conditional operations (cswap / OR-accumulate) | 0.2 |
| HLS pragmas enforce fixed pipeline (UNROLL/PIPELINE) | 0.1 |

**Resource Isolation correctness** (for `security_domain: resource_isolation`):

| Criterion | Points |
|-----------|--------|
| Separate storage for different security domains | 0.25 |
| Sanitization on context switch / reset | 0.25 |
| Stale data cleared after use | 0.2 |
| No cross-domain timing interference | 0.15 |
| Zeroization command available | 0.15 |

### 1.3 Synthesis Pass (Weight: 20%)

Measures whether the generated code can be synthesized by Xilinx Vitis HLS.

| Score | Criteria |
|-------|----------|
| 1.0 | Code synthesizes without errors or warnings |
| 0.75 | Code synthesizes with non-critical warnings only |
| 0.5 | Minor syntax or pragma fixes needed (< 5 lines changed) |
| 0.25 | Significant fixes needed but structure is synthesizable |
| 0.0 | Code is fundamentally non-synthesizable (dynamic alloc, recursion, etc.) |

**Automated check criteria (without running synthesis):**
- No dynamic memory allocation (`new`, `malloc`, `free`)
- No recursion
- No system calls or I/O (`printf`, `cout`, file ops)
- No exceptions (`try`/`catch`/`throw`)
- No virtual functions or RTTI
- All loop bounds statically determinable or bounded by `#pragma HLS LOOP_TRIPCOUNT`
- HLS interface pragmas present and valid
- Uses HLS-compatible types (`ap_int`, `ap_uint`, `hls::stream`)

### 1.4 Functional Equivalence (Weight: 15%)

Measures whether the hardened code produces the same I/O behavior as the insecure code for non-security-related functionality.

| Score | Criteria |
|-------|----------|
| 1.0 | All functional test vectors produce identical output |
| 0.75 | Correct for > 90% of test vectors; edge cases differ |
| 0.5 | Core functionality preserved but some I/O differences |
| 0.25 | Significant functional regression |
| 0.0 | Output is incorrect or function signature incompatible |

**Note:** Removed ports (e.g., debug_out) are excluded from equivalence checking. The comparison is on the subset of ports that exist in both insecure and secure versions.

### 1.5 Security Completeness (Weight: 15%)

Measures whether ALL security properties from the specification are enforced, not just the ones flagged as vulnerabilities.

| Criterion | Points |
|-----------|--------|
| All "Required Properties" from security_spec.md addressed | 0.4 |
| All "Prohibited Patterns" from security_spec.md avoided | 0.3 |
| Defense-in-depth (additional hardening beyond spec) | 0.15 |
| Security-relevant comments in code | 0.15 |

---

## 2. Composite Score Calculation

```
composite = (0.25 * detection_rate)
           + (0.25 * flow_correctness)
           + (0.20 * synthesis_pass)
           + (0.15 * functional_equivalence)
           + (0.15 * security_completeness)
```

### Grade Bands

| Grade | Score Range | Description |
|-------|------------|-------------|
| A | 0.90 – 1.00 | Production-quality security hardening |
| B | 0.75 – 0.89 | Good hardening with minor gaps |
| C | 0.60 – 0.74 | Partial hardening, notable omissions |
| D | 0.40 – 0.59 | Weak hardening, major gaps |
| F | 0.00 – 0.39 | Inadequate — most vulnerabilities missed or introduced |

---

## 3. Per-Example Evaluation Procedure

For each of the 10 benchmark examples:

### Step 1: Vulnerability Report Evaluation
1. Parse the LLM's vulnerability report.
2. Match each reported vulnerability to the reference `vulnerability_report.md`.
3. Score detection rate and CWE classification accuracy.
4. Count false positives.

### Step 2: Hardened Code Evaluation
1. Parse the LLM's generated secure code.
2. Apply the domain-specific correctness rubric (IFT / Access Control / Side-Channel / Isolation).
3. Run synthesis compatibility checks (static analysis).
4. Compare functional I/O against reference.

### Step 3: Security Spec Coverage
1. Check each property in `security_spec.md` against the generated code.
2. Score completeness.

### Step 4: Compute Composite Score
1. Aggregate dimension scores with weights.
2. Assign grade band.

---

## 4. Difficulty-Weighted Aggregate

The 10 examples span three difficulty levels. The final benchmark score can be computed as a difficulty-weighted average:

| Difficulty | Examples | Weight |
|------------|----------|--------|
| Easy | 02, 03, 09 | 1.0x |
| Medium | 01, 04, 05 | 1.5x |
| Hard | 06, 07, 08, 10 | 2.0x |

```
benchmark_score = Σ(example_score * difficulty_weight) / Σ(difficulty_weight)
```

---

## 5. Automated Evaluation Checks

The following checks can be automated without running HLS synthesis:

### 5.1 Static Analysis Checks
- **Debug port removal:** grep for removed port names in generated code
- **Taint type presence:** check for struct/class with security label field
- **Constant-time patterns:** AST check for no `break`/`return` inside loops over secret data
- **Buffer separation:** verify separate array declarations for different security domains
- **Zeroization:** check for buffer-clearing loops
- **Access control function:** verify presence of policy check before memory/register access
- **HLS pragma validity:** parse `#pragma HLS` directives for correctness

### 5.2 Pattern Matching Rules
```
RULE: no_debug_leak
  FAIL if: output port carries variable derived from key/secret input
  CHECK: trace data flow from SECRET-labeled inputs to all output ports

RULE: constant_time_loop
  FAIL if: loop body contains break/return/early-exit conditional on secret data
  CHECK: all loops over secret data have fixed trip count

RULE: access_control_present
  FAIL if: memory/register write has no preceding privilege check
  CHECK: every write to protected region is guarded by policy function

RULE: sanitize_on_transition
  FAIL if: context switch or reset does not zero shared buffers
  CHECK: buffer clearing loop present in reset/ctx_switch handlers

RULE: taint_propagation
  FAIL if: arithmetic on tainted operands produces untainted result
  CHECK: all operator overloads propagate labels correctly
```

---

## 6. Reporting Format

Each evaluated submission should produce a JSON report:

```json
{
  "model": "model_name",
  "timestamp": "2026-04-01T00:00:00Z",
  "examples": [
    {
      "id": "01_aes_ift",
      "scores": {
        "detection_rate": 0.92,
        "flow_correctness": 0.85,
        "synthesis_pass": 1.0,
        "functional_equivalence": 1.0,
        "security_completeness": 0.80
      },
      "composite": 0.91,
      "grade": "A",
      "notes": "Missed V3 (unrestricted key port interface)"
    }
  ],
  "aggregate": {
    "mean_composite": 0.82,
    "difficulty_weighted": 0.79,
    "grade": "B"
  }
}
```
