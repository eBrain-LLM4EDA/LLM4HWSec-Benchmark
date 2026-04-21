# HLS Security Benchmark — Evaluation Framework Technical Reference

## 1. Overview

The evaluation framework scores an LLM's ability to audit and harden HLS (High-Level Synthesis) C/C++ code for hardware security. Given a vulnerable HLS design and a security specification, the LLM must produce two artifacts:

- **`secure.cpp`** — a security-hardened version of the input code
- **`vulnerability_report.md`** — a list of identified security vulnerabilities with CWE classifications

The framework compares these artifacts against gold-standard references across five scoring dimensions, producing a composite grade (A–F) per example and a difficulty-weighted aggregate across all 10 benchmark examples.

---

## 2. Benchmark Structure

### 2.1 Reference Examples

Each of the 10 examples contains six files:

| File | Purpose |
|------|---------|
| `insecure.cpp` | The vulnerable HLS C/C++ code given to the LLM |
| `reference_secure.cpp` | Gold-standard hardened output |
| `vulnerability_report.md` | Expected vulnerability findings |
| `security_spec.md` | Security properties that must hold in the hardened code |
| `prompt.md` | The natural-language task prompt given to the LLM |
| `metadata.json` | CWE IDs, security domain, difficulty, expected vulnerability count |

### 2.2 Metadata Schema

```json
{
  "id": "01_aes_ift",
  "title": "AES-128 Kernel Information Flow Tracking",
  "cwe_ids": ["CWE-200"],
  "security_domain": "information_flow_tracking",
  "difficulty": "medium",
  "expected_vulnerabilities": 3,
  "tags": ["crypto", "ift", "taint_tracking", "debug_leak"]
}
```

The `security_domain` field determines which property checker is used in Dimension 2 scoring. The `expected_vulnerabilities` count is used in Dimension 1 to compute detection rate.

### 2.3 Security Domains

The 10 examples span four security domains:

| Domain | Examples | What it tests |
|--------|----------|---------------|
| `information_flow_tracking` | 01 (AES), 06 (SHA-256 HMAC) | Taint labels on data, propagation through operations, no secret leakage to outputs |
| `access_control` | 02 (Memory), 05 (DMA), 07 (Register File) | Privilege checks before access, policy functions, denial feedback |
| `side_channel` | 03 (Constant-time compare), 08 (ModExp) | No early exit, fixed iteration, branchless operations |
| `resource_isolation` | 04 (Key schedule), 09 (FIFO), 10 (Bus arbiter) | Separate storage, sanitization on context switch, zeroization |

### 2.4 Difficulty Levels

| Difficulty | Weight | Examples |
|------------|--------|----------|
| Easy | 1.0× | 02, 03, 09 |
| Medium | 1.5× | 01, 04, 05 |
| Hard | 2.0× | 06, 07, 08, 10 |

---

## 3. Evaluation Pipeline

### 3.1 Entry Point

The evaluation is invoked via `run_evaluation_v2.py`:

```bash
python evaluation/run_evaluation_v2.py \
    --input llm_outputs/ \
    --reference examples/ \
    --mode simulate \
    --output report.json
```

Or via Docker:

```bash
docker run --rm \
    -v $(pwd)/llm_outputs:/data/submissions:ro \
    -v $(pwd)/results:/data/output \
    hls-security-benchmark --mode simulate
```

### 3.2 Modes

| Mode | Dependencies | What runs |
|------|-------------|-----------|
| `regex` | None | Regex pattern matching on source text |
| `simulate` | libclang, g++, optionally bambu+verilator | Clang AST analysis + C-simulation testbenches + bambu synthesis |

The `simulate` mode gracefully degrades: if libclang is missing, it falls back to `regex`. If bambu is missing, synthesis scoring uses the AST. If a testbench doesn't exist, functional equivalence defaults to 0.75.

### 3.3 Main Loop

```
┌─────────────────────────────────────────────────────┐
│  main()                                             │
│  1. Load scoring_rubric.json (lists all 10 examples)│
│  2. For each example:                               │
│     a. Locate submission dir and reference dir      │
│     b. Call evaluate_example_simulate()             │
│     c. Accumulate difficulty-weighted score         │
│  3. Compute aggregate grade                         │
│  4. Write evaluation_report.json                    │
└─────────────────────────────────────────────────────┘
```

