#!/usr/bin/env python3
"""
evaluation/evaluate.py

Main grader for the hls_constant_time_cbc_unpad_001 task.

Grades inputs/cbc_unpad.cpp IN PLACE against the pinned interface:

    void pad_check(const unsigned char block[16], int *valid, int *unpadded_len);

Checks:
  FR1  valid padding of every length 1..16
  FR2  invalid last-byte values (0, 17, 255) + fully-padded N=16 boundary
  FR3  mismatched padding bytes for N=8 at region-offsets first/middle/last
  FR4  standalone g++ compile + block[] not mutated + static ban on
       STL containers / dynamic allocation / exceptions
  SR1  constant-time behavior (statistical wall-clock timing, majority
       vote over rounds, distance-from-end-of-block framing)
  SR2  full known-answer table bit-identical to reference oracle
  SR3  authoritative, SR1-independent behavioral probe using a
       deterministic cycle-counter-based metric over padding-region
       first/middle/last mismatch vectors, with its own separately
       tuned tolerance/aggregation; a secondary static regex scan is
       retained purely as corroborating, non-authoritative evidence

Exits 0 iff all requirements PASS, else non-zero.
"""

import os
import re
import sys
import statistics
import subprocess
import tempfile
import importlib.util

REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

RESULTS = {}


def report(req_id, ok, reason=""):
    if req_id in RESULTS:
        return
    if ok:
        print(f"[TEST] PASS: {req_id}")
        RESULTS[req_id] = True
    else:
        print(f"[TEST] FAIL: {req_id}: {reason}")
        RESULTS[req_id] = False


def fail_all_remaining(reason):
    for rid in REQ_IDS:
        if rid not in RESULTS:
            report(rid, False, reason)


