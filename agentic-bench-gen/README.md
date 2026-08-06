# AgenticBenchGen

AgenticBenchGen is a modular agentic benchmark generation pipeline for hardware security and reliability tasks.

It follows the infrastructure style used in `hls-bench-agentic` and `agentic-reverse-eng`: YAML-configured JSON agents, strict schemas, prompt templates, workspace materialization, validation reports, analyzer reports, arbiter repair loops, and reproducible case folders.

It is now organized around the HardSecBench construction pattern: CWE/security seeds are expanded into structured specs that separate public functional requirements from hidden security requirements; golden artifacts and test harnesses are synthesized in independent branches; the Arbiter reconciles mismatches using execution/validation evidence; and final quality gates consider requirement coverage plus mutation discrimination.

## Supported Domains

- `hls_security_codegen`: security-aware HLS code generation and auditing
- `rtl_trojan_detection`: RTL-level Hardware Trojan detection
- `gate_trojan_detection`: gate-level Trojan detection and suspect-node localization
- `hardware_reverse_engineering`: netlist/obfuscated RTL lifting
- `side_channel_fault_analysis`: RTL side-channel and fault-analysis assessment
- `logic_deobfuscation_sat`: logic deobfuscation and SAT-attack assistance

Domain behavior is centralized in `src/agentic_bench_gen/domains.py`, so new task families can be added without rewriting the pipeline.

## Pipeline

The generation flow is:

1. `IdeaGenerator`: expands seed rows into concrete benchmark ideas.
2. `Architect`: creates a domain-specific task spec.
3. `ArtifactBuilder`: creates participant-facing inputs (a functional but intentionally insecure baseline).
4. `Expert`: creates the secure golden implementation or private oracle (mirroring input filenames under `golden/`).
5. `Tester`: creates atomic requirement-level harnesses and the `evaluation/evaluate.py` grader.
6. `Mutator`: creates corrupted golden submissions targeting every functional and security requirement for quality filtering.
7. `Validator`: deterministic checks — required files, metrics, harness coverage, the differential gate, and dynamic mutation scoring.
8. `Analyzer`: LLM review of coherence and evaluability.
9. `Arbiter`: retains the case or sends one artifact back for repair.
10. `Quality`: deterministic coverage/mutation/analyzer summary.

### Evaluator semantics (grader convention)

`evaluation/evaluate.py` grades a **submission**. What counts as the submission is set per domain by its *submission contract* (`domains.py`), which has two kinds:

- **`hardened_artifact`** (e.g. `hls_security_codegen`): the participant edits a code input in place; the evaluator grades the file(s) under `inputs/`. The shipped `inputs/` code is the intentionally-insecure baseline submission.
- **`analysis_report`** (the other five domains): the participant does not touch the inputs; they submit a separate answer file under `submission/` (e.g. `submission/trojan_report.json`, `submission/recovered_key.json`). The evaluator *reads* the input artifacts for reference and *grades* the answer file. The case ships a naive/empty starter answer as the baseline submission.

In both cases:

- A correct submission (e.g. the expert golden answer) must be **accepted** — exit 0 with `[TEST] PASS` for every requirement.
- The shipped baseline submission must be **rejected** — exit non-zero with at least one `[TEST] FAIL`.
- Mutants (a correct submission with one reintroduced defect) must be **rejected**.

**How grading works (evaluation contract):** the Expert and Tester generate independently and share only the task spec — in particular `public_spec.interface`, the pinned entry-point contract the Architect must make machine-checkable (the validator gates on it for hardened_artifact domains). To make that isolation workable, each domain declares an `evaluation_mode` in `domains.py`: `compile_and_run` (HLS C/C++ — evaluate.py compiles the submission with g++ against a Tester-written harness and grades observed behavior), `simulate` (RTL submissions — iverilog + vvp testbench), or `report_grading` (answer files graded against hidden ground truth). Behavioral checks are style-invariant by construction; the only permitted static source checks are *fail-on-presence* vulnerability/banned-construct patterns, which can never false-reject a correct rewrite. PASS-on-presence source matching (requiring baseline-styled loops, identifier names, table spellings) is forbidden — it was the root cause of golden rejections.

The validator enforces both directions deterministically: the *differential gate* overlays the golden answer onto the domain's submission path(s) and requires that run to pass, and requires the as-shipped baseline run to fail. Dynamic mutation scoring then stages each mutant on top of the golden overlay and measures how many the evaluator rejects (`mutation_score_meaningful: false` marks scores computed after a failed golden/baseline run). `domains.submission_paths()` is the single source of truth for where the submission lives, shared by the overlay logic and the prompt contract text so `evaluate.py` and the staging never disagree. A pre-flight in the orchestrator runs the differential gate right after the Tester and retries the Tester with the evaluator's runtime output (never the golden source) up to `pipeline.tester_preflight_retries` times, re-checking each retry and keeping the best bundle, before falling back to full Arbiter repair rounds. When the gate still fails after all retries, the round skips mutant generation entirely — a broken evaluator grades every mutant meaninglessly, so those Mutator calls would be pure waste. Two more deterministic guards run before the Tester ever sees the spec: `public_spec.input_artifacts` is reconciled to the files the ArtifactBuilder actually shipped under `inputs/` (a declared-but-unshipped filename otherwise sends `evaluate.py` into an unfixable SETUP failure on every run), and CWE/SR identifiers that leak into public spec text are scrubbed at normalize time (hardened_artifact domains).