The relevant code in `run_evaluation_v2.py`:

```python
for ex_info in rubric["examples"]:
    ex_id = ex_info["id"]
    ref_dir = os.path.join(args.reference, ex_id)
    sub_dir = os.path.join(args.input, ex_id)
    result = evaluate_fn(sub_dir, ref_dir, rubric)
    
    # Difficulty-weighted accumulation
    diff = ex_info.get("difficulty", "medium")
    w = difficulty_weights.get(diff, 1.0)  # easy=1.0, medium=1.5, hard=2.0
    total_weighted += result.scores.composite() * w
    total_weight += w
```

---

## 4. The Five Scoring Dimensions

### 4.1 Dimension 1: Detection Rate (weight = 0.25)

**Question answered:** Did the LLM find the right number of vulnerabilities and tag them with correct CWE IDs?

**Input files:**
- LLM's `vulnerability_report.md`
- Reference `vulnerability_report.md`
- `metadata.json` (`expected_vulnerabilities` count)

**How it works:**

```python
def score_detection(submission_vr_path, ref_dir, metadata):
    expected_count = metadata.get("expected_vulnerabilities", 0)
    _, ref_cwes = count_reference_vulnerabilities(ref_dir)
    
    # Count findings in submission (### V1:, ### V2:, etc.)
    submitted_findings = re.findall(r"(?:###?\s*V\d+|###?\s*\d+\.)", content)
    submitted_cwes = set(f"CWE-{c}" for c in re.findall(r"CWE-(\d+)", content))
    
    # How many of the expected findings were reported?
    finding_rate = min(len(submitted_findings) / expected_count, 1.0)
    
    # How many of the reference CWE IDs were mentioned?
    true_positive_cwes = len(submitted_cwes & set(ref_cwes))
    cwe_coverage = true_positive_cwes / len(ref_cwes)
    
    # Penalize false positive CWEs
    false_positive_cwes = len(submitted_cwes - set(ref_cwes))
    
    score = finding_rate * cwe_coverage - (false_positive_cwes * 0.05)
```

**Example:** If the reference has 3 findings all tagged CWE-200, and the LLM reports 3 findings with CWE-200 and no extra CWEs: `finding_rate = 3/3 = 1.0`, `cwe_coverage = 1/1 = 1.0`, `score = 1.0`.

**Why two components:** An LLM could report 10 generic findings with every CWE under the sun — that would have high CWE coverage but inflated finding count. The two-factor scoring rewards precision: right number of findings AND correct classification.

---

### 4.2 Dimension 2: Security Property Correctness (weight = 0.25)

**Question answered:** Does the hardened code structurally implement the required security fix?

**Input files:**
- LLM's `secure.cpp` (parsed into a Clang AST)
- `metadata.json` (`security_domain` field)

**How it works:**

The `SecurityVerifier` class reads the `security_domain` from metadata and dispatches to a domain-specific checker. Each checker awards partial credit across 5–6 criteria that sum to 1.0.

```python
class SecurityVerifier:
    def score(self):
        if self.domain == "information_flow_tracking":
            self._verify_ift()
        elif self.domain == "access_control":
            self._verify_access_control()
        elif self.domain == "side_channel":
            self._verify_side_channel()
        elif self.domain == "resource_isolation":
            self._verify_resource_isolation()
```

#### 4.2.1 Information Flow Tracking checker (`_verify_ift`)

Applicable to examples 01 (AES) and 06 (SHA-256 HMAC).

| Criterion | Points | How it's checked (AST) |
|-----------|--------|----------------------|
| Taint type defined | 0.20 | Struct exists with both `data` and `label` fields |
| Labels assigned at inputs | 0.20 | Source contains both `SECRET` and `PUBLIC` literals, and taint types exist |
| Taint propagates through operators | 0.20 | `operator^`, `operator+`, or similar overloads exist in AST |
| Taint propagates through lookups | 0.10 | Pattern `sbox[*.data]` with `.label` reference found in source |
| Explicit declassification | 0.15 | Function with "declassif", "authorize", or "check_output" in name exists |
| No untracked secret→output flows | 0.15 | No output port named "debug"/"internal_state", and no direct secret→output assignment found by flow tracing |

The taint type detection works by walking the AST for `STRUCT_DECL` nodes:

