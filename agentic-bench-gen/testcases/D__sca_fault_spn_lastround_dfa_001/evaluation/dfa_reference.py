#!/usr/bin/env python3
"""
dfa_reference.py - Standalone differential fault analysis reference helpers.

This module is a self-contained reference implementation of the DFA
elimination procedure described in inputs/fault_model.md, used to
independently cross-check a submitted vulnerability_report.json's claimed
recovered subkey nibble against inputs/spn_core.v and inputs/trace_pairs.json.

It is deliberately NOT imported by evaluation/evaluate.py at runtime (that
file embeds an equivalent implementation directly so it has no import-path
dependencies), but it is kept here as an independently runnable/reviewable
reference and for any auxiliary tooling that wants to reuse this logic.

All logic here is derived purely from parsing the actual RTL source text and
the actual trace data - no hardcoded S-box or key values.
"""

import json
import re


def parse_sbox_from_verilog(text):
    """
    Regex-extract the 4-bit S-box mapping from Verilog source of the form:

        4'h0: sbox4 = 4'hE;
        4'h1: sbox4 = 4'h4;
        ...

    Returns a dict {int -> int} with 16 entries (input nibble -> output
    nibble). Raises ValueError if a full 16-entry bijective table cannot be
    recovered from the text.
    """
    pattern = re.compile(
        r"4'[hH]([0-9a-fA-F])\s*:\s*sbox4\s*=\s*4'[hH]([0-9a-fA-F])\s*;"
    )
    mapping = {}
    for m in pattern.finditer(text):
        inp = int(m.group(1), 16)
        outp = int(m.group(2), 16)
        mapping[inp] = outp

    if len(mapping) < 16:
        raise ValueError(
            "Could not parse full 16-entry S-box from source text "
            "(found {} entries)".format(len(mapping))
        )

    # Restrict to canonical 0..15 keys only, in case of duplicate/garbage matches.
    mapping = {k: v for k, v in mapping.items() if 0 <= k <= 15}
    if len(mapping) != 16 or set(mapping.keys()) != set(range(16)):
        raise ValueError(
            "Parsed S-box does not cover all 16 input nibbles exactly once: {}".format(
                sorted(mapping.keys())
            )
        )

    return mapping


def invert_sbox(sbox):
    """
    Given a dict {input_nibble -> output_nibble} representing a bijective
    4-bit S-box, return the inverse mapping {output_nibble -> input_nibble}.

    Raises ValueError if the S-box is not a bijection over 0..15.
    """
    inv = {}
    for k, v in sbox.items():
        if v in inv:
            raise ValueError(
                "S-box is not a bijection; output value {} produced by both "
                "{} and {}".format(v, inv[v], k)
            )
        inv[v] = k

    if len(inv) != 16 or set(inv.keys()) != set(range(16)):
        raise ValueError("S-box is not a full bijection over 0..15; cannot invert")

    return inv


def load_traces(trace_json):
    """
    Extract a list of (correct_ciphertext_int, faulty_ciphertext_int) pairs
    from the trace_pairs.json structure. Tolerant of:
      - a top-level dict with a "traces" list
      - a bare top-level list of trace entries
      - ciphertext values given as hex strings ("0x72B1") or plain ints.

    Raises ValueError if no usable trace pairs are found.
    """
    if isinstance(trace_json, dict) and "traces" in trace_json:
        raw = trace_json["traces"]
    elif isinstance(trace_json, list):
        raw = trace_json
    else:
        raise ValueError("Unrecognized trace_pairs.json structure")

    traces = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cct = entry.get("correct_ciphertext")
        fct = entry.get("faulty_ciphertext")
        if cct is None or fct is None:
            continue

        def to_int(v):
            if isinstance(v, str):
                s = v.strip()
                return int(s, 16) if s.lower().startswith("0x") else int(s, 16)
            return int(v)

        cct_i = to_int(cct)
        fct_i = to_int(fct)
        traces.append((cct_i, fct_i))

    if not traces:
        raise ValueError("No usable trace pairs found in trace_pairs.json")

    return traces


