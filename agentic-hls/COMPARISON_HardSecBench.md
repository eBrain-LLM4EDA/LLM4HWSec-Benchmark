# Framework Comparison: HLSSecBench Agentic Generator vs. HardSecBench

This document compares the agentic HLS security benchmark framework in `hlssecbench_openrouter/` with
**HardSecBench** ("HardSecBench: A Comprehensive Benchmark for Evaluating Security Awareness of LLMs
for Hardware Code Generation," arXiv 2601.13864).

---

## 1. High-Level Purpose

| | HLSSecBench (this repo) | HardSecBench (paper) |
|---|---|---|
| **Primary goal** | *Generate* new benchmark tasks using an LLM pipeline | *Evaluate* LLMs against a static, curated benchmark |
| **Output** | A growing library of tasks produced on demand | 924 fixed tasks released as a dataset |
| **Consumer of tasks** | Any target LLM via `hlssecbench evaluate` | The research community running model comparisons |

The fundamental difference is generative vs. static. HLSSecBench is a benchmark **factory**; HardSecBench is a benchmark **collection**.

---

## 2. Hardware Domain Coverage

| | HLSSecBench | HardSecBench |
|---|---|---|
| **Primary language** | HLS C/C++ (Vitis HLS style) | Verilog RTL + Firmware C |
| **Abstraction level** | High-Level Synthesis (pre-RTL) | Register-Transfer Level + embedded firmware |
| **Toolchain integration** | Vitis HLS (csim → synth → cosim → RTL security) | General Verilog simulation / compilation |
| **HLS-specific threats** | First-class (see §4) | Not addressed |

HardSecBench covers the post-synthesis RTL and firmware domains. HLSSecBench sits one level higher—at the C/C++ HLS source level—where security flaws introduced before synthesis (pragma misuse, secret-dependent loops, etc.) are the primary concern.

---

## 3. Scale and Coverage

| | HLSSecBench | HardSecBench |
|---|---|---|
| **Task count** | Seed-driven; starts at 0, grows with seeds | 924 tasks (fixed) |
| **CWE coverage** | HLS-specific subset (timing, pragma, interface) | 76 hardware-relevant CWEs (broad) |
| **Vulnerability themes** | Timing leakage, secret-dependent branches, AXI handshake, debug registers, reset/zeroization, C/RTL mismatch | Full CWE taxonomy mapped to RTL/firmware flaws |
| **Multi-domain** | No (HLS C/C++ only) | Yes (Verilog + C firmware) |

HardSecBench has broader CWE coverage; HLSSecBench has deeper coverage of HLS-specific attack surfaces that are absent from HardSecBench.

---

## 4. HLS-Specific Security Concerns (Unique to HLSSecBench)

The Architect and Mutator agents explicitly target vulnerabilities that only exist at the HLS level:

- Secret-dependent branches and loop trip counts surviving HLS to RTL
- HLS pragmas (`PIPELINE`, `ARRAY_PARTITION`, etc.) that introduce unintended resource sharing or timing channels
- AXI-lite / `ap_done` / `valid`-`ready` handshake timing dependent on secret data
- C/RTL co-simulation mismatches where security properties hold in C but break in synthesized RTL
- Debug/status register leakage introduced during HLS directives

These categories have no equivalent in HardSecBench, which evaluates at the RTL or firmware levels where HLS transformations are already fixed.

---

## 5. Agent Architecture

### HLSSecBench — 7 specialized agents

```
Architect  →  Expert  →  Tester  →  Runner
                                      ↓
                          Security Analyzer  →  Arbiter
                                      ↓
                                   Mutator
```

| Agent | Role |
|---|---|
| **Architect** | Transforms a YAML seed into a structured task spec (public + hidden) |
| **Expert** | Generates the secure reference implementation |
| **Tester** | Independently generates testbenches from the spec (not from Expert output) |
| **Security Analyzer** | Inspects execution logs and verdicts per requirement |
| **Arbiter** | Diagnoses inconsistencies and recommends repair or retention |
| **Mutator** | Produces insecure variants to validate test detection capability |
| **Target Model** | The LLM under evaluation; sees only the public spec |

### HardSecBench — decoupled synthesis / verification

HardSecBench proposes a multi-agent pipeline that separates synthesis (code generation) from verification
(security assessment), but the paper does not describe individual agent roles at the same level of
granularity. The benchmark itself is a curated artifact rather than a live agent workflow.

**Key structural difference:** In HLSSecBench, the Tester agent generates tests *independently* from the
Expert's implementation, preventing tests from being coupled to a single reference solution.
HardSecBench's test generation methodology is not specified in the paper.

---

## 6. Information Asymmetry (Public vs. Hidden Spec)

HLSSecBench enforces a deliberate split:

- **Public spec** — functional requirements only; what the target model sees
- **Hidden spec** — security requirements; used only by Expert, Tester, Analyzer, Arbiter, and Mutator

This design ensures that a target model cannot trivially satisfy security requirements by reading them
in the prompt. It must infer or independently apply secure coding practices.

HardSecBench does not appear to use this public/hidden split; tasks are presented as single prompts
asking the model to produce secure code, and evaluation checks the output.

---

## 7. Mutation Testing

| | HLSSecBench | HardSecBench |
|---|---|---|
| **Mutation testing** | First-class, dedicated Mutator agent | Not described in the paper |
| **Mutants per task** | Configurable (default 5) | N/A |
| **Mutation targets** | HLS-specific flaws (secret-dependent exit, bad pragmas, debug leaks, etc.) | N/A |
| **Detection signal** | Test suite failure or timeout on the mutant | N/A |
| **Quality gate** | Min mutation score 0.60; ≥1 mutant detected per security requirement | N/A |

Mutation testing serves as the primary mechanism for validating that the testbench is *sensitive*—a
task is only retained if its tests can distinguish secure from insecure code. HardSecBench validates
benchmark quality through different means (manual curation, CWE alignment).

---

## 8. Evaluation Methodology

| | HLSSecBench | HardSecBench |
|---|---|---|
| **Task types** | Secure code generation only | Secure code generation + vulnerability detection |
| **Ground truth** | Expert-generated secure reference + test suite | Curated secure reference + executable tests |
| **Execution** | Optional HLS toolchain (csim, synth, cosim, RTL security script) | Verilog simulation / compilation checks |
| **Metrics** | Pass/fail per requirement, mutation score, C/RTL coverage | Security-correct generation rate across models |
| **Comparative evaluation** | Not built-in (single model at a time) | Explicit comparison: Claude, GPT-o1, Gemini, Qwen, DeepSeek, etc. |
| **Prompting sensitivity** | Not studied (generator side) | Explicitly studied ("security results vary with prompting") |

---

## 9. Quality Gates

HLSSecBench enforces programmatic retention criteria before a task enters the benchmark:

| Gate | Threshold |
|---|---|
| Secure reference must pass all requirements | Required |
| C-simulation coverage | ≥ 80 % |
| RTL co-simulation coverage | ≥ 70 % |
| Security mutation score | ≥ 60 % |
| ≥ 1 mutant detected per security requirement | Required |

HardSecBench relies on manual curation and CWE alignment for quality assurance. No automated
mutation-score threshold is described.

---

## 10. LLM Provider and Model Access

| | HLSSecBench | HardSecBench |
|---|---|---|
| **API layer** | OpenRouter (model-agnostic; any OpenRouter-supported model) | Direct API calls to individual providers |
| **Generator model** | Configurable (default `openai/gpt-5.2` per `agents.yaml`) | Not applicable (static benchmark) |
| **Models evaluated** | Any model reachable via OpenRouter | Claude, GPT-o1, Gemini, Qwen variants, DeepSeek, and others |
| **Switching models** | Change one line in `agents.yaml` | Re-run evaluation against each model separately |

---

## 11. Task Lifecycle Summary

### HLSSecBench pipeline (per seed)

```
YAML seed → Architect (task spec) → Expert (reference impl) → Tester (harnesses)
         → Runner (csim/synth/cosim/RTL) → Security Analyzer → Arbiter
         → Mutator (insecure variants) → Quality gates → retained task
         ↓
Target Model evaluation (public spec only) → candidate impl → test suite → report
```

### HardSecBench pipeline (per task)

```
Curated spec → LLM prompt → generated code → executable tests → pass/fail verdict
```

---

## 12. Maturity and Availability

| | HLSSecBench | HardSecBench |
|---|---|---|
| **Status** | Research scaffold (explicitly noted in README) | Peer-reviewed paper; dataset forthcoming |
| **Manual audit** | Not yet included (flagged as future work) | Curated by authors |
| **Formal verification** | Not yet included | Not described |
| **Side-channel tooling** | Stubbed (`run_rtl_security.sh`) | Not described |

---

## 13. Summary of Key Differences

| Dimension | HLSSecBench | HardSecBench |
|---|---|---|
| Nature | Generative benchmark factory | Static curated benchmark |
| Hardware abstraction | HLS (pre-RTL) | RTL + firmware |
| HLS-specific threats | Yes (timing, pragmas, AXI) | No |
| Task count | Unlimited (seed-driven) | 924 |
| CWE breadth | Narrow (HLS subset) | Broad (76 CWEs) |
| Agent pipeline | 7 named agents with explicit roles | Synthesis/verification decoupled |
| Public/hidden spec split | Yes | No |
| Mutation testing | Yes (Mutator agent + quality gate) | No |
| Task types | Secure generation | Secure generation + detection |
| LLM comparison study | Not built-in | Core contribution |
| Prompting sensitivity | Not studied | Explicitly studied |
| Maturity | Research scaffold | Near-publication benchmark |

---

## 14. Complementarity

The two frameworks are **complementary rather than competing**:

- HardSecBench provides a broad, community-comparable baseline across RTL and firmware domains.
- HLSSecBench fills the gap at the HLS abstraction layer and provides the infrastructure to
  continuously generate new tasks as HLS toolchains and LLM capabilities evolve.

A natural integration would use HLSSecBench's generative pipeline to expand HardSecBench's coverage
into the HLS domain, then export retained tasks in HardSecBench's task format for community evaluation.
