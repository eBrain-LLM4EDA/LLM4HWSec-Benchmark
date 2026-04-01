# HLS Security-Aware Code Generation Benchmark (Arda)

A benchmark for evaluating LLM capabilities in generating and auditing High-Level Synthesis (HLS) C/C++ designs with hardware security properties.

## Overview

This benchmark targets three core security domains at the HLS abstraction level:

1. **Information Flow Tracking (IFT)** — Preventing secret data leakage across security boundaries
2. **Access Control Enforcement** — Hardware-level memory and peripheral access control
3. **Side-Channel Leakage Mitigation** — Constant-time execution, power/timing attack resistance

## Benchmark Structure

```
hls-security-benchmark/
├── README.md
├── examples/
│   ├── 01_aes_ift/                  # AES kernel with information flow tracking
│   ├── 02_memory_access_control/    # Memory interface access control
│   ├── 03_constant_time_compare/    # Constant-time comparison
│   ├── 04_key_schedule_isolation/   # Key schedule compartmentalization
│   ├── 05_dma_access_policy/        # DMA controller access policy
│   ├── 06_sha256_ift/               # SHA-256 with taint propagation
│   ├── 07_register_file_rbac/       # Register file role-based access
│   ├── 08_modexp_side_channel/      # Modular exponentiation side-channel fix
│   ├── 09_fifo_data_sanitization/   # FIFO buffer data sanitization
│   └── 10_bus_arbiter_isolation/    # Bus arbiter temporal isolation
└── evaluation/
    ├── evaluation_framework.md
    ├── scoring_rubric.json
    └── run_evaluation.py
```

## Example Format (per example)

Each example directory contains:

| File | Description |
|------|-------------|
| `prompt.md` | The natural-language task prompt given to the LLM |
| `insecure.cpp` | The vulnerable HLS C/C++ input code |
| `security_spec.md` | Security specification / CWE references |
| `reference_secure.cpp` | Gold-standard hardened output |
| `vulnerability_report.md` | Expected vulnerability report |
| `metadata.json` | CWE IDs, security domain, difficulty, synthesis target |

## CWE Coverage

| CWE | Description | Examples |
|-----|-------------|----------|
| CWE-200 | Exposure of Sensitive Information | 01, 06 |
| CWE-284 | Improper Access Control | 02, 05, 07 |
| CWE-208 | Observable Timing Discrepancy | 03, 08 |
| CWE-226 | Sensitive Information in Resource Not Removed Before Reuse | 09 |
| CWE-1189 | Improper Isolation of Shared Resources | 04, 10 |
| CWE-1191 | On-Chip Debug and Test Interface With Improper Access Control | 07 |
| CWE-1234 | Hardware Internal or Debug Modes Allow Override of Locks | 05 |
| CWE-1271 | Uninitialized Value on Reset | 09 |

## Evaluation Metrics

1. **CWE Violation Rate** — % of known CWE violations remaining in generated code
2. **Information Flow Correctness** — Taint labels correctly propagated and checked
3. **Synthesis Pass** — Code compiles and synthesizes with Vitis HLS / Vivado HLS
4. **Functional Equivalence** — Hardened code produces identical I/O behavior
5. **Security Completeness** — All specified security properties are enforced

## Quick Start

```bash
# Evaluate an LLM's output against the benchmark
python evaluation/run_evaluation.py --input llm_outputs/ --reference examples/
```

## License

Apache 2.0