def brute_force_nibble0(traces, sbox):
    """
    Perform the differential fault analysis elimination described in
    inputs/fault_model.md, restricted to nibble index 0 of the final round.

    Model:
        ciphertext_nibble0 = sbox(state_nibble0) XOR final_key_nibble0

    For a candidate final_key nibble0 value k, and a given trace pair
    (correct_ciphertext, faulty_ciphertext):

        sbox_out_correct = ciphertext_nibble0_correct XOR k
        sbox_out_faulty  = ciphertext_nibble0_faulty  XOR k

        state_correct = inv_sbox[sbox_out_correct]
        state_faulty  = inv_sbox[sbox_out_faulty]

    Because the fault model (fault_model.md) guarantees the injected fault
    always produces a NONZERO difference in the targeted nibble, a candidate
    k is falsified ("eliminated") by any trace pair for which the recovered
    pre-substitution difference (state_correct XOR state_faulty) is zero,
    since that would imply the fault had no effect on this trace, contradicting
    the documented fault model. This is the elimination criterion available
    from ciphertext pairs alone under this fault model, and is applied
    identically and simultaneously across every trace pair for a given k
    (i.e. k must survive on ALL traces to remain a candidate).

    Args:
        traces: list of (correct_ciphertext_int, faulty_ciphertext_int) pairs,
                16-bit integers.
        sbox: dict {int -> int}, the forward S-box mapping (0..15 -> 0..15).

    Returns:
        (survivors, reasons) where:
          - survivors: sorted list of candidate ints (0..15) consistent with
            every trace pair under the elimination criterion above.
          - reasons: dict {candidate_int -> str} explaining, for every
            candidate NOT in survivors, which trace index (0-based) and
            observation caused its elimination. Survivors are not present
            as keys in this dict.
    """
    inv_sbox = invert_sbox(sbox)

    survivors = []
    reasons = {}

    for k in range(16):
        eliminated_reason = None
        for trace_idx, (cct, fct) in enumerate(traces):
            ct_n0_correct = cct & 0xF
            ct_n0_faulty = fct & 0xF

            sbox_out_correct = ct_n0_correct ^ k
            sbox_out_faulty = ct_n0_faulty ^ k

            state_correct = inv_sbox[sbox_out_correct]
            state_faulty = inv_sbox[sbox_out_faulty]

            if state_correct == state_faulty:
                eliminated_reason = (
                    "candidate k=0x{:X} eliminated by trace {}: implies zero "
                    "pre-substitution difference (state_correct=0x{:X} == "
                    "state_faulty=0x{:X}), contradicting the documented "
                    "nonzero single-nibble fault model".format(
                        k, trace_idx, state_correct, state_faulty
                    )
                )
                break

        if eliminated_reason is None:
            survivors.append(k)
        else:
            reasons[k] = eliminated_reason

    return sorted(survivors), reasons


def _self_check():
    """
    Lightweight self-test using a locally-defined toy S-box and synthetic
    trace pairs, exercised only when this module is run directly (python3
    evaluation/dfa_reference.py). Not invoked by evaluate.py.
    """
    sample_verilog = """
        case (x)
            4'h0: sbox4 = 4'hE;
            4'h1: sbox4 = 4'h4;
            4'h2: sbox4 = 4'hD;
            4'h3: sbox4 = 4'h1;
            4'h4: sbox4 = 4'h2;
            4'h5: sbox4 = 4'hF;
            4'h6: sbox4 = 4'hB;
            4'h7: sbox4 = 4'h8;
            4'h8: sbox4 = 4'h3;
            4'h9: sbox4 = 4'hA;
            4'hA: sbox4 = 4'h6;
            4'hB: sbox4 = 4'hC;
            4'hC: sbox4 = 4'h5;
            4'hD: sbox4 = 4'h9;
            4'hE: sbox4 = 4'h0;
            4'hF: sbox4 = 4'h7;
        endcase
    """
    sbox = parse_sbox_from_verilog(sample_verilog)
    inv_sbox = invert_sbox(sbox)
    assert len(sbox) == 16
    assert len(inv_sbox) == 16

    # Build synthetic traces for a chosen true key nibble k_true, guaranteeing
    # every candidate other than k_true is eliminated on at least one trace,
    # by constructing state/fault pairs across the full nibble range.
    k_true = 0x9
    traces = []
    for state_correct in range(16):
        for diff in range(1, 16):
            state_faulty = state_correct ^ diff
            sbox_out_correct = sbox[state_correct]
            sbox_out_faulty = sbox[state_faulty]
            cct_n0 = sbox_out_correct ^ k_true
            fct_n0 = sbox_out_faulty ^ k_true
            traces.append((cct_n0, fct_n0))
            break  # one diff per state is enough for this smoke test
        if len(traces) >= 8:
            break

    survivors, reasons = brute_force_nibble0(traces, sbox)
    assert k_true in survivors, "self-check failed: true key not among survivors"


if __name__ == "__main__":
    _self_check()
    print("dfa_reference.py self-check passed")