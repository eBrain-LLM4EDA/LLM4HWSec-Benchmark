#!/usr/bin/env python3
"""
evaluation/evaluate.py

Grades inputs/kernel.c against the pinned xor_cipher_kernel interface.
Behavioral checks (FR1,FR2,FR3,SR1,SR2,SR4): compile+link inputs/kernel.c
with evaluation/harness_main.cpp, run the binary, parse its deterministic
stdout, and judge observed behavior.

FR4 is a build-hygiene check (gcc -Wall -Wextra with no implicit-decl /
pointer-type / type-mismatch warnings).

SR3 is a static fail-on-presence scan for banned/data-dependent
control-flow constructs in inputs/kernel.c.
"""

import os
import re
import subprocess
import sys
import tempfile

ALL_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]
BEHAVIORAL_IDS = ["FR1", "FR2", "FR3", "SR1", "SR2", "SR4"]

KERNEL_PATH = "inputs/kernel.c"
HARNESS_SRC = "evaluation/harness_main.cpp"

results = {}  # id -> (True/False, reason_or_None)


def emit_all(ok, reason):
    for rid in ALL_IDS:
        results[rid] = (ok, reason)


def emit(rid, ok, reason=None):
    results[rid] = (ok, reason)


def run_cmd(cmd, timeout):
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), \
            proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    except Exception as e:
        return None, "", "EXC: %s" % e


def first_line(text):
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return "(no output)"


# ---------------------------------------------------------------------
# Static source stripping / matching helpers for SR3
# ---------------------------------------------------------------------

