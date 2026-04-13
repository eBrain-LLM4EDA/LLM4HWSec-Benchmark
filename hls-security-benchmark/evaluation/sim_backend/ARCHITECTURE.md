# Simulation Backend Architecture

## Overview

The simulation backend replaces regex-based heuristics with three analysis layers
that each address a different evaluation dimension:

```
┌──────────────────────────────────────────────────────────────┐
│                     run_evaluation.py                        │
│                   (orchestrator — unchanged CLI)             │
├──────────────┬──────────────────┬────────────────────────────┤
│  Layer 1     │  Layer 2         │  Layer 3                   │
│  Clang AST   │  C-Simulation    │  Security Property         │
│  Analyzer    │  (Testbenches)   │  Verification              │
├──────────────┼──────────────────┼────────────────────────────┤
│ Synthesis    │ Functional       │ IFT correctness            │
│ pass check   │ equivalence      │ Access control policy      │
│              │                  │ Side-channel resistance    │
│ HLS pragma   │ Golden I/O       │ Sanitization checks        │
│ validation   │ comparison       │                            │
└──────────────┴──────────────────┴────────────────────────────┘
```

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| PandA-bambu | **Primary HLS synthesis + co-simulation** | AppImage from GitHub releases |
| Verilator | RTL co-simulation backend for bambu | `apt install verilator` |
| Clang 14+ | AST parsing via libTooling or python bindings | `apt install clang libclang-dev` |
| `libclang` Python bindings | AST traversal from Python | `pip install libclang` |
| g++ with HLS stubs | Compile testbenches without any HLS tool | See `sim_backend/hls_stubs/` |

### PandA-bambu (primary synthesis backend)

PandA-bambu is an open-source HLS framework from Politecnico di Milano that
accepts standard C/C++ and generates Verilog/VHDL. It replaces Vitis HLS
entirely — no Xilinx license needed.

**Install via AppImage (easiest):**
```bash
# Download latest release
wget https://github.com/ferrandi/PandA-bambu/releases/latest/download/bambu-Ubuntu_22.04.AppImage
chmod +x bambu-Ubuntu_22.04.AppImage
sudo mv bambu-Ubuntu_22.04.AppImage /usr/local/bin/bambu

# Install co-simulation backend
sudo apt install verilator

# Verify
bambu --version
```

**Install from source (for development):**
```bash
git clone https://github.com/ferrandi/PandA-bambu.git
cd PandA-bambu && mkdir build && cd build
../configure --prefix=/opt/panda --enable-opt --enable-release
make -j$(nproc) && make install
export PATH=/opt/panda/bin:$PATH
```

**What bambu gives us that Vitis doesn't (for free):**
- Actual RTL synthesis from C/C++ (Verilog output)
- Co-simulation via Verilator (compares RTL behavior to C golden model)
- Latency and area estimates
- Support for `#pragma HLS` interface/unroll/pipeline/inline
- Initial support for `ap_uint`/`ap_int` types (since PandA 2024.10)
- Targets: Xilinx, Intel/Altera, Lattice, NanoXplore FPGAs + ASIC via OpenROAD

**How bambu is invoked for each benchmark example:**
```bash
# Basic synthesis (generates Verilog)
bambu secure.cpp --top-fname=aes_encrypt \
    --clock-period=10 \
    --device-name=xc7z020-1clg484-VVD \
    --generate-interface=INFER \
    --experimental-setup=BAMBU-BALANCED

# Synthesis + co-simulation (verifies RTL matches C)
bambu secure.cpp --top-fname=aes_encrypt \
    --clock-period=10 \
    --device-name=xc7z020-1clg484-VVD \
    --generate-interface=INFER \
    --simulate --simulator=VERILATOR
```

### Running WITHOUT bambu

If bambu is not installed, the evaluation framework automatically falls back to:
- Layer 1 (AST analysis via Clang) — for synthesis compatibility static checks
- Layer 2 (C-simulation via g++ with stubs) — for functional equivalence
- Layer 3 (security verification via AST) — fully supported

