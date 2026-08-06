#!/usr/bin/env python3
"""
evaluation/evaluate.py

Main entry point for the hls_key_indexed_lookup_001 benchmark case.

Grades inputs/lookup_kernel.cpp IN PLACE (hardened_artifact submission
contract). Behaviorally compiles and runs the submission against a
harness (evaluation/harness_main.cpp) using the compile_and_run
evaluation contract:

  - a "plain" build (no TRACE_MODE) compiles evaluation/table_accessor.cpp
    (the only translation unit that #includes inputs/lookup_kernel.cpp in
    this build) together with evaluation/harness_main.cpp, and is used for
    FR1/SR4 (exhaustive output correctness) plus FR2's compile-cleanliness
    gate.
  - a "trace" build (-DTRACE_MODE) compiles evaluation/harness_main.cpp
    ALONE; that file #includes inputs/lookup_kernel.cpp itself, exactly
    once, after redefining TRACE_ACCESS, so every table access the kernel
    performs is recorded into a buffer we can inspect. This build is used
    for FR3/SR1/SR2/SR3.

FR1 and SR4 verdicts are derived exclusively from the harness binary's own
fr1-mode output, which compares lookup(value,key) against expected values
computed live from the SUBMISSION'S OWN COMPILED `table` contents (via
harness_get_table_entry(idx), linked from evaluation/table_accessor.cpp).
Nothing here hardcodes an independent reference table: the public
interface pins only the table's name (`table`), element type (`uint8_t`),
and size (16 entries) -- not its byte contents -- so any hardened
submission that keeps that pinned shape and faithfully implements
table[(value^key)&0x0F] against its own table passes, regardless of what
specific bytes its table holds. A mutant that breaks the substitution
formula itself (wrong index computation, ignoring key, returning a
constant, off-by-one masks, etc.) still fails, since the expected value is
always computed the same way -- table[(value^key)&0x0F] read live from the
same compiled table object the submission's own lookup() must have used.

FR2 and FR4 include a fail-on-presence static component (banned
synthesizable-subset constructs / secret-dependent branch constructs)
combined with the compile step itself; no requirement PASSes purely
because of matching source style.
"""

import os
import re
import subprocess
import sys
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle as oracle_mod  # noqa: E402  (imported for documentation cross-checking only)

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"
KERNEL_FILE = os.path.join(INPUTS_DIR, "lookup_kernel.cpp")
BRIEF_FILE = os.path.join(INPUTS_DIR, "design_brief.md")
HARNESS_SRC = os.path.join(EVAL_DIR, "harness_main.cpp")
ACCESSOR_SRC = os.path.join(EVAL_DIR, "table_accessor.cpp")

COMPILE_TIMEOUT = 60
RUN_TIMEOUT = 30

results = {}  # requirement_id -> True/False (for exit code computation)


def emit_pass(req_id):
    print("[TEST] PASS: %s" % req_id)
    results[req_id] = True


def emit_fail(req_id, reason):
    print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results[req_id] = False


ALL_REQS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


def setup_fail_all(reason):
    # Emit a single SETUP fail line, but every requirement must still get
    # a PASS/FAIL marker with its own id per the contract.
    print("[TEST] FAIL: SETUP: %s" % reason)
    for rid in ALL_REQS:
        results[rid] = False


def check_files_exist():
    missing = []
    if not os.path.isfile(KERNEL_FILE):
        missing.append(KERNEL_FILE)
    if not os.path.isfile(BRIEF_FILE):
        missing.append(BRIEF_FILE)
    if missing:
        setup_fail_all("required file(s) not found: %s" % ", ".join(missing))
        return False
    if not os.path.isfile(HARNESS_SRC):
        setup_fail_all("harness file not found: %s" % HARNESS_SRC)
        return False
    if not os.path.isfile(ACCESSOR_SRC):
        setup_fail_all("accessor file not found: %s" % ACCESSOR_SRC)
        return False
    return True


