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
- `adversarial_ht_generation`: adversarial Trojan generation for detector stress-testing
- `logic_deobfuscation_sat`: logic deobfuscation and SAT-attack assistance

Domain behavior is centralized in `src/agentic_bench_gen/domains.py`, so new task families can be added without rewriting the pipeline.

## Pipeline

The generation flow is:

1. `IdeaGenerator`: expands seed rows into concrete benchmark ideas.
2. `Architect`: creates a domain-specific task spec.
3. `ArtifactBuilder`: creates participant-facing inputs.
4. `Expert`: creates the secure golden implementation or private oracle.
5. `Tester`: creates atomic requirement-level harnesses and evaluators.
6. `Mutator`: creates insecure/incorrect variants for quality filtering.
7. `Validator`: deterministic checks for required files, metrics, harness coverage, and safety.
8. `Analyzer`: LLM review of coherence and evaluability.
9. `Arbiter`: retains the case or sends one artifact back for repair.
10. `Quality`: deterministic coverage/mutation/analyzer summary.

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
```

## Install

```bash
cd agentic-bench-gen
python -m pip install -e .
```

Set OpenRouter credentials before generation:

```bash
export OPENROUTER_API_KEY=...
```

## Generate

```bash
agentic-bench-gen --config config/pipeline.yaml generate \
  --seed examples/multi_domain_seeds.yaml \
  --out runs/demo
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