def load_reference_module():
    """
    Load evaluation/private/reference.py as a module without relying on
    package __init__.py files being present.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    ref_path = os.path.join(here, "private", "reference.py")
    if not os.path.isfile(ref_path):
        print(f"[TEST] FAIL: SETUP: {ref_path} not found")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("reference", ref_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REF = load_reference_module()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(cmd, cwd=None, timeout=30):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout
        )
        return proc.returncode, proc.stdout.decode(errors="replace"), proc.stderr.decode(errors="replace")
    except subprocess.TimeoutExpired as e:
        return None, "", f"TIMEOUT after {timeout}s: {e}"
    except FileNotFoundError as e:
        return None, "", f"executable not found: {e}"


def parse_result_line(stdout):
    m = re.search(r"RESULT\s+valid=(-?\d+)\s+len=(-?\d+)\s+block_unchanged=(\d+)", stdout)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def parse_timing_lines(stdout, label):
    vals = []
    pattern = re.compile(
        r"TIMING\s+" + re.escape(label) + r"\s+round=(\d+)\s+ns_per_call=([0-9.]+)"
    )
    for line in stdout.splitlines():
        m = pattern.match(line.strip())
        if m:
            vals.append(float(m.group(2)))
    return vals


def parse_probe_lines(stdout, label):
    vals = []
    pattern = re.compile(
        r"PROBE\s+" + re.escape(label) + r"\s+round=(\d+)\s+cycles=([0-9.]+)"
    )
    for line in stdout.splitlines():
        m = pattern.match(line.strip())
        if m:
            vals.append(float(m.group(2)))
    return vals


def aggregate_labels_over_runs(binary_path, vectors, num_runs, parser, timeout=60):
    """
    Runs the given harness binary `num_runs` independent times against
    the given (label, block) vectors, collecting per-run medians per
    label using `parser` (either parse_timing_lines or
    parse_probe_lines depending on which harness/metric is in use), and
    returns (agg_median_per_label, failure_reason_or_None).

    agg_median_per_label maps label -> median-of-medians across the
    independent runs.
    """
    args = [binary_path] + [f"{label}:{REF.to_hex(block)}" for label, block in vectors]

    per_run_medians = {label: [] for label, _ in vectors}

    for run_idx in range(num_runs):
        rc, out, err = run_cmd(args, timeout=timeout)
        if rc != 0:
            return None, f"run crashed/timed out: {err.strip()[-400:]}"
        for label, _ in vectors:
            vals = parser(out, label)
            if not vals:
                return None, f"no samples parsed for label '{label}'"
            per_run_medians[label].append(statistics.median(vals))

    agg = {}
    for label, _ in vectors:
        agg[label] = statistics.median(per_run_medians[label])

    return agg, None


# ---------------------------------------------------------------------------
# FR4 static fail-on-presence scan
# ---------------------------------------------------------------------------

def _strip_comments_and_strings(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    # Strip string/char literals conservatively so a comment/string
    # containing the word "vector" etc. can't trigger a false positive.
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    text = re.sub(r"'(?:[^'\\]|\\.)*'", "''", text)
    return text


def static_scan_banned_constructs(cpp_path):
    """
    Fail-on-presence scan restricted to inputs/cbc_unpad.cpp only.
    FAILs (returns a non-empty reason) if the file contains:
      - STL container headers (<vector>, <map>, <set>, <string>,
        <deque>, <list>, <unordered_map>, <unordered_set>, <array>)
      - std:: container-type usage (std::vector, std::map, etc.)
      - dynamic allocation via `new` or `malloc(`
      - C++ exception constructs: throw / try / catch

    Public constraints explicitly forbid dynamic memory allocation,
    STL containers, and C++ exceptions in the submitted kernel, so
    absence of these constructs is required, not merely stylistic.
    Returns None if no banned construct is found (i.e. PASS for this
    sub-check).
    """
    try:
        with open(cpp_path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError as e:
        return f"could not read {cpp_path}: {e}"

    clean = _strip_comments_and_strings(src)

    banned_headers = [
        "vector", "map", "set", "string", "deque", "list",
        "unordered_map", "unordered_set", "array", "queue", "stack",
    ]
    for hdr in banned_headers:
        if re.search(r"#\s*include\s*<" + re.escape(hdr) + r">", clean):
            return f"banned STL header <{hdr}> included"

    if re.search(r"\bstd\s*::\s*(vector|map|set|string|deque|list|"
                 r"unordered_map|unordered_set|array|queue|stack)\b", clean):
        return "banned std:: container type used"

    # `new` as a dynamic-allocation keyword (word boundary, not part of
    # an identifier like `renew` or `newlen`).
    if re.search(r"\bnew\b", clean):
        return "dynamic allocation via 'new' found"

    if re.search(r"\bmalloc\s*\(", clean):
        return "dynamic allocation via 'malloc(' found"

    if re.search(r"\bthrow\b", clean):
        return "C++ exception construct 'throw' found"
    if re.search(r"\btry\b\s*\{", clean):
        return "C++ exception construct 'try' block found"
    if re.search(r"\bcatch\s*\(", clean):
        return "C++ exception construct 'catch(' found"

    return None


# ---------------------------------------------------------------------------
# SR3 secondary corroborating static scan (non-authoritative)
# ---------------------------------------------------------------------------

def _static_corroborating_scan(cpp_path):
    """
    Secondary, non-authoritative fail-on-presence style scan retained
    purely as corroborating evidence/logging alongside the authoritative
    behavioral SR3 probe (harness_probe.cpp). This function NEVER
    changes the SR3 verdict -- it only returns a human-readable note (or
    None) that evaluate.py may print for diagnostic purposes. The
    behavioral cycle-counter probe is the sole authoritative pass/fail
    mechanism for SR3.

    # Vulnerability in baseline:
    #   for (int i = 15; i >= start; --i) {
    #       if (block[i] != n) {
    #           *valid = 0;
    #           *unpadded_len = 16;
    #           return;
    #       }
    #   }
    """
    try:
        with open(cpp_path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        return None

    clean_src = _strip_comments_and_strings(src)

    loop_block_pattern = re.compile(
        r"(for|while)\s*\([^)]*\)\s*\{[^{}]*\bblock\s*\[[^\]]*\][^{}]*\}",
        re.DOTALL,
    )
    early_exit_pattern = re.compile(r"\b(return|break)\b\s*;")

    for loop_match in loop_block_pattern.finditer(clean_src):
        loop_body = loop_match.group(0)
        if early_exit_pattern.search(loop_body):
            if re.search(r"if\s*\([^)]*block\s*\[[^\]]*\][^)]*\)", loop_body):
                snippet = " ".join(loop_body.split())[:200]
                return f"found early return/break inside a block[]-indexing loop: '{snippet}'"

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    inputs_dir = "inputs"
    cpp_path = os.path.join(inputs_dir, "cbc_unpad.cpp")
    brief_path = os.path.join(inputs_dir, "design_brief.md")

    if not os.path.isfile(cpp_path):
        print(f"[TEST] FAIL: SETUP: {cpp_path} not found")
        sys.exit(1)
    if not os.path.isfile(brief_path):
        print(f"[TEST] FAIL: SETUP: {brief_path} not found")
        sys.exit(1)

    harness_main_src = os.path.join("evaluation", "harness_main.cpp")
    harness_timing_src = os.path.join("evaluation", "harness_timing.cpp")
    harness_probe_src = os.path.join("evaluation", "harness_probe.cpp")

    if not os.path.isfile(harness_main_src):
        print(f"[TEST] FAIL: SETUP: {harness_main_src} not found")
        sys.exit(1)
    if not os.path.isfile(harness_timing_src):
        print(f"[TEST] FAIL: SETUP: {harness_timing_src} not found")
        sys.exit(1)
    if not os.path.isfile(harness_probe_src):
        print(f"[TEST] FAIL: SETUP: {harness_probe_src} not found")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        main_bin = os.path.join(tmpdir, "harness_main")
        timing_bin = os.path.join(tmpdir, "harness_timing")
        probe_bin = os.path.join(tmpdir, "harness_probe")

        # ---------------------------------------------------------------
        # Compile main functional/security harness (covers FR1-FR4, SR2)
        # ---------------------------------------------------------------
        rc, out, err = run_cmd(
            ["g++", "-std=c++11", "-O0", "-o", main_bin, cpp_path, harness_main_src],
            timeout=60,
        )
        if rc != 0:
            reason = f"compile failed: {err.strip()[-800:] if err else 'unknown error'}"
            for rid in ("FR1", "FR2", "FR3", "FR4", "SR2"):
                report(rid, False, reason)
        else:
            # Build the full functional/security vector table from the
            # shared reference module (single source of truth).
            vectors = REF.make_vectors()

            fr1_ok, fr1_reason = True, ""
            fr2_ok, fr2_reason = True, ""
            fr3_ok, fr3_reason = True, ""
            fr4_run_ok, fr4_run_reason = True, ""
            sr2_ok, sr2_reason = True, ""

            for label, block in vectors:
                hexstr = REF.to_hex(block)
                rc2, out2, err2 = run_cmd([main_bin, hexstr], timeout=10)
                if rc2 != 0:
                    msg = f"run crashed/timed out on vector '{label}': {err2.strip()[-400:]}"
                    fr1_ok = fr1_ok and False
                    fr2_ok = fr2_ok and False
                    fr3_ok = fr3_ok and False
                    fr4_run_ok = fr4_run_ok and False
                    sr2_ok = sr2_ok and False
                    fr1_reason = fr1_reason or msg
                    fr2_reason = fr2_reason or msg
                    fr3_reason = fr3_reason or msg
                    fr4_run_reason = fr4_run_reason or msg
                    sr2_reason = sr2_reason or msg
                    continue

                parsed = parse_result_line(out2)
                if parsed is None:
                    msg = f"could not parse RESULT line for vector '{label}': stdout={out2!r}"
                    fr1_ok = fr1_ok and False
                    fr2_ok = fr2_ok and False
                    fr3_ok = fr3_ok and False
                    fr4_run_ok = fr4_run_ok and False
                    sr2_ok = sr2_ok and False
                    fr1_reason = fr1_reason or msg
                    fr2_reason = fr2_reason or msg
                    fr3_reason = fr3_reason or msg
                    fr4_run_reason = fr4_run_reason or msg
                    sr2_reason = sr2_reason or msg
                    continue

                got_valid, got_len, block_unchanged = parsed
                exp_valid, exp_len = REF.reference_pad_check(block)

                mismatch = (got_valid != exp_valid) or (got_len != exp_len)

                if label.startswith("valid_len"):
                    if mismatch:
                        fr1_ok = False
                        fr1_reason = (
                            f"vector '{label}': expected valid={exp_valid} len={exp_len}, "
                            f"got valid={got_valid} len={got_len}"
                        )
                    # FR2 also explicitly re-checks the N=16 fully-padded
                    # boundary vector to catch off-by-one bounds mutants
                    # (n<16 vs n<=16), which would incorrectly reject
                    # this vector.
                    if label == "valid_len16" and mismatch:
                        fr2_ok = False
                        fr2_reason = (
                            f"vector '{label}' (N=16 fully-padded boundary): "
                            f"expected valid={exp_valid} len={exp_len}, "
                            f"got valid={got_valid} len={got_len}"
                        )
                elif label.startswith("invalid_lastbyte_"):
                    # Covers last-byte 0, 17, and 255 -- the 17 vector
                    # specifically catches an off-by-one upper-bound
                    # mutant that treats 17 as an in-range padding
                    # length (e.g. `n <= 17` instead of `n <= 16`).
                    if mismatch:
                        fr2_ok = False
                        fr2_reason = (
                            f"vector '{label}': expected valid={exp_valid} len={exp_len}, "
                            f"got valid={got_valid} len={got_len}"
                        )
                elif label.startswith("mismatch_region_"):
                    if mismatch:
                        fr3_ok = False
                        fr3_reason = (
                            f"vector '{label}': expected valid={exp_valid} len={exp_len}, "
                            f"got valid={got_valid} len={got_len}"
                        )

                # SR2: every vector's outputs must match the reference exactly.
                if mismatch:
                    sr2_ok = False
                    sr2_reason = (
                        f"vector '{label}': expected valid={exp_valid} len={exp_len}, "
                        f"got valid={got_valid} len={got_len}"
                    )

                # FR4 (runtime half): block[] must not be mutated by the call.
                if block_unchanged != 1:
                    fr4_run_ok = False
                    fr4_run_reason = f"block[] contents were modified by pad_check on vector '{label}'"

            report("FR1", fr1_ok, fr1_reason)
            report("FR2", fr2_ok, fr2_reason)
            report("FR3", fr3_ok, fr3_reason)
            report("SR2", sr2_ok, sr2_reason)

            # FR4 (static half): banned-construct scan restricted to
            # inputs/cbc_unpad.cpp only.
            static_ban_reason = static_scan_banned_constructs(cpp_path)

            if not fr4_run_ok:
                report("FR4", False, fr4_run_reason)
            elif static_ban_reason:
                report("FR4", False, static_ban_reason)
            else:
                report("FR4", True)

        # ---------------------------------------------------------------
        # Compile timing harness (covers SR1)
        # ---------------------------------------------------------------
        rc, out, err = run_cmd(
            ["g++", "-std=c++11", "-O0", "-o", timing_bin, cpp_path, harness_timing_src],
            timeout=60,
        )
        timing_compile_failed = (rc != 0)
        if timing_compile_failed:
            reason = f"compile failed: {err.strip()[-800:] if err else 'unknown error'}"
            report("SR1", False, reason)
        else:
            mismatch_vectors = REF.make_mismatch_vectors()
            mismatch_by_label = {label: block for label, block in mismatch_vectors}

            valid_vectors = REF.make_valid_vectors()
            valid8_block = None
            for label, block in valid_vectors:
                if label == "valid_len8":
                    valid8_block = block
                    break

            SR1_TOLERANCE = 0.30
            SR1_NUM_RUNS = 5

            if valid8_block is None:
                report("SR1", False, "internal error: could not locate valid_len8 reference vector")
            else:
                timing_vectors_sr1 = [
                    ("valid8", valid8_block),
                    ("near_end_offset14", mismatch_by_label["mismatch_region_last_offset14"]),
                    ("middle_offset11", mismatch_by_label["mismatch_region_middle_offset11"]),
                    ("far_offset8", mismatch_by_label["mismatch_region_first_offset8"]),
                ]

                agg, err_reason = aggregate_labels_over_runs(
                    timing_bin, timing_vectors_sr1, SR1_NUM_RUNS, parse_timing_lines, timeout=60
                )
                if err_reason:
                    report("SR1", False, err_reason)
                else:
                    near_ns = agg["near_end_offset14"]
                    mid_ns = agg["middle_offset11"]
                    far_ns = agg["far_offset8"]

                    values_in_order = [near_ns, mid_ns, far_ns]
                    monotonic = all(
                        values_in_order[i] <= values_in_order[i + 1] * (1.0 + SR1_TOLERANCE)
                        for i in range(len(values_in_order) - 1)
                    ) and (far_ns > near_ns * (1.0 + SR1_TOLERANCE))

                    spread_ratio = (far_ns - near_ns) / near_ns if near_ns > 0 else 0.0

                    if monotonic and spread_ratio > SR1_TOLERANCE:
                        reason = (
                            f"timing scales with mismatch position (near={near_ns:.1f}ns, "
                            f"mid={mid_ns:.1f}ns, far={far_ns:.1f}ns, "
                            f"spread_ratio={spread_ratio:.2f} > tolerance={SR1_TOLERANCE}); "
                            f"this indicates a data-dependent early-exit padding scan"
                        )
                        report("SR1", False, reason)
                    else:
                        report("SR1", True)

        # ---------------------------------------------------------------
        # Compile probe harness (authoritative SR3 mechanism, independent
        # of SR1's wall-clock timing metric)
        # ---------------------------------------------------------------
        rc, out, err = run_cmd(
            ["g++", "-std=c++11", "-O0", "-o", probe_bin, cpp_path, harness_probe_src],
            timeout=60,
        )
        if rc != 0:
            reason = f"compile failed: {err.strip()[-800:] if err else 'unknown error'}"
            report("SR3", False, reason)
        else:
            mismatch_vectors = REF.make_mismatch_vectors()
            mismatch_by_label = {label: block for label, block in mismatch_vectors}

            # SR3's own vector set: identical region-position semantics
            # to FR3 (fixed N=8 padding region, single mismatch at the
            # first/middle/last byte of that region), reused here so the
            # authoritative probe targets exactly the vulnerability shape
            # the requirement describes.
            sr3_region_vectors = [
                ("region_first_offset8", mismatch_by_label.get("mismatch_region_first_offset8")),
                ("region_middle_offset11", mismatch_by_label.get("mismatch_region_middle_offset11")),
                ("region_last_offset14", mismatch_by_label.get("mismatch_region_last_offset14")),
            ]

            if any(v[1] is None for v in sr3_region_vectors):
                report("SR3", False, "internal error: could not locate all region-position reference vectors")
            else:
                # SR3 uses its OWN tolerance and its OWN aggregation
                # (median-of-medians over independent process
                # invocations of harness_probe, a different binary
                # measuring a different metric than harness_timing's
                # ns_per_call) so that a mutant tuned narrowly to slip
                # under SR1's specific numbers cannot automatically also
                # defeat SR3.
                SR3_TOLERANCE = 0.25
                SR3_NUM_RUNS = 5

                agg3, err_reason3 = aggregate_labels_over_runs(
                    probe_bin, sr3_region_vectors, SR3_NUM_RUNS, parse_probe_lines, timeout=60
                )
                if err_reason3:
                    report("SR3", False, err_reason3)
                else:
                    first_cy = agg3["region_first_offset8"]
                    middle_cy = agg3["region_middle_offset11"]
                    last_cy = agg3["region_last_offset14"]

                    # A naive end-to-start (index 15 -> 8) early-exit scan
                    # finds the mismatch at region-offset 14 (index 14,
                    # scanned 2nd) very quickly, the middle mismatch
                    # (offset 11) after scanning roughly half the region,
                    # and the mismatch at region-offset 8 (the very last
                    # byte examined) only after scanning the entire
                    # 8-byte region -- i.e. "last" (offset14) should be
                    # fastest/cheapest and "first" (offset8) slowest for
                    # a vulnerable implementation.
                    values_in_order = [last_cy, middle_cy, first_cy]
                    monotonic = all(
                        values_in_order[i] <= values_in_order[i + 1] * (1.0 + SR3_TOLERANCE)
                        for i in range(len(values_in_order) - 1)
                    ) and (first_cy > last_cy * (1.0 + SR3_TOLERANCE))

                    spread_ratio = (first_cy - last_cy) / last_cy if last_cy > 0 else 0.0

                    if monotonic and spread_ratio > SR3_TOLERANCE:
                        reason = (
                            f"cycle-counter proxy scales with padding-region mismatch position "
                            f"(last_offset14={last_cy:.1f}, middle_offset11={middle_cy:.1f}, "
                            f"first_offset8={first_cy:.1f}, spread_ratio={spread_ratio:.2f} > "
                            f"tolerance={SR3_TOLERANCE}); this indicates a secret-dependent early "
                            f"exit (break/return) inside the padding scan"
                        )
                        report("SR3", False, reason)
                    else:
                        # Secondary, non-authoritative corroborating
                        # static scan: only ever used to add a diagnostic
                        # note alongside a PASS, never to flip a
                        # behavioral PASS into a FAIL and never to be the
                        # sole basis of a PASS verdict by itself.
                        static_note = _static_corroborating_scan(cpp_path)
                        if static_note:
                            print(f"[INFO] SR3 static corroborating note: {static_note}")
                        report("SR3", True)

    fail_all_remaining("requirement was not evaluated due to an earlier setup failure")

    all_pass = all(RESULTS.get(rid, False) for rid in REQ_IDS)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()