def run_subprocess(cmd, timeout, input_data=None):
    try:
        proc = subprocess.run(
            cmd,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    except FileNotFoundError as e:
        return None, "", "NOT_FOUND: %s" % e


def first_error_line(stderr_text):
    for line in stderr_text.splitlines():
        if "error" in line.lower():
            return line.strip()
    lines = [l for l in stderr_text.splitlines() if l.strip()]
    if lines:
        return lines[0].strip()
    return "unknown compile error"


def compile_plain(tmpdir, opt_flag):
    # Plain build: table_accessor.cpp (which alone #includes
    # inputs/lookup_kernel.cpp) + harness_main.cpp. inputs/lookup_kernel.cpp
    # is never passed directly to the compiler as a top-level translation
    # unit, avoiding any duplicate-definition hazard.
    out_bin = os.path.join(tmpdir, "harness_plain_%s" % opt_flag.lstrip("-"))
    cmd = ["g++", "-std=c++11", opt_flag, "-o", out_bin, ACCESSOR_SRC, HARNESS_SRC]
    rc, out, err = run_subprocess(cmd, COMPILE_TIMEOUT)
    return rc, out, err, out_bin


def compile_trace(tmpdir, opt_flag):
    # Trace build: harness_main.cpp ALONE. It #includes
    # inputs/lookup_kernel.cpp itself, exactly once, under TRACE_MODE.
    out_bin = os.path.join(tmpdir, "harness_trace_%s" % opt_flag.lstrip("-"))
    cmd = ["g++", "-std=c++11", "-DTRACE_MODE", opt_flag, "-o", out_bin, HARNESS_SRC]
    rc, out, err = run_subprocess(cmd, COMPILE_TIMEOUT)
    return rc, out, err, out_bin


def compile_plain_warnings(tmpdir, opt_flag):
    out_bin = os.path.join(tmpdir, "harness_warn_%s" % opt_flag.lstrip("-"))
    cmd = [
        "g++", "-std=c++11", "-Wall", "-Wextra", opt_flag,
        "-o", out_bin, ACCESSOR_SRC, HARNESS_SRC,
    ]
    rc, out, err = run_subprocess(cmd, COMPILE_TIMEOUT)
    return rc, out, err, out_bin


def parse_trace_lines(stdout_text, prefix="TRACE"):
    """Parse lines of the form 'TRACE <idx> <count> <csv-indices>' into a
    dict idx -> (count, [indices])."""
    out = {}
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line.startswith(prefix + " "):
            continue
        parts = line.split(" ", 3)
        if len(parts) < 3:
            continue
        try:
            idx = int(parts[1])
            count = int(parts[2])
        except ValueError:
            continue
        indices = []
        if len(parts) == 4 and parts[3].strip() != "":
            for tok in parts[3].strip().split(","):
                tok = tok.strip()
                if tok == "":
                    continue
                try:
                    indices.append(int(tok))
                except ValueError:
                    pass
        out[idx] = (count, indices)
    return out


def build_pairs_stdin(pairs):
    return ("\n".join("%d %d" % (v, k) for v, k in pairs) + "\n").encode("utf-8")


def main():
    import tempfile

    if not check_files_exist():
        sys.exit(1)

    with open(KERNEL_FILE, "r", encoding="utf-8", errors="replace") as f:
        kernel_source = f.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        # ---------------------------------------------------------------
        # Build 1: plain (no TRACE_MODE), used for FR1/SR4 exhaustive
        # output correctness (against the submission's own live table via
        # harness_get_table_entry), and FR2's compile-cleanliness gate.
        # ---------------------------------------------------------------
        plain_rc0, plain_out0, plain_err0, plain_bin0 = compile_plain(tmpdir, "-O0")
        plain_rc2, plain_out2, plain_err2, plain_bin2 = compile_plain(tmpdir, "-O2")

        plain_build_ok = (plain_rc0 == 0) and (plain_rc2 == 0)

        # ---------------------------------------------------------------
        # Build 2: TRACE_MODE, used for FR3/SR1/SR2/SR3.
        # ---------------------------------------------------------------
        trace_rc0, trace_out0, trace_err0, trace_bin0 = compile_trace(tmpdir, "-O0")

        trace_build_ok = (trace_rc0 == 0)

        # ---------------------------------------------------------------
        # FR2: clean compile at -O0 and -O2 (no hard errors), plus a
        # fail-on-presence scan for banned synthesizable-subset constructs
        # (malloc/new/STL containers/recursion markers). This scan targets
        # constructs that are absent from any correct hardened submission
        # and present only in disallowed styles; it never requires a
        # specific correct-style construct to be present.
        # ---------------------------------------------------------------
        fr2_reasons = []
        if plain_rc0 != 0:
            fr2_reasons.append("compile failed at -O0: %s" % first_error_line(plain_err0))
        if plain_rc2 != 0:
            fr2_reasons.append("compile failed at -O2: %s" % first_error_line(plain_err2))

        # Also attempt a -Wall -Wextra build to confirm the file compiles
        # under stricter diagnostics; only hard compiler *errors* (rc!=0)
        # count against FR2, matching "compile cleanly ... without
        # warnings-as-errors" (i.e. warnings alone must not fail FR2).
        warn_rc0, warn_out0, warn_err0, _ = compile_plain_warnings(tmpdir, "-O0")
        if warn_rc0 != 0:
            fr2_reasons.append(
                "compile with -Wall -Wextra failed at -O0: %s" % first_error_line(warn_err0)
            )

        # Vulnerability/banned-construct fail-on-presence scan.
        # Baseline itself contains none of these banned constructs (it is
        # simple and compiles cleanly), so this scan does not exercise
        # baseline-failure by itself for FR2; FR2's baseline failure is not
        # required (baseline is stated to PASS FR1/FR2). This scan exists
        # to catch mutants/submissions that violate the synthesizable
        # subset rule (heap allocation, STL, recursion).
        banned_patterns = [
            (r"\bmalloc\s*\(", "malloc() call (dynamic memory not allowed)"),
            (r"\bnew\s+(?:\[|[A-Za-z_])", "operator new (dynamic memory not allowed)"),
            (r"#include\s*<vector>", "STL <vector> header included"),
            (r"#include\s*<map>", "STL <map> header included"),
            (r"#include\s*<string>", "STL <string> header included"),
            (r"#include\s*<list>", "STL <list> header included"),
            (r"\bstd::vector\b", "std::vector usage (STL container not allowed)"),
            (r"\bstd::map\b", "std::map usage (STL container not allowed)"),
            (r"\btry\s*\{", "exception handling (try block) not allowed"),
            (r"\bthrow\b", "exception handling (throw) not allowed"),
        ]
        banned_found = None
        for pattern, desc in banned_patterns:
            if re.search(pattern, kernel_source):
                banned_found = desc
                break

        if banned_found is not None:
            fr2_reasons.append("banned construct found: %s" % banned_found)

        if fr2_reasons:
            emit_fail("FR2", "; ".join(fr2_reasons))
        else:
            emit_pass("FR2")

        # If the plain build failed to compile, every behaviorally-graded
        # requirement relying on it must be reported as compile-failed
        # (not SETUP), per the build/run failure protocol.
        plain_compile_reason = None
        if not plain_build_ok:
            if plain_rc0 != 0:
                plain_compile_reason = "compile failed: %s" % first_error_line(plain_err0)
            else:
                plain_compile_reason = "compile failed: %s" % first_error_line(plain_err2)

        trace_compile_reason = None
        if not trace_build_ok:
            trace_compile_reason = "compile failed: %s" % first_error_line(trace_err0)

        # ---------------------------------------------------------------
        # FR1 & SR4: exhaustive 65536-pair output correctness against
        # expected values computed live from the submission's OWN
        # compiled table via harness_get_table_entry((value^key)&0x0F),
        # inside the compiled harness binary itself
        # (evaluation/harness_main.cpp + evaluation/table_accessor.cpp).
        # This is deliberately NOT an independently hardcoded reference
        # array: the public interface pins only the table's name/type/
        # size, not its byte values. A submission that faithfully
        # implements table[(value^key)&0x0F] against its own table
        # therefore always PASSes here, regardless of table contents,
        # while a mutant that breaks the substitution formula itself
        # (wrong index, ignoring key, constant return, etc.) reliably
        # produces a detectable mismatch, since the expected value is
        # always recomputed the same way from the same live table.
        # ---------------------------------------------------------------
        if plain_compile_reason is not None:
            emit_fail("FR1", plain_compile_reason)
            emit_fail("SR4", plain_compile_reason)
        else:
            rc, out, err = run_subprocess([plain_bin0, "fr1"], RUN_TIMEOUT)
            if rc is None:
                reason = "run crashed/timed out: %s" % err
                emit_fail("FR1", reason)
                emit_fail("SR4", reason)
            elif rc != 0:
                reason = "run crashed/timed out (exit %s): %s" % (rc, err.strip()[:200])
                emit_fail("FR1", reason)
                emit_fail("SR4", reason)
            else:
                mismatches = None
                total = None
                sample_mismatch = None
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("FR1_MISMATCHES "):
                        try:
                            mismatches = int(line.split()[1])
                        except (IndexError, ValueError):
                            pass
                    elif line.startswith("FR1_TOTAL "):
                        try:
                            total = int(line.split()[1])
                        except (IndexError, ValueError):
                            pass
                    elif line.startswith("FR1_MISMATCH ") and sample_mismatch is None:
                        sample_mismatch = line

                if mismatches is None or total is None:
                    reason = "harness produced no FR1_MISMATCHES/FR1_TOTAL output"
                    emit_fail("FR1", reason)
                    emit_fail("SR4", reason)
                elif total != 65536:
                    reason = "harness did not report full 65536-pair sweep (got %d)" % total
                    emit_fail("FR1", reason)
                    emit_fail("SR4", reason)
                elif mismatches != 0:
                    reason = "found %d mismatches over %d pairs against submission's own table[(value^key)&0x0F] (e.g. %s)" % (
                        mismatches, total, sample_mismatch or "n/a"
                    )
                    emit_fail("FR1", reason)
                    emit_fail("SR4", reason)
                else:
                    emit_pass("FR1")
                    emit_pass("SR4")

        # ---------------------------------------------------------------
        # FR4: fail-on-presence static scan for a secret-dependent branch,
        # ternary, or switch inside the kernel body. This is combined with
        # (corroborated by) the behavioral SR1/SR2 trace-invariance checks
        # below, but the pass/fail verdict for FR4 itself is the static
        # scan since execution alone cannot prove absence of a branch that
        # happens not to change the observed trace on the sampled inputs.
        # ---------------------------------------------------------------
        # Extract just the lookup() function body to scope the scan and
        # avoid false positives from unrelated code (e.g. include guards).
        func_match = re.search(
            r"uint8_t\s+lookup\s*\([^)]*\)\s*\{", kernel_source
        )
        fr4_reason = None
        if func_match is None:
            fr4_reason = "could not locate lookup() function definition to scan"
        else:
            # Extract the function body via brace counting.
            start = func_match.end() - 1  # position of the opening '{'
            depth = 0
            end_idx = None
            for i in range(start, len(kernel_source)):
                c = kernel_source[i]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break
            if end_idx is None:
                fr4_reason = "could not locate closing brace of lookup() body"
            else:
                body = kernel_source[start:end_idx + 1]

                # Vulnerability construct family: an if/else/ternary/switch
                # whose controlling expression textually references
                # `value`, `key`, or an identifier that is itself directly
                # assigned from an expression combining value/key (e.g.
                # `idx = (value ^ key) & 0x0F;` followed by `if (idx == ...)`
                # or `switch (idx)`), which is exactly the shape a
                # secret-dependent-branch/index vulnerability takes.
                #
                # We deliberately do NOT flag: masked/ternary *data*
                # selects used purely as arithmetic (e.g.
                # `result |= table[i] & -(uint8_t)(i == idx);`) because
                # that is an unconditional expression, not a control-flow
                # branch -- it contains no `if`/`switch` keyword and no `?`
                # ternary operator altering control flow.

                # Collect names of locals assigned directly from an
                # expression referencing value or key (covers `idx`,
                # `sel`, etc. regardless of the name chosen).
                assign_re = re.compile(
                    r"\b(?:uint8_t|int|unsigned|auto)\s+(\w+)\s*=\s*[^;]*\b(?:value|key)\b[^;]*;"
                )
                secret_derived_names = set(assign_re.findall(body))
                secret_derived_names.update({"value", "key"})

                # Look for control-flow keywords whose condition
                # references value/key or a secret-derived local.
                control_kw_re = re.compile(
                    r"\b(if|switch)\s*\(([^)]*)\)"
                )
                ternary_re = re.compile(
                    r"([^;{}]*)\?[^;{}:]*:[^;{}]*;"
                )

                found_branch = None
                for m in control_kw_re.finditer(body):
                    cond = m.group(2)
                    for name in secret_derived_names:
                        if re.search(r"\b%s\b" % re.escape(name), cond):
                            found_branch = m.group(0)[:80]
                            break
                    if found_branch:
                        break

                if found_branch is None:
                    for m in ternary_re.finditer(body):
                        expr = m.group(0)
                        for name in secret_derived_names:
                            if re.search(r"\b%s\b" % re.escape(name), expr):
                                found_branch = expr.strip()[:80]
                                break
                        if found_branch:
                            break

                if found_branch is not None:
                    fr4_reason = "secret-dependent control-flow construct found: %s" % found_branch

        if fr4_reason is not None:
            emit_fail("FR4", fr4_reason)
        else:
            emit_pass("FR4")

        # ---------------------------------------------------------------
        # FR3 / SR1 / SR2 / SR3: all derived from the TRACE_MODE binary's
        # recorded access sequences across a deterministic set of probes:
        #   (a) value fixed, key swept over 0..255           -> SR1
        #   (b) key fixed, value swept over 0..255            -> SR2 (part)
        #   (c) 500 random joint (value,key) pairs (seeded)   -> SR2 (part), FR3, SR3
        # ---------------------------------------------------------------
        if trace_compile_reason is not None:
            for rid in ("FR3", "SR1", "SR2", "SR3"):
                emit_fail(rid, trace_compile_reason)
        else:
            rng = random.Random(1234567)

            fixed_value = 0x5A
            fixed_key = 0xA5

            pairs_sr1 = [(fixed_value, k) for k in range(256)]
            pairs_sr2 = [(v, fixed_key) for v in range(256)]
            pairs_rand = [(rng.randint(0, 255), rng.randint(0, 255)) for _ in range(500)]

            all_pairs = pairs_sr1 + pairs_sr2 + pairs_rand
            stdin_data = build_pairs_stdin(all_pairs)

            rc, out, err = run_subprocess([trace_bin0, "trace"], RUN_TIMEOUT, input_data=stdin_data)

            if rc is None:
                reason = "run crashed/timed out: %s" % err
                for rid in ("FR3", "SR1", "SR2", "SR3"):
                    emit_fail(rid, reason)
            elif rc != 0:
                reason = "run crashed/timed out (exit %s): %s" % (rc, err.strip()[:200])
                for rid in ("FR3", "SR1", "SR2", "SR3"):
                    emit_fail(rid, reason)
            else:
                trace_data = parse_trace_lines(out, prefix="TRACE")

                n_sr1 = len(pairs_sr1)
                n_sr2 = len(pairs_sr2)
                n_rand = len(pairs_rand)
                n_total = n_sr1 + n_sr2 + n_rand

                if len(trace_data) != n_total:
                    reason = (
                        "expected %d TRACE lines from harness, got %d"
                        % (n_total, len(trace_data))
                    )
                    for rid in ("FR3", "SR1", "SR2", "SR3"):
                        emit_fail(rid, reason)
                else:
                    canonical = oracle_mod.canonical_trace()

                    def get_entry(i):
                        return trace_data.get(i)

                    # ---- SR3 & FR3: every single call (across all
                    # samples) must record exactly 16 accesses. ----
                    sr3_bad = None
                    for i in range(n_total):
                        entry = get_entry(i)
                        if entry is None:
                            sr3_bad = "missing trace line %d" % i
                            break
                        count, _indices = entry
                        if count != 16:
                            v, k = all_pairs[i]
                            sr3_bad = (
                                "call #%d (value=%d,key=%d) recorded %d accesses, expected 16"
                                % (i, v, k, count)
                            )
                            break

                    if sr3_bad is not None:
                        emit_fail("FR3", sr3_bad)
                        emit_fail("SR3", sr3_bad)
                    else:
                        # ---- FR3 (shape): every call must also touch
                        # indices exactly {0..15} once each, in ascending
                        # order. ----
                        fr3_bad = None
                        for i in range(n_total):
                            _count, indices = get_entry(i)
                            if indices != canonical:
                                v, k = all_pairs[i]
                                fr3_bad = (
                                    "call #%d (value=%d,key=%d) trace=%s != canonical %s"
                                    % (i, v, k, indices, canonical)
                                )
                                break
                        if fr3_bad is not None:
                            emit_fail("FR3", fr3_bad)
                        else:
                            emit_pass("FR3")
                        emit_pass("SR3")

                    # ---- SR1: value fixed, key varies over 0..255 -> all
                    # traces byte-identical to each other (and, since we
                    # already validated FR3-shape above when it passed,
                    # to the canonical sequence too; but SR1 is judged on
                    # mutual invariance regardless of FR3's outcome). ----
                    sr1_traces = []
                    sr1_ok = True
                    sr1_reason = None
                    for i in range(n_sr1):
                        entry = get_entry(i)
                        if entry is None:
                            sr1_ok = False
                            sr1_reason = "missing trace line %d" % i
                            break
                        _count, indices = entry
                        sr1_traces.append(indices)
                    if sr1_ok:
                        first = sr1_traces[0]
                        for j, tr in enumerate(sr1_traces):
                            if tr != first:
                                sr1_ok = False
                                v, k = pairs_sr1[j]
                                sr1_reason = (
                                    "trace for key=%d differs from key=%d's trace "
                                    "(value fixed at %d): %s != %s"
                                    % (k, pairs_sr1[0][1], fixed_value, tr, first)
                                )
                                break
                    if sr1_ok:
                        emit_pass("SR1")
                    else:
                        emit_fail("SR1", sr1_reason)

                    # ---- SR2: key fixed, value varies over 0..255, plus
                    # the random joint pairs; every recorded trace must
                    # equal the single canonical sequence [0..15]. ----
                    sr2_ok = True
                    sr2_reason = None

                    for j in range(n_sr2):
                        i = n_sr1 + j
                        entry = get_entry(i)
                        if entry is None:
                            sr2_ok = False
                            sr2_reason = "missing trace line %d" % i
                            break
                        _count, indices = entry
                        if indices != canonical:
                            v, k = pairs_sr2[j]
                            sr2_reason = (
                                "trace for value=%d (key fixed at %d) = %s != canonical %s"
                                % (v, fixed_key, indices, canonical)
                            )
                            sr2_ok = False
                            break

                    if sr2_ok:
                        for j in range(n_rand):
                            i = n_sr1 + n_sr2 + j
                            entry = get_entry(i)
                            if entry is None:
                                sr2_ok = False
                                sr2_reason = "missing trace line %d" % i
                                break
                            _count, indices = entry
                            if indices != canonical:
                                v, k = pairs_rand[j]
                                sr2_reason = (
                                    "trace for random pair (value=%d,key=%d) = %s != canonical %s"
                                    % (v, k, indices, canonical)
                                )
                                sr2_ok = False
                                break

                    if sr2_ok:
                        emit_pass("SR2")
                    else:
                        emit_fail("SR2", sr2_reason)

    # -------------------------------------------------------------------
    # Final verdict: ensure every requirement in the map produced exactly
    # one PASS/FAIL, then exit accordingly.
    # -------------------------------------------------------------------
    missing_reqs = [r for r in ALL_REQS if r not in results]
    if missing_reqs:
        for r in missing_reqs:
            emit_fail(r, "requirement was never evaluated (internal harness error)")

    all_pass = all(results.get(r, False) for r in ALL_REQS)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()