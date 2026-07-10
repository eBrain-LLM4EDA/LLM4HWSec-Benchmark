# CWE Reference — Constant-Behavior XOR-Cipher HLS Kernel

This document lists the CWE categories relevant to `inputs/crypto_kernel.c`
and explains how each one manifests concretely in this task's baseline
vulnerability: a secret-dependent early-exit branch on `key[0] == 0` that
alters `status_out` and `iter_count_out`, and skips the correct ciphertext
computation on that path.

## CWE-208: Observable Discrepancy (Timing)

CWE-208 describes situations where a program's response time (or, more
generally, any externally observable timing-correlated behavior) differs
depending on secret data, allowing an attacker to infer information about
that secret purely by observing *how* the program behaves rather than what
it explicitly outputs. In hardware/HLS contexts, this generalizes beyond
wall-clock timing to loop trip counts and pipeline iteration counts, since
these directly determine cycle-accurate execution latency once synthesized.

**In this scenario:** the baseline kernel's `iter_count_out` value acts as
a direct, exposed proxy for the number of loop iterations executed. Because
the kernel exits after 0 iterations when `key[0] == 0` and after 16
iterations otherwise, `iter_count_out` is effectively a synthesizable
stand-in for execution latency that leaks whether `key[0] == 0` to any
observer who can read this diagnostic output or infer it from downstream
timing.

## CWE-203: Observable Discrepancy

CWE-203 is the general form of CWE-208: a product behaves differently, or
sends different responses, in a way that reveals security-relevant
information, even when the difference is not strictly about timing (e.g. a
different return value, error code, or status output). Any observable
difference in behavior that is correlated with a secret constitutes an
oracle an attacker can query repeatedly to narrow down the secret's value.

**In this scenario:** the baseline kernel sets `status_out = 1` on the
`key[0] == 0` branch and `status_out = chk` (the plaintext checksum) on the
normal path. For a fixed plaintext, these two possible `status_out` values
are mutually exclusive and directly reveal, with certainty, whether the
secret key's first byte is zero — a textbook observable discrepancy over a
non-timing output channel.

## CWE-385: Covert Timing Channel (generalized: Covert Behavioral Channel)

CWE-385 describes a covert timing channel: a mechanism by which two
processes, or a process and an external observer, can communicate or leak
information through variations in processing time that are not part of the
program's intended output contract. In HLS/synthesizable hardware, the
"timing channel" is frequently made concrete and machine-checkable as a
loop-iteration or resource-usage counter, since these values are what
ultimately determine cycle counts after synthesis.

**In this scenario:** `iter_count_out` is precisely such a channel. It was
introduced as an innocuous HLS resource/performance instrumentation value,
but because its value (`0` vs `16`) is gated by a branch on `key[0]`, it
becomes a covert channel through which one bit of the secret key is
smuggled out via a field that was never intended to carry secret-derived
information.

## CWE-200: Exposure of Sensitive Information to an Unauthorized Actor

CWE-200 is the umbrella category for any case where sensitive information
(here, the secret key) is made available, in whole or in part, to an actor
who is not authorized to have it — whether through direct leakage,
side-channel inference, or an incidental behavioral difference. Both of the
mechanisms above (CWE-208/CWE-385 via `iter_count_out`, CWE-203 via
`status_out`) are specific instances of this broader exposure: the kernel's
secret `key` parameter influences outputs that are documented and pinned as
*public* diagnostic channels.

**In this scenario:** any observer permitted to see only `ciphertext`,
`status_out`, and `iter_count_out` (per the interface contract) can, by
varying the public plaintext-holding input and observing repeated calls,
recover the fact `key[0] == 0` — a direct exposure of one bit of secret key
material through channels that were never declassified for that purpose.
Additionally, the baseline's incorrect/skipped ciphertext computation on
the `key[0] == 0` path (`ciphertext` zeroed rather than XORed) compounds
the exposure risk: functional discrepancies of this kind are exactly the
class of implementation bug that tends to accompany, and make detectable,
secret-dependent control flow.

## Hardening requirement

Hardening this kernel means **eliminating all key-dependent control flow
entirely** — not merely restructuring the existing branch so that both
sides "look" similar, execute similar-looking code, or produce superficially
close values. Any `if`, `switch`, ternary, or loop bound that reads any byte
of `key` in a way that could affect which instructions execute, how many
loop iterations run, or what gets written to `status_out` or
`iter_count_out` is a violation, regardless of how subtle.

Grading for this task is **purely behavioral**: `evaluate.py` compiles the
submitted `inputs/crypto_kernel.c` and executes it against a generated test
harness across a large sweep of keys (≥ 200, including the edge cases
enumerated in `inputs/security_spec.md`) with a fixed plaintext, and checks
that `status_out` and `iter_count_out` never vary and that `ciphertext`
always equals `plaintext XOR key`. Static grep-style pattern checks may be
used only as a fast auxiliary pre-check for banned constructs — they are
never the basis for a PASS. The CWE mappings above explain *why* this
invariance is required; the actual pass/fail determination is made
entirely by compiling and running the code.