This covers everything except the "actual RTL was generated" confirmation.

---

## Layer 1: Clang AST Analyzer

**Replaces:** `score_synthesis()` regex checks
**File:** `analysis/ast_analyzer.py`

### What it does

Parses the submitted C++ source into a Clang AST and performs structural checks
that regex cannot reliably do:

1. **Synthesis compatibility** — walks the AST looking for unsynthesizable constructs
   (dynamic allocation, recursion, system calls, exceptions, virtual functions, etc.)
   as actual AST node types, not string patterns.

2. **HLS pragma validation** — extracts all `#pragma HLS` directives and validates
   their syntax against Vitis HLS's pragma grammar (e.g., `PIPELINE` requires `II=`,
   `INTERFACE` requires `port=`, etc.).

3. **Data flow analysis** — builds a def-use chain for variables tagged as SECRET
   in the source. Traces every use of those variables through assignments, function
   calls, and return values to determine if they reach any output port.

4. **Control flow analysis** — identifies loops whose trip count depends on a SECRET
   variable (data-dependent iteration), and branches whose condition depends on
   SECRET data (data-dependent branching).

### Why AST over regex

Consider the false positive from the user's run: "Debug/diagnostic port still present"
was flagged because the regex found the word `debug` in a comment. AST analysis
distinguishes between:
- A function parameter named `debug_out` (real port — flag it)
- A comment saying "// debug port removed" (not a port — ignore it)
- A local variable `debug_count` used for internal logic (not an output — ignore it)

---

## Layer 2: C-Simulation with Testbenches

**Replaces:** The placeholder `functional_equivalence = 0.75`
**Files:** `testbenches/<example_id>/tb_<example_id>.cpp`

### What it does

Each example gets a C++ testbench that:

1. Instantiates both the insecure and secure top-level functions.
2. Feeds identical test vectors into both.
3. Compares outputs on shared ports (ports that exist in both versions).
4. Reports pass/fail per test vector.

The testbench compiles with g++ using the HLS stub headers — no Vitis needed.

### Test vector strategy

| Example | Vector source | Count |
|---------|--------------|-------|
| 01 AES IFT | Known-answer tests (NIST FIPS 197) | 4 |
| 02 Memory AC | Read/write to each region × each requestor | 16 |
| 03 Const-time | All-match, first-mismatch, last-mismatch, random | 8 |
| 04 Key sched | Key load → process → zeroize cycle | 6 |
| 05 DMA | Each channel × secure/non-secure region | 12 |
| 06 SHA-256 | Known HMAC-SHA256 vectors (RFC 4231) | 4 |
| 07 Reg file | Each master × each register group × read/write | 20 |
| 08 ModExp | Small known modexp results | 4 |
| 09 FIFO | Push/pop/ctx_switch/reset sequences | 10 |
| 10 Bus arbiter | Per-slot request patterns | 8 |

### Compilation

```bash
g++ -std=c++17 -I sim_backend/hls_stubs/ \
    testbenches/01_aes_ift/tb_01_aes_ift.cpp \
    -o tb_01 && ./tb_01
```

Output is machine-parseable:
```
TEST 01_aes_ift vector_0: PASS
TEST 01_aes_ift vector_1: PASS
TEST 01_aes_ift vector_2: FAIL output_mismatch ciphertext expected=0xABCD got=0x0000
SUMMARY 01_aes_ift: 2/3 passed
```

---

## Layer 3: Security Property Verification

**Replaces:** `_score_ift()`, `_score_access_control()`, etc. (regex checks)
**File:** `analysis/security_verifier.py`

### What it does

Uses the Clang AST (from Layer 1) combined with runtime instrumentation (from Layer 2)
to verify security properties with actual analysis instead of pattern matching.

#### 3a. Information Flow Tracking verification

Instead of grepping for `struct tainted`, the verifier:

1. Identifies all input parameters and their security labels (from `security_spec.md`).
2. Walks the AST def-use graph from each SECRET input.
3. Checks that every operation on a SECRET value produces a result that is either:
   - Also marked SECRET (if taint types are used), OR
   - Never reaches a PUBLIC output port.