**The Arbiter can blame the mutants, not just the checks:** an undetected mutant has two possible root causes — a weak check, or a mutant that never genuinely violated its requirement (semantically equivalent edits, cosmetic changes, wrong file). The Arbiter sees the undetected mutants' full file content and may set `artifact_to_revise: "mutants"` (root cause `mutation_issue`). Such a round re-runs only the Mutator, selectively: mutants that already demonstrated discrimination are kept as-is, only the flagged targets are regenerated, the failed (operator, target) combinations are forbidden, and the Arbiter's diagnosis travels to the Mutator as repair notes.

**Repair rounds patch, not rewrite:** on every retry — Arbiter-directed repair rounds and Tester pre-flight retries alike — the regenerating agent (ArtifactBuilder, Expert, Tester) receives its own previous bundle alongside the repair notes, with instructions to keep the file set, architecture, and unimplicated content identical and apply the smallest change that resolves the notes. Without this, agents redesign the bundle from scratch each round and regularly regress checks that already worked. Per-round history survives keep-best: `validation_report_r<N>.json`, `analyzer_report_r<N>.json`, and `arbiter_decision_r<N>.json` are written every round and preserved across a keep-best restore (which also writes `reports/keep_best.json` recording which round was restored), so a regressing round can always be debugged after the fact. The Arbiter — and only the Arbiter — also sees the golden solution to localize mismatches (its prompt forbids echoing golden code into revision instructions, so Tester-side isolation is preserved).

The Mutator deliberately never sees the evaluator's check code or detection strategies — only requirement ids/types and the requirement text from the task spec. Mutants are an independent sample of plausible defects; showing the checks would let mutants be tailored to them and make the mutation score circular.

### Token budgets

File-emitting agents (`per_file: true` in agents.yaml) generate bundles in two phases — a JSON plan (manifest, no contents), then one plain-text completion per file — so no single response has to fit an entire bundle under an output-token cap, and a truncated file retries alone. Extended reasoning is explicitly disabled in the pipeline and both agent configuration files. Per-call token usage is printed to the console.

Generated workspaces contain:

```text
spec/task_spec.json
spec/public_spec.json
spec/hidden_spec.json
artifacts/artifact_bundle.json
expert/expert_bundle.json
tests/tester_bundle.json
mutants/mutation_bundle.json
reports/validation_report.json
reports/analyzer_report.json
reports/arbiter_decision_r*.json
reports/quality_report.json
reports/selection.json
case_manifest.json
```

Cases are built in hidden staging directories and atomically published only
after all canonical reports and `case_manifest.json` are complete. Each output
run also maintains an atomically updated `run_manifest.json` with `published`,
`published_quality_failed`, `failed`, or `interrupted` case states. A completed
author bundle is therefore not mistaken for a benchmark that passed quality gates.

Validation reports distinguish `requirement_mapping_coverage_score` (every
declared requirement has a harness mapping) from
`requirement_discrimination_coverage_score` (the requirement's own check kills
its targeting mutant). `coverage_score` remains a compatibility alias for the
mapping score.
When the differential gate fails before mutation, validation records
`mutation_status: blocked_by_differential` instead of reporting every requirement
as an independent untested-mutant defect.

## Install

```bash
cd agentic-bench-gen
python -m pip install -e .
```

Set OpenRouter credentials before generation:

```bash
export OPENROUTER_API_KEY=...
```

## Evaluation Sandbox

Generated `evaluate.py` and mutant code are untrusted LLM output, so they run
inside a single shared, network-isolated Docker container (one image reused for
every case and mutant; the case workspace is bind-mounted at `/work`). Build it
once before generating:

```bash
docker build -t agentic-bench-gen-runner:latest docker/
```

The image ships the behavioral-grading toolchain: `gcc`/`g++` (compile-and-run
grading of HLS C/C++ kernels), `iverilog`/`vvp` (RTL simulation) and `yosys`
(netlist analysis). A true HLS synthesis flow (Bambu / Vitis HLS) is
deliberately not included — HLS synthesizability is enforced as static subset
checks, while functional and security properties are graded by compiling with
g++ and executing. Add further tools to `docker/Dockerfile` as the benchmark
grows — evaluators pick them up with no runner code changes. Isolation knobs
live under `execution:` in `config/pipeline.yaml`; set `use_docker: false`
there to fall back to host execution (trusted/dev runs only — host runs also
need the toolchain on PATH).

## Generate

`examples/multi_domain_seeds_set3.yaml` contains the 30 newest scenarios, with
five seeds in each supported domain. Seed files are validated before any model
calls for required fields, known domains, non-empty constraints, and unique IDs
within the file.

```bash
agentic-bench-gen --config config/pipeline.yaml generate \
  --seed examples/multi_domain_seeds_set3.yaml \
  --out runs/demo
```

To use DeepSeek V4 Pro for every agent instead of the default model:

```bash
agentic-bench-gen --config config/deepseek_pipeline.yaml generate \
  --seed examples/multi_domain_seeds_set3.yaml \
  --out runs/deepseek-v4-pro
```

## Validate

```bash
agentic-bench-gen validate --case runs/demo/<case_id>
```

## Adapting To A New Domain

1. Add a `DomainProfile` in `src/agentic_bench_gen/domains.py`.
2. Add seeds with the new `domain_id`.
3. If needed, specialize the prompts with extra domain guidance.
4. Add validator checks for any new required artifact patterns.

The Tester should generate requirement-level harnesses and a lightweight evaluator. This keeps each generated benchmark case self-contained enough for a GitHub repository while preserving HardSecBench-style independence between the golden solution and the verification branch.