def strip_comments_and_strings(text):
    """Remove // comments, /* */ comments, and string/char literals,
    replacing them with spaces to preserve rough layout (offsets not
    required to be exact)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            if j == -1:
                j = n
            out.append(' ' * (j - i))
            i = j
        elif c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            if j == -1:
                j = n
                out.append(' ' * (j - i))
                i = j
            else:
                j2 = j + 2
                seg = text[i:j2]
                out.append(' '.join(['']) )
                out.append(' ' * (j2 - i))
                i = j2
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == '\\' and j + 1 < n:
                    j += 2
                else:
                    j += 1
            j = min(j + 1, n)
            out.append(' ' * (j - i))
            i = j
        elif c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                if text[j] == '\\' and j + 1 < n:
                    j += 2
                else:
                    j += 1
            j = min(j + 1, n)
            out.append(' ' * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def find_matching(text, open_idx, open_ch, close_ch):
    """Given index of an opening char (text[open_idx] == open_ch), find
    the index of the matching closing char, handling nesting. Returns -1
    if not found."""
    depth = 0
    n = len(text)
    i = open_idx
    while i < n:
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def extract_paren_condition(text, if_kw_end_idx):
    """text[if_kw_end_idx:] should start (after whitespace) with '('.
    Returns (condition_text, index_after_closing_paren) or (None, None)."""
    i = if_kw_end_idx
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] != '(':
        return None, None
    close = find_matching(text, i, '(', ')')
    if close == -1:
        return None, None
    return text[i + 1:close], close + 1


def extract_block_or_stmt(text, after_idx):
    """After the closing paren of an if/while/for header (or switch
    header), extract either a brace-delimited block or a single statement
    up to the next ';'. Returns (block_text, index_after_block)."""
    i = after_idx
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i < n and text[i] == '{':
        close = find_matching(text, i, '{', '}')
        if close == -1:
            return text[i:], n
        return text[i:close + 1], close + 1
    # single statement up to ';'
    j = text.find(';', i)
    if j == -1:
        return text[i:], n
    return text[i:j + 1], j + 1


def scan_branch_condition_pattern(stripped, cond_regex):
    """Scan for if(...) / switch(...) headers whose condition matches
    cond_regex, then check whether the following block/case-bodies
    contain return/break/continue. Returns list of (index, snippet)
    hits."""
    hits = []
    exit_re = re.compile(r'\b(return|break|continue)\b')

    # if / else if headers
    for m in re.finditer(r'\bif\s*\(', stripped):
        cond_start = m.end() - 1  # index of '('
        cond, after = extract_paren_condition(stripped, m.end() - 1)
        if cond is None:
            continue
        if cond_regex.search(cond):
            block, _ = extract_block_or_stmt(stripped, after)
            if exit_re.search(block):
                snippet = stripped[m.start():m.start() + 80].replace('\n', ' ')
                hits.append((m.start(), "if-branch: " + snippet))

    # switch headers
    for m in re.finditer(r'\bswitch\s*\(', stripped):
        cond, after = extract_paren_condition(stripped, m.end() - 1)
        if cond is None:
            continue
        if cond_regex.search(cond):
            # find the switch body block
            i = after
            n = len(stripped)
            while i < n and stripped[i].isspace():
                i += 1
            if i < n and stripped[i] == '{':
                close = find_matching(stripped, i, '{', '}')
                if close == -1:
                    body = stripped[i:]
                else:
                    body = stripped[i:close + 1]
                # split body into case segments and check each for exit stmts
                # a `break` terminating a case is itself a banned exit here
                # because it is data-dependent control flow keyed on `key`
                if exit_re.search(body):
                    snippet = stripped[m.start():m.start() + 80].replace('\n', ' ')
                    hits.append((m.start(), "switch-branch: " + snippet))
    return hits


def sr3_static_scan(source_text):
    """Returns (passed: bool, reasons: list[str])."""
    stripped = strip_comments_and_strings(source_text)
    reasons = []

    # Sub-check (a): direct key-branch-then-exit
    # Vulnerability in baseline: "if (key[i] == 0) { *status = ERR_KEY_ZERO_BYTE; return; }"
    key_cond_re = re.compile(r'key\s*\[')
    hits_a = scan_branch_condition_pattern(stripped, key_cond_re)
    if hits_a:
        reasons.append(
            "sub-check(a) key-indexed branch with return/break/continue: %s"
            % hits_a[0][1]
        )

    # Sub-check (b): indirect via intermediate variable assigned from key[...]
    assign_re = re.compile(
        r'\b([A-Za-z_]\w*)\s*=\s*[^;{}]*key\s*\[[^\]]*\][^;]*;'
    )
    seen_names = set()
    hits_b = []
    for m in assign_re.finditer(stripped):
        name = m.group(1)
        if name in seen_names:
            continue
        seen_names.add(name)
        name_re = re.compile(r'\b' + re.escape(name) + r'\b')
        found = scan_branch_condition_pattern(stripped, name_re)
        hits_b.extend(found)
    if hits_b:
        reasons.append(
            "sub-check(b) branch on intermediate variable staged from key[...] "
            "with return/break/continue: %s" % hits_b[0][1]
        )

    # Sub-check (c): malloc/calloc
    # Vulnerability class: dynamic allocation banned for HLS synthesis
    malloc_re = re.compile(r'\b(malloc|calloc)\s*\(')
    m = malloc_re.search(stripped)
    if m:
        snippet = stripped[m.start():m.start() + 40].replace('\n', ' ')
        reasons.append("sub-check(c) malloc/calloc found: %s" % snippet)

    # Sub-check (d): recursion - actual call sites of xor_cipher_kernel(
    # followed by ';' rather than '{' (definition header)
    call_hits = 0
    for m in re.finditer(r'xor_cipher_kernel\s*\(', stripped):
        close = find_matching(stripped, m.end() - 1, '(', ')')
        if close == -1:
            continue
        j = close + 1
        n = len(stripped)
        while j < n and stripped[j].isspace():
            j += 1
        if j < n and stripped[j] == ';':
            call_hits += 1
    if call_hits >= 1:
        reasons.append(
            "sub-check(d) recursive call site(s) to xor_cipher_kernel found (%d)"
            % call_hits
        )

    # Sub-check (e): variable/content-bound loop condition
    # for (...; <cond containing key[]/plaintext[]/ciphertext[]>; ...)
    for m in re.finditer(r'for\s*\(', stripped):
        open_idx = m.end() - 1
        close = find_matching(stripped, open_idx, '(', ')')
        if close == -1:
            continue
        header = stripped[open_idx + 1:close]
        parts = header.split(';')
        if len(parts) >= 2:
            cond_clause = parts[1]
            if re.search(r'(key|plaintext|ciphertext)\s*\[', cond_clause):
                snippet = header.strip().replace('\n', ' ')[:80]
                reasons.append(
                    "sub-check(e) loop condition bound to buffer contents: %s"
                    % snippet
                )
                break

    passed = (len(reasons) == 0)
    return passed, reasons


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    # Step 1: verify inputs/kernel.c exists
    if not os.path.isfile(KERNEL_PATH):
        for rid in ALL_IDS:
            print("[TEST] FAIL: SETUP: %s not found" % KERNEL_PATH)
        return 1

    # Step 2: read kernel.c source once (for SR3, independent of build/run)
    try:
        with open(KERNEL_PATH, "r", encoding="utf-8", errors="replace") as f:
            kernel_src = f.read()
    except Exception as e:
        for rid in ALL_IDS:
            print("[TEST] FAIL: SETUP: could not read %s: %s" % (KERNEL_PATH, e))
        return 1

    if not os.path.isfile(HARNESS_SRC):
        print("[TEST] FAIL: SETUP: %s not found" % HARNESS_SRC)
        return 1

    tmpdir = tempfile.mkdtemp(prefix="xor_eval_")

    # -------------------------------------------------------------
    # FR4: build hygiene check
    # -------------------------------------------------------------
    fr4_obj = os.path.join(tmpdir, "kernel_fr4.o")
    rc, out, err = run_cmd(
        ["gcc", "-std=c11", "-Wall", "-Wextra", "-c", KERNEL_PATH, "-o", fr4_obj],
        timeout=30,
    )
    banned_patterns = [
        "implicit declaration",
        "incompatible pointer type",
        "conflicting types",
        "type mismatch",
    ]
    if rc != 0:
        emit("FR4", False, "compile failed: %s" % first_line(err))
    else:
        lowered = err.lower()
        matched = None
        for pat in banned_patterns:
            if pat in lowered:
                matched = pat
                break
        if matched is not None:
            emit("FR4", False, "warning matched banned pattern '%s': %s" %
                 (matched, first_line(err)))
        else:
            emit("FR4", True, None)

    # -------------------------------------------------------------
    # SR3: static fail-on-presence scan (independent of build success)
    # -------------------------------------------------------------
    sr3_ok, sr3_reasons = sr3_static_scan(kernel_src)
    if sr3_ok:
        emit("SR3", True, None)
    else:
        emit("SR3", False, "; ".join(sr3_reasons))

    # -------------------------------------------------------------
    # Build step B: compile+link kernel.c with harness_main.cpp
    # -------------------------------------------------------------
    kernel_obj = os.path.join(tmpdir, "kernel.o")
    harness_obj = os.path.join(tmpdir, "harness.o")
    harness_bin = os.path.join(tmpdir, "harness_bin")

    rc1, out1, err1 = run_cmd(
        ["gcc", "-std=c11", "-O0", "-c", KERNEL_PATH, "-o", kernel_obj],
        timeout=30,
    )
    build_failed = False
    build_fail_reason = None

    if rc1 != 0:
        build_failed = True
        build_fail_reason = "compile failed: %s" % first_line(err1)
    else:
        rc2, out2, err2 = run_cmd(
            ["g++", "-std=c++11", "-O0", "-c", HARNESS_SRC, "-o", harness_obj],
            timeout=30,
        )
        if rc2 != 0:
            build_failed = True
            build_fail_reason = "compile failed: %s" % first_line(err2)
        else:
            rc3, out3, err3 = run_cmd(
                ["g++", kernel_obj, harness_obj, "-o", harness_bin],
                timeout=30,
            )
            if rc3 != 0:
                build_failed = True
                build_fail_reason = "compile failed: %s" % first_line(err3)

    if build_failed:
        for rid in BEHAVIORAL_IDS:
            emit(rid, False, build_fail_reason)
    else:
        # -------------------------------------------------------------
        # Run the harness binary
        # -------------------------------------------------------------
        rc_run, out_run, err_run = run_cmd([harness_bin], timeout=10)
        if rc_run is None or rc_run != 0:
            reason = "run crashed/timed out"
            for rid in BEHAVIORAL_IDS:
                emit(rid, False, reason)
        else:
            plaintext = None
            kats = []
            trials = []

            for line in out_run.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if parts[0] == "PLAINTEXT" and len(parts) >= 2:
                    try:
                        plaintext = bytes.fromhex(parts[1])
                    except ValueError:
                        plaintext = None
                elif parts[0] == "KAT" and len(parts) >= 6:
                    try:
                        row = {
                            "len": int(parts[1]),
                            "key": bytes.fromhex(parts[2]),
                            "status": int(parts[3]),
                            "iterations": int(parts[4]),
                            "ct": bytes.fromhex(parts[5]),
                        }
                        kats.append(row)
                    except ValueError:
                        pass
                elif parts[0] == "TRIAL" and len(parts) >= 6:
                    try:
                        row = {
                            "idx": int(parts[1]),
                            "key": bytes.fromhex(parts[2]),
                            "status": int(parts[3]),
                            "iterations": int(parts[4]),
                            "ct": bytes.fromhex(parts[5]),
                        }
                        trials.append(row)
                    except ValueError:
                        pass

            if plaintext is None or len(kats) < 5 or len(trials) < 200:
                reason = "compile failed: harness produced malformed/insufficient output"
                for rid in BEHAVIORAL_IDS:
                    emit(rid, False, reason)
            else:
                # ---- FR1: ciphertext correctness across ALL rows ----
                fr1_ok = True
                fr1_reason = None
                for row in kats:
                    n = row["len"]
                    expected = bytes(p ^ k for p, k in zip(plaintext[:n], row["key"][:n]))
                    if row["ct"][:n] != expected:
                        off = next(i for i in range(n) if row["ct"][i] != expected[i])
                        fr1_ok = False
                        fr1_reason = "KAT len=%d mismatch at offset %d (got 0x%02x expected 0x%02x)" % (
                            n, off, row["ct"][off], expected[off]
                        )
                        break
                if fr1_ok:
                    for row in trials:
                        expected = bytes(p ^ k for p, k in zip(plaintext[:64], row["key"][:64]))
                        if row["ct"][:64] != expected:
                            off = next(i for i in range(64) if row["ct"][i] != expected[i])
                            fr1_ok = False
                            fr1_reason = "TRIAL idx=%d mismatch at offset %d (got 0x%02x expected 0x%02x)" % (
                                row["idx"], off, row["ct"][off], expected[off]
                            )
                            break
                emit("FR1", fr1_ok, fr1_reason)

                # ---- FR2: status == 0 for all rows ----
                fr2_ok = True
                fr2_reason = None
                for row in kats:
                    if row["status"] != 0:
                        fr2_ok = False
                        fr2_reason = "KAT len=%d status=%d (expected 0)" % (
                            row["len"], row["status"]
                        )
                        break
                if fr2_ok:
                    for row in trials:
                        if row["status"] != 0:
                            fr2_ok = False
                            fr2_reason = "TRIAL idx=%d status=%d (expected 0)" % (
                                row["idx"], row["status"]
                            )
                            break
                emit("FR2", fr2_ok, fr2_reason)

                # ---- FR3: full population / no truncation (KAT rows only) ----
                fr3_ok = True
                fr3_reason = None
                for row in kats:
                    n = row["len"]
                    if row["iterations"] != n:
                        fr3_ok = False
                        fr3_reason = "KAT len=%d iterations=%d (expected %d)" % (
                            n, row["iterations"], n
                        )
                        break
                    expected = bytes(p ^ k for p, k in zip(plaintext[:n], row["key"][:n]))
                    if row["ct"][:n] != expected:
                        fr3_ok = False
                        fr3_reason = "KAT len=%d ciphertext incomplete/incorrect" % n
                        break
                emit("FR3", fr3_ok, fr3_reason)

                # ---- SR1: status constant across TRIAL rows ----
                distinct_status = set(row["status"] for row in trials)
                if len(distinct_status) == 1:
                    emit("SR1", True, None)
                else:
                    deviating = sum(
                        1 for row in trials
                        if row["status"] != trials[0]["status"]
                    )
                    emit("SR1", False,
                         "distinct status values observed: %s (%d/%d trials deviate)" %
                         (sorted(distinct_status), deviating, len(trials)))

                # ---- SR2: iterations == 64 for every TRIAL row ----
                sr2_ok = True
                sr2_reason = None
                for row in trials:
                    if row["iterations"] != 64:
                        sr2_ok = False
                        sr2_reason = "TRIAL idx=%d iterations=%d (expected 64)" % (
                            row["idx"], row["iterations"]
                        )
                        break
                emit("SR2", sr2_ok, sr2_reason)

                # ---- SR4: ciphertext correctness under secret variation ----
                sr4_ok = True
                sr4_reason = None
                for row in trials:
                    expected = bytes(p ^ k for p, k in zip(plaintext[:64], row["key"][:64]))
                    if row["ct"][:64] != expected:
                        off = next(i for i in range(64) if row["ct"][i] != expected[i])
                        sr4_ok = False
                        sr4_reason = "TRIAL idx=%d mismatch at offset %d (got 0x%02x expected 0x%02x)" % (
                            row["idx"], off, row["ct"][off], expected[off]
                        )
                        break
                emit("SR4", sr4_ok, sr4_reason)

    # -------------------------------------------------------------
    # Print results in fixed order, compute exit code
    # -------------------------------------------------------------
    all_pass = True
    for rid in ALL_IDS:
        ok, reason = results.get(rid, (False, "requirement not evaluated"))
        if ok:
            print("[TEST] PASS: %s" % rid)
        else:
            all_pass = False
            print("[TEST] FAIL: %s: %s" % (rid, reason))

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())