```python
def _detect_taint_types(self, cursor):
    for child in cursor.get_children():
        if child.kind in (CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL):
            fields = [c.spelling for c in child.get_children()
                      if c.kind == CursorKind.FIELD_DECL]
            has_data = any("data" in f.lower() for f in fields)
            has_label = any(kw in f.lower() for f in fields
                           for kw in ("label", "taint", "security", "tag"))
            if has_data and has_label:
                self.result.has_taint_types = True
```

#### 4.2.2 Access Control checker (`_verify_access_control`)

Applicable to examples 02 (Memory), 05 (DMA), 07 (Register File).

| Criterion | Points | How it's checked (AST) |
|-----------|--------|----------------------|
| Policy function exists | 0.25 | Function with "privilege", "access", "authorize", or "policy" in name found in AST function list |
| Policy called before access | 0.25 | Top-level function's call list includes a policy function name |
| Safe default on denial | 0.20 | Source contains `rdata = 0` pattern |
| Denial feedback | 0.15 | Source contains `access_denied` field/variable |
| No debug bypass | 0.15 | Source does NOT contain `debug_mode` |

The "policy called before access" check uses the AST's call graph:

```python
policy_names = {f.name for f in policy_funcs}
top_funcs = [f for f in self.analysis.functions if f.is_top_level]
policy_called = any(
    any(call in policy_names for call in f.calls)
    for f in top_funcs
)
```

#### 4.2.3 Side-Channel checker (`_verify_side_channel`)

Applicable to examples 03 (Constant-time compare) and 08 (Modular exponentiation).

| Criterion | Points | How it's checked (AST) |
|-----------|--------|----------------------|
| No early exit in loops | 0.30 | No `BREAK_STMT` or `RETURN_STMT` found inside any loop body in AST |
| Fixed iteration count | 0.20 | All `FOR_STMT` nodes have a condition with a numeric literal |
| Constant ops per iteration | 0.20 | `cswap` function exists, or `diff |=` pattern found, or all loops have 0 branches |
| Branchless conditionals | 0.20 | `cswap`, `|= (`, or `mask &` pattern in source |
| HLS pipeline pragmas | 0.10 | `#pragma HLS UNROLL` or `PIPELINE` found |

The early-exit detection walks the AST recursively but skips nested loops (a `break` in an inner loop is fine):

```python
def _has_early_exit(self, cursor):
    for child in cursor.get_children():
        if child.kind == CursorKind.BREAK_STMT:
            return True
        if child.kind == CursorKind.RETURN_STMT:
            return True
        if child.kind in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT):
            continue  # Don't recurse into nested loops
        if self._has_early_exit(child):
            return True
    return False
```

#### 4.2.4 Resource Isolation checker (`_verify_resource_isolation`)

Applicable to examples 04 (Key schedule), 09 (FIFO), 10 (Bus arbiter).

| Criterion | Points | How it's checked (AST) |
|-----------|--------|----------------------|
| Separate storage | 0.25 | ≥ 2 `static` array declarations found by walking `VAR_DECL` nodes |
| Sanitize on transition | 0.25 | Function named "sanitize"/"zeroize"/"clear_buffer" exists, or zeroing loop in reset handler |
| Stale data cleared | 0.20 | Pattern `[head] = 0` or `data_buf[...] = 0` in source |
| No cross-domain timing | 0.15 | `current_slot`, `tdm_schedule`, or `time_slot` in source, or no early exits in loops |
| Zeroization command | 0.15 | Sanitize function exists or `bool zeroize` parameter in source |

---

### 4.3 Dimension 3: Synthesis Pass (weight = 0.20)

**Question answered:** Can this code be synthesized to hardware?

**Two approaches tried in order:**

#### 4.3.1 Primary: AST Static Analysis

The `ASTAnalyzer.score_synthesis_compatibility()` method checks three things:

**Violations** — walks the AST for unsynthesizable constructs:

```python
UNSYNTHESIZABLE_KINDS = {
    CursorKind.CXX_NEW_EXPR: "dynamic allocation (new)",
    CursorKind.CXX_DELETE_EXPR: "dynamic deallocation (delete)",
    CursorKind.CXX_THROW_EXPR: "exception (throw)",
    CursorKind.CXX_TRY_STMT: "exception (try/catch)",
}

UNSYNTHESIZABLE_CALLS = {
    "malloc", "calloc", "realloc", "free",
    "printf", "fprintf", "sprintf", "snprintf",
    "fopen", "fclose", "exit", "system",
    "rand", "srand", "time",
}
```

