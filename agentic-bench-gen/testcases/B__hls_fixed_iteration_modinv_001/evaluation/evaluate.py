#!/usr/bin/env python3
"""
evaluate.py - Grader for hls_fixed_iteration_modinv_001

Compiles inputs/modinv_kernel.cpp against evaluation/harness_main.cpp,
runs the resulting binary, and derives PASS/FAIL for FR1,FR2,FR3,FR4,
SR1,SR2,SR3 from observed behavior (plus two fail-on-presence static
scans used only to FAIL, never to PASS: SR2 and part of FR2).
"""

import os
import re
import statistics
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"

REQUIRED_INPUT_FILES = [
    "modinv_kernel.cpp",
    "modinv_kernel.h",
    "design_brief.md",
]

BEHAVIORAL_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR3"]
ALL_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

COMPILE_TIMEOUT = 30
RUN_TIMEOUT = 120

results = {}


def pass_(rid):
    results[rid] = (True, "")
    print("[TEST] PASS: %s" % rid)


def fail(rid, reason):
    results[rid] = (False, reason)
    print("[TEST] FAIL: %s: %s" % (rid, reason))


def setup_fail(path):
    print("[TEST] FAIL: SETUP: %s not found" % path)
    sys.exit(1)


def main():
    # --- Check required input files exist ---
    input_paths = {}
    for fname in REQUIRED_INPUT_FILES:
        p = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(p):
            setup_fail(p)
        input_paths[fname] = p

    harness_path = os.path.join(EVAL_DIR, "harness_main.cpp")
    if not os.path.isfile(harness_path):
        setup_fail(harness_path)

    cpp_path = input_paths["modinv_kernel.cpp"]
    with open(cpp_path, "r", encoding="utf-8", errors="replace") as f:
        cpp_source = f.read()

    # --- SR2: static fail-on-presence scan (independent of compile result) ---
    run_sr2_static_check(cpp_source)

    # --- FR2 secondary static fail-on-presence scan (malloc/new/STL/recursion) ---
    fr2_static_ok, fr2_static_reason = run_fr2_static_check(cpp_source)

    # --- Compile ---
    with tempfile.TemporaryDirectory() as tmpdir:
        binary_path = os.path.join(tmpdir, "harness")
        compile_cmd = [
            "g++", "-std=c++11", "-O0",
            "-I", INPUTS_DIR,
            "-o", binary_path,
            cpp_path,
            harness_path,
        ]
        try:
            proc = subprocess.run(
                compile_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=COMPILE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            for rid in BEHAVIORAL_IDS:
                fail(rid, "compile timed out")
            finish()
            return

        if proc.returncode != 0:
            stderr_text = proc.stderr.decode("utf-8", errors="replace")
            summary = summarize_stderr(stderr_text)
            for rid in BEHAVIORAL_IDS:
                fail(rid, "compile failed: %s" % summary)
            finish()
            return

        # Compile succeeded -> FR2 primary criterion satisfied, subject to
        # the static fail-on-presence scan.
        if fr2_static_ok:
            pass_("FR2")
        else:
            fail("FR2", fr2_static_reason)

        # --- Run ---
        try:
            run_proc = subprocess.run(
                [binary_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=RUN_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            for rid in ["FR1", "FR3", "FR4", "SR1", "SR3"]:
                fail(rid, "run crashed/timed out")
            finish()
            return

        if run_proc.returncode != 0:
            reason = "run crashed/timed out (exit code %d)" % run_proc.returncode
            for rid in ["FR1", "FR3", "FR4", "SR1", "SR3"]:
                fail(rid, reason)
            finish()
            return

        stdout_text = run_proc.stdout.decode("utf-8", errors="replace")

        func_map, func_order = run_fr1_check(stdout_text)
        run_fr3_check(stdout_text)
        run_fr4_check(stdout_text, func_map)
        run_sr1_check(stdout_text)
        run_sr3_check(stdout_text)

    finish()


def summarize_stderr(stderr_text):
    lines = [l for l in stderr_text.splitlines() if l.strip()]
    # Prefer lines that contain an actual diagnostic (error:/warning:) over
    # "In file included from" preambles, but keep it concise.
    diag_lines = [l for l in lines if ("error:" in l or "error " in l)]
    chosen = diag_lines[:5] if diag_lines else lines[:5]
    summary = " | ".join(chosen)
    if len(summary) > 800:
        summary = summary[:800] + "...(truncated)"
    if not summary:
        summary = "unknown compile error (no stderr output)"
    return summary


def run_fr3_check(stdout_text):
    m = re.search(r"^MOD_VALUE\s+(\d+)\s*$", stdout_text, re.MULTILINE)
    if not m:
        fail("FR3", "MOD_VALUE line not found in harness output")
        return
    value = int(m.group(1))
    if value == 251:
        pass_("FR3")
    else:
        fail("FR3", "MOD printed as %d, expected 251" % value)


def run_fr1_check(stdout_text):
    func_map = {}
    func_order = []
    for m in re.finditer(r"^FUNC a=(\d+) r=(\d+)\s*$", stdout_text, re.MULTILINE):
        a = int(m.group(1))
        r = int(m.group(2))
        func_map[a] = r
        func_order.append(a)

    if not func_map:
        fail("FR1", "no FUNC lines found in harness output")
        return func_map, func_order

    expected_operands = set(range(1, 251))
    seen_operands = set(func_map.keys())
    missing = expected_operands - seen_operands
    if missing:
        fail("FR1", "missing FUNC results for operands: %s" %
             sorted(missing)[:10])
        return func_map, func_order

    mismatches = []
    for a in range(1, 251):
        r = func_map[a]
        if r < 1 or r > 250:
            mismatches.append((a, r, "out of range [1,250]"))
            continue
        if (a * r) % 251 != 1:
            mismatches.append((a, r, "(a*r) mod 251 = %d, expected 1" % ((a * r) % 251)))

    if mismatches:
        a0, r0, reason0 = mismatches[0]
        fail("FR1", "operand a=%d returned r=%d: %s (total %d mismatches)" %
             (a0, r0, reason0, len(mismatches)))
    else:
        pass_("FR1")

    return func_map, func_order


def run_fr4_check(stdout_text, func_map):
    repeat_entries = []
    for m in re.finditer(r"^REPEAT a=(\d+) r=(\d+)\s*$", stdout_text, re.MULTILINE):
        a = int(m.group(1))
        r = int(m.group(2))
        repeat_entries.append((a, r))

    if not repeat_entries:
        fail("FR4", "no REPEAT lines found in harness output")
        return

    if not func_map:
        fail("FR4", "cannot verify REPEAT results: FUNC results unavailable")
        return

    mismatches = []
    for a, r in repeat_entries:
        expected = func_map.get(a)
        if expected is None:
            mismatches.append((a, r, "no FUNC baseline available for operand"))
            continue
        if r != expected:
            mismatches.append((a, r, "expected %d from FUNC baseline" % expected))

    if mismatches:
        a0, r0, reason0 = mismatches[0]
        fail("FR4", "operand a=%d returned r=%d on repeated/interleaved call: %s "
                    "(total %d mismatches out of %d repeated calls)" %
             (a0, r0, reason0, len(mismatches), len(repeat_entries)))
    else:
        pass_("FR4")


def run_sr1_check(stdout_text):
    counts = {}
    for m in re.finditer(r"^ITER a=(\d+) count=(\d+)\s*$", stdout_text, re.MULTILINE):
        a = int(m.group(1))
        c = int(m.group(2))
        counts[a] = c

    if not counts:
        fail("SR1", "no ITER lines found in harness output")
        return

    expected_operands = set(range(1, 251))
    seen_operands = set(counts.keys())
    missing = expected_operands - seen_operands
    if missing:
        fail("SR1", "missing ITER results for operands: %s" % sorted(missing)[:10])
        return

    values = list(counts.values())
    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        pass_("SR1")
    else:
        # Find an example operand pair with differing counts for the reason.
        example_low = None
        example_high = None
        for a, c in counts.items():
            if c == min_v and example_low is None:
                example_low = a
            if c == max_v and example_high is None:
                example_high = a
        fail("SR1", "iteration count varies with operand (min=%d at a=%s, max=%d at a=%s); "
                    "expected identical iteration count for every operand" %
             (min_v, example_low, max_v, example_high))


def run_sr3_check(stdout_text):
    # Collect per-operand list of trial elapsed times.
    per_operand_trials = {}
    for m in re.finditer(r"^TIMING_TRIAL a=(\d+) trial=(\d+) ns=(-?\d+)\s*$",
                          stdout_text, re.MULTILINE):
        a = int(m.group(1))
        ns = int(m.group(3))
        per_operand_trials.setdefault(a, []).append(ns)

    if not per_operand_trials:
        fail("SR3", "no TIMING_TRIAL lines found in harness output")
        return

    # Require a minimum number of trials per operand to make the median
    # and outlier-trimming meaningful.
    MIN_TRIALS = 5
    insufficient = [a for a, vals in per_operand_trials.items() if len(vals) < MIN_TRIALS]
    if insufficient:
        fail("SR3", "insufficient timing trials for operand(s) %s (need >= %d)" %
             (sorted(insufficient)[:5], MIN_TRIALS))
        return

    if any(v <= 0 for vals in per_operand_trials.values() for v in vals):
        fail("SR3", "non-positive timing measurement encountered")
        return

    # Trim the single fastest and slowest trial per operand (outlier
    # trimming), then take the median of what remains, to reduce
    # sensitivity to scheduler/cache/turbo noise inherent in -O0,
    # unpinned wall-clock measurement. SR1 (iteration-count invariance)
    # is the authoritative, deterministic signal for this security
    # property; SR3 is a secondary, best-effort corroboration via
    # wall-clock behavior, so its tolerance is calibrated generously
    # against the empirically observed noise floor of this measurement
    # environment rather than against an idealized noise-free timing
    # model.
    per_operand_median = {}
    for a, vals in per_operand_trials.items():
        sorted_vals = sorted(vals)
        if len(sorted_vals) > 2:
            trimmed = sorted_vals[1:-1]
        else:
            trimmed = sorted_vals
        per_operand_median[a] = statistics.median(trimmed)

    medians = list(per_operand_median.values())
    min_v = min(medians)
    max_v = max(medians)

    if min_v <= 0:
        fail("SR3", "non-positive median timing encountered")
        return

    spread = (max_v - min_v) / float(min_v)

    # SR1 already independently and deterministically verifies constant
    # iteration count; if SR1 has already passed, treat SR3 as a very
    # generously-tolerant corroborating check so environmental wall-clock
    # noise on an unpinned, -O0 build cannot false-reject an
    # already-proven-constant-time submission. If SR1 failed or was not
    # yet evaluated favorably, fall back to the same generous threshold
    # (SR3 is still evaluated independently and must still catch the
    # baseline's genuinely operand-dependent timing behavior).
    sr1_passed = results.get("SR1", (False, ""))[0]
    threshold = 1.50 if sr1_passed else 0.60

    if spread < threshold:
        pass_("SR3")
    else:
        slow_a = [a for a, v in per_operand_median.items() if v == max_v][0]
        fast_a = [a for a, v in per_operand_median.items() if v == min_v][0]
        fail("SR3", "trimmed-median timing spread %.3f exceeds tolerance %.2f "
                    "(fastest a=%d: %.0fns, slowest a=%d: %.0fns)" %
             (spread, threshold, fast_a, min_v, slow_a, max_v))


def run_sr2_static_check(cpp_source):
    """
    Fail-on-presence static scan: locate the loop block containing the
    g_iter_count increment (via brace matching around its innermost
    enclosing for/while), then search that substring for `break` or
    `return` keywords used as statements inside the loop body.

    Vulnerability anchor in baseline (inputs/modinv_kernel.cpp):
        while (u != 1 && v != 1) {
            g_iter_count++;
            ...
            if (u == 1) {
                long r = x1 % (long)MOD;
                if (r < 0) r += (long)MOD;
                return (unsigned int)r;
            }
            if (v == 1) {
                long r = x2 % (long)MOD;
                if (r < 0) r += (long)MOD;
                return (unsigned int)r;
            }
        }
    The `return (unsigned int)r;` statements lexically inside the while
    loop that increments g_iter_count are exactly the banned
    data-dependent early-exit construct.
    """
    occurrences = [m.start() for m in re.finditer(r"g_iter_count", cpp_source)]

    if not occurrences:
        fail("SR2", "could not locate g_iter_count usage in modinv_kernel.cpp "
                     "to identify the core inversion loop")
        return

    loop_block = None
    for occ in occurrences:
        block = extract_enclosing_loop_block(cpp_source, occ)
        if block is not None:
            loop_block = block
            break

    if loop_block is None:
        fail("SR2", "g_iter_count is not incremented inside any for/while loop; "
                     "cannot identify the core inversion loop body")
        return

    # Vulnerability pattern: break; or return ...; as a statement inside
    # the loop body (banned data-dependent early exit).
    banned_pattern = re.compile(r'(?<![A-Za-z0-9_])(break|return)\s*[;\(]')
    matches = banned_pattern.findall(loop_block)

    if matches:
        fail("SR2", "found banned early-exit construct(s) %s inside the core "
                     "inversion loop body (the loop that increments "
                     "g_iter_count); loop must run a fixed number of "
                     "iterations with no data-dependent break/return" %
             sorted(set(matches)))
    else:
        pass_("SR2")


def extract_enclosing_loop_block(source, pos):
    """
    Given a position `pos` in `source`, find the innermost enclosing
    for/while loop (by scanning backward for the loop keyword whose
    opening brace's matching closing brace still contains `pos`), and
    return the full text of that loop's body (between its braces).
    Returns None if no enclosing for/while loop is found.
    """
    candidates = []
    for m in re.finditer(r'\b(for|while)\b', source):
        kw_start = m.start()
        if kw_start >= pos:
            continue
        brace_open = find_next_top_level_brace(source, m.end())
        if brace_open is None:
            continue
        brace_close = find_matching_brace(source, brace_open)
        if brace_close is None:
            continue
        if brace_open < pos < brace_close:
            candidates.append((kw_start, brace_open, brace_close))

    if not candidates:
        return None

    # Choose the innermost (i.e. the one with the smallest enclosing span).
    candidates.sort(key=lambda t: (t[2] - t[1]))
    _, brace_open, brace_close = candidates[0]
    return source[brace_open:brace_close + 1]


def find_next_top_level_brace(source, start_idx):
    """
    Starting at start_idx (right after 'for'/'while'), skip the condition
    parentheses (balancing '(' ')'), then return the index of the '{'
    that opens the loop body. Returns None if not found.
    """
    i = start_idx
    n = len(source)
    while i < n and source[i] in " \t\r\n":
        i += 1
    if i >= n or source[i] != '(':
        return None
    depth = 0
    while i < n:
        if source[i] == '(':
            depth += 1
        elif source[i] == ')':
            depth -= 1
            if depth == 0:
                i += 1
                break
        i += 1
    while i < n and source[i] in " \t\r\n":
        i += 1
    if i < n and source[i] == '{':
        return i
    return None


def find_matching_brace(source, open_idx):
    depth = 0
    n = len(source)
    for i in range(open_idx, n):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    return None


def run_fr2_static_check(cpp_source):
    """
    Fail-on-presence static scan restricted to modinv_kernel.cpp text,
    used only to FAIL non-synthesizable submissions (never to grant PASS
    on its own -- compilation success is the primary FR2 criterion).

    Bans:
      - malloc(/calloc(/realloc(  (dynamic memory allocation)
      - `new` operator             (dynamic memory allocation)
      - std:: usage                (STL / standard library containers)
      - obvious self-recursion: the function `modinv` calling itself by
        name inside its own definition body.
    """
    reasons = []

    # Dynamic allocation.
    alloc_pattern = re.compile(r'\b(malloc|calloc|realloc)\s*\(')
    if alloc_pattern.search(cpp_source):
        reasons.append("dynamic memory allocation (malloc/calloc/realloc) found")

    new_pattern = re.compile(r'(?<![A-Za-z0-9_])new\s*(\[|\()|(?<![A-Za-z0-9_])new\s+[A-Za-z_]')
    if new_pattern.search(cpp_source):
        reasons.append("`new` operator usage found (dynamic memory allocation)")

    std_pattern = re.compile(r'\bstd::')
    if std_pattern.search(cpp_source):
        reasons.append("std:: (STL/standard library) usage found")

    # Self-recursion: look for the definition of modinv, then search its
    # body for a call to modinv(...) other than the definition header
    # itself.
    def_match = re.search(
        r'unsigned\s+int\s+modinv\s*\(\s*unsigned\s+int\s+\w+\s*\)\s*\{',
        cpp_source,
    )
    if def_match:
        body_open = def_match.end() - 1  # index of the '{'
        body_close = find_matching_brace(cpp_source, body_open)
        if body_close is not None:
            body_text = cpp_source[body_open:body_close + 1]
            if re.search(r'(?<![A-Za-z0-9_])modinv\s*\(', body_text):
                reasons.append("self-recursive call to modinv() found inside its own body")

    if reasons:
        return False, "; ".join(reasons)
    return True, ""


def finish():
    failed = [rid for rid in ALL_IDS if rid in results and not results[rid][0]]
    missing = [rid for rid in ALL_IDS if rid not in results]
    if missing:
        for rid in missing:
            fail(rid, "requirement was never evaluated (internal grader error)")
        failed = [rid for rid in ALL_IDS if rid in results and not results[rid][0]]

    if failed:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()