4. Checks that every output port either:
   - Receives only PUBLIC-labeled data, OR
   - Has an explicit declassification guard.

#### 3b. Access control verification

Instead of grepping for `has_privilege`, the verifier:

1. Identifies all memory write/read operations in the AST.
2. For each, checks if there is a **dominating** conditional (in the control flow graph)
   that tests the requestor's privilege before the access.
3. Checks that the "else" branch of denied access writes a safe default (zero).

#### 3c. Side-channel verification

Instead of grepping for `break`, the verifier:

1. Builds the control flow graph.
2. Identifies all loops.
3. For each loop, checks:
   - Does the loop bound depend on any SECRET variable? (variable trip count)
   - Does any branch inside the loop depend on a SECRET variable? (data-dependent branch)
   - Does the loop contain `break` or early `return`? (early exit)
4. Counts operations per loop iteration across all paths. If the count differs
   between paths → side channel.

#### 3d. Resource isolation / sanitization verification

Instead of grepping for `sanitize`, the verifier:

1. Identifies all array declarations.
2. For each reset/context-switch handler (identified by checking for
   `reset` or `ctx_switch` in the condition of an `if`):
   - Walks the body to check if every array element is overwritten.
3. For each pop/dequeue operation:
   - Checks if the popped slot is zeroed after reading.

---

## Integration: How it all fits into run_evaluation.py

The `evaluate_example()` function is modified to call the real backends
instead of the regex functions:

```python
def evaluate_example(submission_dir, reference_dir, rubric, use_simulation=True):
    metadata = load_metadata(reference_dir)
    scores = DimensionScores()

    sub_code = os.path.join(submission_dir, "secure.cpp")
    sub_vr   = os.path.join(submission_dir, "vulnerability_report.md")

    # Dim 1: Detection rate — unchanged (compares markdown reports)
    scores.detection_rate = score_detection(sub_vr, reference_dir, metadata)

    if use_simulation:
        # Dim 2: Security properties — AST-based (Layer 1 + 3)
        ast = ASTAnalyzer(sub_code, stubs_dir="sim_backend/hls_stubs/")
        scores.flow_correctness = SecurityVerifier(ast, metadata).score()

        # Dim 3: Synthesis pass — AST-based (Layer 1)
        scores.synthesis_pass = ast.score_synthesis_compatibility()

        # Dim 4: Functional equivalence — C-sim (Layer 2)
        scores.functional_equivalence = run_testbench(
            example_id=metadata["id"],
            secure_code=sub_code,
            insecure_code=os.path.join(reference_dir, "insecure.cpp"),
            testbench_dir="testbenches/"
        )

        # Dim 5: Security completeness — AST-based (Layer 3)
        scores.security_completeness = SecurityVerifier(ast, metadata).score_completeness(
            spec_path=os.path.join(reference_dir, "security_spec.md")
        )
    else:
        # Fallback to regex (current behavior)
        ...
```

---

## File manifest

```
evaluation/
├── run_evaluation.py          # Original regex-only evaluator
├── run_evaluation_v2.py       # Updated: regex / simulate / bambu modes
├── scoring_rubric.json        # Unchanged
├── evaluation_framework.md    # Unchanged
│
├── sim_backend/
│   ├── ARCHITECTURE.md        # This file
│   ├── bambu_backend.py       # PandA-bambu synthesis + co-sim integration
│   ├── compile_and_run.py     # g++ testbench compiler/runner
│   └── hls_stubs/             # Header-only HLS type stubs for g++
│       ├── ap_int.h
│       └── hls_stream.h
│
├── analysis/
│   ├── ast_analyzer.py        # Clang AST parsing + synthesis checks
│   └── security_verifier.py   # AST-based security property verification
│
└── testbenches/
    ├── 02_memory_access_control/
    │   └── tb_02_memory_access_control.cpp
    └── ...                    # One testbench per example
```