Each violation is counted only if it originates in the user's source file (not in header templates):

```python
def _is_in_user_source(self, cursor):
    if not cursor.location.file:
        return False
    return os.path.abspath(cursor.location.file.name) == self.source_path
```

**Positive signals** — checks for HLS pragmas and types:
- `has_pragmas`: any `#pragma HLS INTERFACE` found
- `has_hls_types`: `ap_uint` or `ap_int` in variable/parameter type strings
- `has_streams`: `hls::stream` in variable/parameter type strings

If AST-level detection fails (Clang resolves template names), falls back to raw source text search.

**Scoring table:**

| Condition | Score | Reason |
|-----------|-------|--------|
| 0 violations + pragmas + HLS types | 1.0 | "clean" |
| 0 violations + pragmas + HLS types + invalid pragmas | 0.9 | "N invalid pragma(s)" |
| 0 violations + HLS types, no pragmas | 0.85 | "no INTERFACE pragmas" |
| 0 violations, no HLS types | 0.70 | "no HLS constructs found" |
| 1–2 violations | 0.50 | "N violation(s)" |
| 3+ violations | 0.25 | "N violations" |

The method returns `(score, reason_string)` so diagnostics explain why a score was given.

#### 4.3.2 Bonus: PandA-bambu Synthesis

If bambu is installed, the framework attempts real HLS synthesis:

```python
def score_synthesis_bambu(source_path, top_function, config):
    wrapper = generate_bambu_wrapper(source_path, top_function, work_dir)
    result = run_bambu_synthesis(wrapper, top_function, config, work_dir)
    
    if result.success and result.verilog_generated:
        return 1.0 if not result.warnings else 0.85
```

The wrapper generator translates Vitis HLS pragmas to bambu-compatible format:

| Vitis pragma | Bambu translation |
|-------------|-------------------|
| `#pragma HLS INTERFACE axis port=req_in` | `#pragma HLS INTERFACE mode=ap_fifo port=req_in` |
| `#pragma HLS INTERFACE ap_ctrl_hs port=return` | Removed (bambu auto-infers) |
| `#pragma HLS INTERFACE m_axi port=mem` | `#pragma HLS INTERFACE mode=ap_memory port=mem` |
| `#pragma HLS BIND_STORAGE ...` | Commented out (unsupported) |
| `#pragma HLS PIPELINE II=1` | Commented out (unsupported) |
| `#pragma HLS UNROLL` | Passed through (supported) |

Bambu is invoked with:
```bash
bambu source.cpp --top-fname=function_name \
    --clock-period=10 --device-name=xc7z020-1clg484-VVD \
    --generate-interface=INFER --compiler=I386_GCC8 --std=c++14 \
    -I/opt/HLS_arbitrary_Precision_Types/include \
    -I/path/to/hls_stubs
```

If bambu generates Verilog, its score overrides the AST score. If bambu fails, the AST score is used and bambu's error messages are logged in the notes.

---

### 4.4 Dimension 4: Functional Equivalence (weight = 0.15)

**Question answered:** Does the hardened code produce the same I/O behavior as the original?

**Input files:**
- LLM's `secure.cpp`
- Reference `insecure.cpp`
- Testbench `testbenches/XX/tb_XX.cpp`

**How it works:**

Each testbench is a standalone C++ program that includes both the insecure and secure DUT via namespaces, feeds test vectors, and compares outputs:

```cpp
namespace insecure {
    #include "/benchmark/examples/02_memory_access_control/insecure.cpp"
}
namespace secure {
    #include "/benchmark/examples/02_memory_access_control/reference_secure.cpp"
}

void test_nonsecure_write_read() {
    // Feed same inputs to both versions
    // Compare outputs on shared ports
    report("nonsecure_write_read", insecure_result == secure_result, "...");
}
```

The `compile_and_run.py` module handles compilation and output parsing:

```python
def run_testbench(example_id, secure_code, insecure_code, testbench_dir):
    tb_path = find_testbench(example_id, testbench_dir)
    compile_testbench(tb_path, secure_code, insecure_code, binary)
    ok, output = run_binary(binary)
    score, notes = parse_results(output)  # Parses "TEST ... PASS/FAIL" lines
    return score, notes
```

Compilation uses the Xilinx open-source `ap_int` headers (not the broken custom stubs) and a minimal `hls_stream.h` stub:

```bash
g++ -std=c++17 -O2 \
    -I/opt/HLS_arbitrary_Precision_Types/include \
    -I/path/to/hls_stubs \
    testbench.cpp -o tb
```

Testbench output format:
```
TEST 02_memory_access_control nonsecure_write_read: PASS
TEST 02_memory_access_control boundary_768_denied: PASS
SUMMARY 02_memory_access_control: 7/7 passed
```

**Score = passed / total.** If no testbench exists, defaults to 0.75.

**Test strategies by example type:**

| Example type | Strategy |
|-------------|----------|
| Same interface (02, 03, 08) | Cross-version: same inputs → compare outputs on both insecure and secure |
| Changed interface — port removed (01, 06) | Secure-only: verify determinism, non-zero output, key/plaintext sensitivity |
| Changed interface — port added (04, 07, 09, 10) | Secure-only: verify new security features work (zeroize, access control, sanitization) |

---

### 4.5 Dimension 5: Security Completeness (weight = 0.15)

**Question answered:** Does the code address ALL security properties from the specification, not just the ones flagged as vulnerabilities?

**Input files:**
- LLM's `secure.cpp` (via AST)
- Reference `security_spec.md`

**How it works:**

The `SecurityVerifier.score_completeness()` method extracts every bullet point from the security spec, then checks whether each property is addressed in the code:

```python
def score_completeness(self, spec_path):
    with open(spec_path) as f:
        spec = f.read()
    
    # Extract bullet points: "- No debug port", "- Taint must propagate", etc.
    properties = re.findall(r"[-•]\s*(.+)", spec)
    
    addressed = 0
    for prop in properties:
        if self._is_property_addressed(prop):
            addressed += 1
    
    return addressed / len(properties)
```

The `_is_property_addressed()` method uses AST structural checks first, then falls back to keyword matching:

```python
def _is_property_addressed(self, property_text):
    text_lower = property_text.lower()
    
    # Structural checks via AST
    if "no debug" in text_lower:
        return not any("debug" in p.lower() for p in self.analysis.output_ports)
    
    if "taint" in text_lower or "label" in text_lower:
        return self.analysis.has_taint_types
    
    if "access control" in text_lower:
        return any("privilege" in f.name.lower() or "access" in f.name.lower()
                   for f in self.analysis.functions)
    
    # Fallback: keyword match against function/variable names
    keywords = re.findall(r"\w{4,}", text_lower)[:3]
    all_names = [f.name.lower() for f in self.analysis.functions] + \
                [v.name.lower() for v in self.analysis.variables]
    return any(kw in name for kw in keywords for name in all_names)
```

**Why this dimension scores lower than others:** The keyword matching is conservative. A spec property like "All TOKEN_LEN bytes must always be compared" checks for the keyword "compared" in function/variable names, which usually isn't there — the code compares bytes but doesn't name anything "compared". This is a known limitation documented in the framework.

---

## 5. Composite Score and Grading

### 5.1 Per-Example Composite

```python
composite = (0.25 * detection_rate
           + 0.25 * flow_correctness
           + 0.20 * synthesis_pass
           + 0.15 * functional_equivalence
           + 0.15 * security_completeness)
```

### 5.2 Grade Bands

| Grade | Score Range |
|-------|------------|
| A | ≥ 0.90 |
| B | ≥ 0.75 |
| C | ≥ 0.60 |
| D | ≥ 0.40 |
| F | < 0.40 |

### 5.3 Difficulty-Weighted Aggregate

```python
weighted_score = Σ(example_composite × difficulty_weight) / Σ(difficulty_weight)
```

With weights: easy = 1.0, medium = 1.5, hard = 2.0. The total weight across all 10 examples is 3×1.0 + 3×1.5 + 4×2.0 = 15.5.

---

## 6. Clang AST Analysis Layer

### 6.1 Initialization

The `ASTAnalyzer` class parses source files using libclang's Python bindings:

```python
class ASTAnalyzer:
    def __init__(self, source_path, include_dirs=None):
        args = ["-std=c++17", "-fsyntax-only"]
        for d in include_dirs:
            args.append(f"-I{os.path.abspath(d)}")
        
        # Auto-detect system headers (stddef.h, etc.)
        args.extend(_get_system_include_args())
        
        index = Index.create()
        self.tu = index.parse(source_path, args=args)
```

### 6.2 System Include Detection

Libclang doesn't automatically find the system's `stddef.h`. The `_get_system_include_args()` function tries four strategies in order:

1. **Libclang's own resource dir** — asks the `libclang` Python binding where its `.so` lives, then searches relative paths for `clang/*/include/stddef.h`
2. **`clang -print-resource-dir`** — calls the system clang binary
3. **Brute-force glob** — searches `/usr/lib/llvm-*/lib/clang/*/include/`
4. **GCC include paths** — calls `gcc -E -x c++ -v /dev/null` and parses the search list

### 6.3 Analysis Passes

After parsing, six analysis passes run:

```python
def _analyze(self):
    self._extract_functions(self.tu.cursor)    # Function signatures, call graphs
    self._extract_variables(self.tu.cursor)    # Variable declarations, types
    self._extract_loops(self.tu.cursor)        # Loop bounds, early exits, branch counts
    self._extract_pragmas()                     # HLS pragma parsing from source text
    self._check_synthesis_violations(self.tu.cursor)  # Unsynthesizable constructs
    self._detect_taint_types(self.tu.cursor)   # Struct types with data+label fields
    self._identify_ports()                      # Input/output ports from function signatures
    self._trace_secret_flows(self.tu.cursor)   # Secret-to-output data flow tracing
```

### 6.4 Data Structures

The analysis produces an `AnalysisResult` containing:

```python
@dataclass
class AnalysisResult:
    functions: List[FunctionInfo]        # name, params, calls, is_top_level
    variables: List[VariableInfo]        # name, type, is_static, is_array
    loops: List[LoopInfo]               # fixed_bound, early_exit, branch_count
    pragmas: List[PragmaInfo]           # kind, args, is_valid
    synthesis_violations: List[str]      # "Line 42: dynamic allocation (new)"
    output_ports: List[str]             # ["ciphertext", "debug_out"]
    input_ports: List[str]              # ["plaintext", "key"]
    has_taint_types: bool               # True if struct with data+label found
    taint_type_names: List[str]         # ["tainted_byte"]
    has_declassification: bool          # True if declassification function exists
    secret_to_output_flows: List[str]   # ["rk -> debug_out"]
```

---

## 7. C-Simulation Layer

### 7.1 Header Strategy

The framework uses two sets of headers:

| Header | Source | Used by |
|--------|--------|---------|
| `ap_int.h`, `ap_uint.h`, `ap_fixed.h` | Xilinx `HLS_arbitrary_Precision_Types` (Apache 2.0) | g++ testbenches, Clang AST |
| `hls_stream.h` | Custom stub (wrapper around `std::queue`) | g++ testbenches, Clang AST |

The Xilinx headers provide bit-accurate `ap_uint<W>` simulation. The `hls_stream.h` stub provides a queue-based `hls::stream<T>` that matches the Vitis API.

### 7.2 Testbench Compilation

```python
cmd = ["g++", "-std=c++17", "-O2"]
if os.path.isdir(_XILINX_HLS_INCLUDE):
    cmd.append(f"-I{_XILINX_HLS_INCLUDE}")
cmd.append(f"-I{_LOCAL_STUBS}")  # for hls_stream.h
cmd.extend([testbench_path, "-o", output_binary])
```

### 7.3 Output Parsing

```python
def parse_results(output):
    summary = re.search(r"SUMMARY\s+\S+:\s+(\d+)/(\d+)\s+passed", output)
    if summary:
        passed, total = int(summary.group(1)), int(summary.group(2))
        return passed / total, notes
```

---

## 8. PandA-bambu Synthesis Layer

### 8.1 Architecture

```
bambu_backend.py
├── generate_bambu_wrapper()    # Translate Vitis pragmas → bambu format
├── run_bambu_synthesis()       # Invoke bambu, parse results
├── score_synthesis_bambu()     # Scoring wrapper
├── score_cosim_bambu()         # Co-simulation scoring (optional)
└── detect_top_function()       # Find top-level function from pragmas
```

### 8.2 Pragma Translation

The wrapper generator rewrites Vitis-style pragmas for bambu compatibility:

```python
IFACE_MAP = {
    "ap_ctrl_hs": "ap_hs",
    "axis": "ap_fifo",
    "m_axi": "ap_memory",
    "ap_none": "ap_none",
    "s_axilite": "ap_none",
}
```

Unsupported pragmas (`PIPELINE`, `BIND_STORAGE`, `LOOP_TRIPCOUNT`, `ARRAY_PARTITION`) are commented out with a `// [bambu]` prefix. `port=return` lines are removed entirely.

### 8.3 Docker Integration

The Dockerfile extracts bambu from an AppImage and creates a wrapper script:

```bash
#!/bin/bash
export APPDIR=/opt/bambu/squashfs
export PATH=/opt/bambu/squashfs/usr/bin:...
export LD_LIBRARY_PATH=/opt/bambu/squashfs/usr/lib:...
exec /opt/bambu/squashfs/usr/bin/bambu "$@"
```

### 8.4 Current Limitations

The bundled Clang-12 and Clang-16 in the AppImage segfault on the Xilinx `ap_int` headers due to glibc incompatibility with Ubuntu 22.04. GCC-8 parses the code but bambu's IR processing fails with "Parse error" on the complex template instantiations. As a result, bambu synthesis currently falls back to AST scoring for all 10 examples.

---

## 9. Output Format

### 9.1 Console Output

```
01_aes_ift: composite=0.900 grade=B [medium]
    detection=1.00  security=1.00  synth=1.00  func=1.00  complete=0.33
    → bambu: score=0.25, top=aes_encrypt
    → bambu error: clang-12: error: clang frontend command failed with exit code 139
```

### 9.2 JSON Report

```json
{
  "model": "unknown",
  "mode": "simulate",
  "examples": [
    {
      "id": "01_aes_ift",
      "scores": {
        "detection_rate": 1.0,
        "flow_correctness": 1.0,
        "synthesis_pass": 1.0,
        "functional_equivalence": 1.0,
        "security_completeness": 0.33
      },
      "composite": 0.9,
      "grade": "B",
      "notes": ["..."],
      "property_details": [
        {"description": "Taint-tracked data type defined", "passed": true, "score": 0.2}
      ]
    }
  ],
  "aggregate": {
    "mean_composite": 0.886,
    "difficulty_weighted": 0.886,
    "grade": "B"
  }
}
```

---

## 10. File Manifest

```
hls-security-benchmark/
├── Dockerfile                          # Docker image with bambu + all tools
├── docker-compose.yml                  # Docker Compose services
├── docker-entrypoint.sh                # Smart entrypoint (eval / shell / bambu)
├── README.md                           # Quick start guide
│
├── examples/                           # 10 benchmark examples
│   └── XX_name/
│       ├── insecure.cpp                # Vulnerable input code
│       ├── reference_secure.cpp        # Gold-standard hardened code
│       ├── vulnerability_report.md     # Expected findings
│       ├── security_spec.md            # Required security properties
│       ├── prompt.md                   # Task prompt for the LLM
│       └── metadata.json              # CWE IDs, domain, difficulty
│
└── evaluation/
    ├── run_evaluation.py               # v1: regex-only (legacy)
    ├── run_evaluation_v2.py            # v2: AST + simulation + bambu
    ├── scoring_rubric.json             # Example list, weights, grade bands
    ├── evaluation_framework.md         # High-level evaluation design doc
    │
    ├── analysis/
    │   ├── ast_analyzer.py             # Clang AST parsing (760 lines)
    │   └── security_verifier.py        # Domain-specific property checkers (350 lines)
    │
    ├── sim_backend/
    │   ├── ARCHITECTURE.md             # Architecture overview
    │   ├── bambu_backend.py            # PandA-bambu synthesis integration (525 lines)
    │   ├── compile_and_run.py          # g++ testbench compiler/runner (210 lines)
    │   └── hls_stubs/
    │       └── hls_stream.h            # Minimal hls::stream stub for g++
    │
    └── testbenches/                    # 10 C++ testbenches (one per example)
        └── XX_name/
            └── tb_XX_name.cpp
```