#!/usr/bin/env python3
"""
evaluation/evaluate.py

Main grader for the reg_write_kernel.cpp hardening task.

Compiles the submission (inputs/reg_write_kernel.cpp) together with the
fixed C++ test harness (evaluation/harness_main.cpp), runs the resulting
binary, and parses its deterministic PROBE/OOB output lines to derive
PASS/FAIL for every functional (FR1-FR4) and security (SR1-SR4)
requirement.

FR4 note: FR4 is a build-gate precondition (the submission must compile
cleanly with g++ -std=c++11 -Wall against the harness) combined with an
ABI-invocation confirmation (the harness actually executed reg_write
through the pinned extern "C" signature for the full deterministic probe
sweep) AND a static fail-on-presence scan of the submitted source text
for banned dynamic-allocation/exception constructs (new/malloc/calloc/
realloc/throw/try), since the interface constraint explicitly forbids
dynamic memory allocation or exceptions inside reg_write and such a
construct is not guaranteed to be observable via stdout behavior alone.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

REG_FILE_SIZE = 64
PROTECTED_LO = 16
PROTECTED_HI = 47  # inclusive

INPUTS_DIR = "inputs"
KERNEL_FILE = os.path.join(INPUTS_DIR, "reg_write_kernel.cpp")
BRIEF_FILE = os.path.join(INPUTS_DIR, "design_brief.md")
HARNESS_FILE = os.path.join("evaluation", "harness_main.cpp")

results = {}


def record(req_id, passed, reason=""):
    if req_id in results:
        return
    results[req_id] = (passed, reason)
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))


def fail_all_remaining(reason):
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            record(rid, False, reason)


def parse_probe_line(line):
    # PROBE idx=<i> tag=<t> ret=<r> before=<b> after=<a>
    parts = line.split()
    d = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        d[k] = int(v)
    return d


def parse_oob_line(line):
    # OOB idx=<i> tag=<t> ret=<r> pre_canary=<0/1> post_canary=<0/1> reg_unchanged=<0/1>
    parts = line.split()
    d = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        d[k] = int(v)
    return d


# Banned-construct detection for FR4: the interface constraint states
# "Do not use dynamic memory allocation or exceptions inside the
# reg_write" implementation. These whole-word patterns are matched
# against the raw submission source text so that a mutant which
# reintroduces e.g. `new unsigned int[...]` is caught even though its
# observable stdout behavior is unchanged from a correct submission.
BANNED_CONSTRUCT_PATTERNS = [
    ("new", r"\bnew\b"),
    ("malloc", r"\bmalloc\b"),
    ("calloc", r"\bcalloc\b"),
    ("realloc", r"\brealloc\b"),
    ("throw", r"\bthrow\b"),
    ("try", r"\btry\b"),
]


def scan_for_banned_constructs(source_text):
    """Return a list of (construct_name, line_number, line_text) for any
    banned-construct occurrence found in source_text, or an empty list
    if none are present."""
    findings = []
    lines = source_text.splitlines()
    for line_no, line_text in enumerate(lines, start=1):
        for name, pattern in BANNED_CONSTRUCT_PATTERNS:
            if re.search(pattern, line_text):
                findings.append((name, line_no, line_text.strip()))
    return findings


def main():
    # --- SETUP checks: required input files must exist ---
    if not os.path.isfile(KERNEL_FILE):
        for rid in REQUIREMENT_IDS:
            record(rid, False, "SETUP: %s not found" % KERNEL_FILE)
        return 1

    if not os.path.isfile(BRIEF_FILE):
        for rid in REQUIREMENT_IDS:
            record(rid, False, "SETUP: %s not found" % BRIEF_FILE)
        return 1

    if not os.path.isfile(HARNESS_FILE):
        for rid in REQUIREMENT_IDS:
            record(rid, False, "SETUP: %s not found" % HARNESS_FILE)
        return 1

    # --- Compile ---
    with tempfile.TemporaryDirectory() as tmpdir:
        binary_path = os.path.join(tmpdir, "harness_bin")
        compile_cmd = [
            "g++", "-std=c++11", "-Wall", "-O0",
            "-o", binary_path,
            HARNESS_FILE,
        ]

        try:
            compile_proc = subprocess.run(
                compile_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            fail_all_remaining("compile failed: g++ invocation timed out after 30s")
            return 1
        except OSError as e:
            fail_all_remaining("compile failed: could not invoke g++: %s" % e)
            return 1

        if compile_proc.returncode != 0:
            stderr_text = compile_proc.stderr.decode("utf-8", errors="replace")
            excerpt = stderr_text.strip()
            if len(excerpt) > 2000:
                excerpt = excerpt[:2000] + "... [truncated]"
            fail_all_remaining("compile failed: %s" % excerpt)
            return 1

        # Compilation succeeded (build-gate precondition for FR4 satisfied
        # so far; final FR4 verdict still depends on confirming the binary
        # actually exercised reg_write through the pinned ABI, and on the
        # static banned-construct scan below).

        # --- Run ---
        try:
            run_proc = subprocess.run(
                [binary_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except subprocess.TimeoutExpired:
            for rid in REQUIREMENT_IDS:
                record(rid, False, "run crashed/timed out: harness execution exceeded 10s")
            return 1
        except OSError as e:
            for rid in REQUIREMENT_IDS:
                record(rid, False, "run crashed/timed out: could not execute harness: %s" % e)
            return 1

        if run_proc.returncode != 0:
            for rid in REQUIREMENT_IDS:
                record(
                    rid, False,
                    "run crashed/timed out: harness exited with code %d" % run_proc.returncode
                )
            return 1

        stdout_text = run_proc.stdout.decode("utf-8", errors="replace")

    # --- Parse output ---
    probes = {}  # (idx, tag) -> dict(ret, before, after)
    oob_probes = []  # list of dicts

    for line in stdout_text.splitlines():
        line = line.strip()
        if line.startswith("PROBE"):
            d = parse_probe_line(line)
            probes[(d["idx"], d["tag"])] = d
        elif line.startswith("OOB"):
            d = parse_oob_line(line)
            oob_probes.append(d)

    # -------------------------------------------------------------
    # FR4: build-gate precondition + ABI-invocation confirmation +
    # static fail-on-presence scan for banned dynamic-allocation /
    # exception constructs. Compilation already succeeded to reach
    # this point. Confirm the binary actually invoked reg_write
    # through the pinned extern "C" ABI by checking that the full
    # deterministic probe sweep was observed (128 PROBE lines: 64
    # indices x 2 tags) and at least 6 OOB lines were produced. Then
    # scan the raw submission source text for banned constructs; any
    # occurrence fails FR4 even if compile+ABI checks passed, since
    # the interface constraint explicitly forbids dynamic memory
    # allocation and exceptions inside reg_write.
    # -------------------------------------------------------------
    expected_probe_count = REG_FILE_SIZE * 2
    if len(probes) != expected_probe_count or len(oob_probes) < 6:
        record(
            "FR4", False,
            "build succeeded but ABI-invocation verification failed: "
            "expected %d PROBE lines and >=6 OOB lines, got %d PROBE lines "
            "and %d OOB lines" % (expected_probe_count, len(probes), len(oob_probes))
        )
    else:
        try:
            with open(KERNEL_FILE, "r", encoding="utf-8", errors="replace") as f:
                kernel_source_text = f.read()
        except OSError as e:
            record("FR4", False, "could not read %s for banned-construct scan: %s" % (KERNEL_FILE, e))
            kernel_source_text = None

        if kernel_source_text is not None:
            findings = scan_for_banned_constructs(kernel_source_text)
            if findings:
                excerpt = "; ".join(
                    "%s at line %d: %s" % (name, line_no, line_text)
                    for (name, line_no, line_text) in findings[:5]
                )
                record(
                    "FR4", False,
                    "banned dynamic-allocation/exception construct found in "
                    "submission source: %s" % excerpt
                )
            else:
                record("FR4", True)

    # Sanity: expect full sweep of 64 indices x 2 tags = 128 probes
    if len(probes) != REG_FILE_SIZE * 2:
        reason = (
            "harness output malformed: expected %d PROBE lines, got %d"
            % (REG_FILE_SIZE * 2, len(probes))
        )
        for rid in ["FR1", "FR2", "SR1", "SR2", "SR3"]:
            record(rid, False, reason)

    if len(oob_probes) < 6:
        reason = (
            "harness output malformed: expected at least 6 OOB lines, got %d"
            % len(oob_probes)
        )
        for rid in ["FR3", "SR4"]:
            record(rid, False, reason)

    # -------------------------------------------------------------
    # FR1: unprotected indices (0..15, 48..63), priv_tag=0 -> ret=1,
    # after == sentinel value that was written.
    # -------------------------------------------------------------
    if "FR1" not in results:
        unprotected = list(range(0, 16)) + list(range(48, REG_FILE_SIZE))
        failed = []
        for idx in unprotected:
            key = (idx, 0)
            if key not in probes:
                failed.append("idx=%d missing probe" % idx)
                continue
            d = probes[key]
            expected_value = 1000 + idx * 7 + 0 * 3
            if d["ret"] != 1:
                failed.append("idx=%d tag=0 ret=%d (expected 1)" % (idx, d["ret"]))
            elif d["after"] != expected_value:
                failed.append(
                    "idx=%d tag=0 after=%d expected=%d" % (idx, d["after"], expected_value)
                )
        if failed:
            record("FR1", False, "unprotected write failed for: " + "; ".join(failed[:5]))
        else:
            record("FR1", True)

    # -------------------------------------------------------------
    # FR2: protected indices (16..47 inclusive), checked per-index for
    # BOTH outcomes: priv_tag=1 -> ret=1 with correct write, AND
    # priv_tag=0 -> ret=0 (rejected). This loop is deliberately
    # independent of SR1/SR2's loops below (its own explicit
    # range(16,48) sweep -- which in Python covers 16..47 inclusive --
    # its own failure accumulator, no early break/continue) so that a
    # boundary-narrowing mutant (e.g. one that treats the
    # protected/gated window as only 16..39, silently accepting
    # unprivileged writes for 40..47, or that stops enforcing
    # privileged-success for those same indices) is caught here
    # directly rather than only via incidental overlap with SR1/SR2.
    # -------------------------------------------------------------
    if "FR2" not in results:
        fr2_failed = []
        fr2_protected_indices = list(range(16, 48))  # 16..47 inclusive
        for idx in fr2_protected_indices:
            # Sub-check A: priv_tag=1 must succeed and store the value.
            key_priv = (idx, 1)
            if key_priv not in probes:
                fr2_failed.append("FR2: idx=%d tag=1 missing probe" % idx)
            else:
                d_priv = probes[key_priv]
                expected_value = 1000 + idx * 7 + 1 * 3
                if d_priv["ret"] != 1:
                    fr2_failed.append(
                        "FR2: idx=%d tag=1 ret=%d (expected 1)" % (idx, d_priv["ret"])
                    )
                elif d_priv["after"] != expected_value:
                    fr2_failed.append(
                        "FR2: idx=%d tag=1 after=%d expected=%d"
                        % (idx, d_priv["after"], expected_value)
                    )

            # Sub-check B: priv_tag=0 must be rejected. This is what
            # catches a mutant that narrows the gated window (e.g.
            # only enforcing 16..39) regardless of tag=1 behavior.
            key_unpriv = (idx, 0)
            if key_unpriv not in probes:
                fr2_failed.append("FR2: idx=%d tag=0 missing probe" % idx)
            else:
                d_unpriv = probes[key_unpriv]
                if d_unpriv["ret"] != 0:
                    fr2_failed.append(
                        "FR2: idx=%d tag=0 ret=%d (expected 0, gated window narrowed)"
                        % (idx, d_unpriv["ret"])
                    )

        if fr2_failed:
            record("FR2", False, "; ".join(fr2_failed[:10]))
        else:
            record("FR2", True)

    # -------------------------------------------------------------
    # FR3: out-of-bounds indices -> ret=0, no memory mutation.
    # -------------------------------------------------------------
    if "FR3" not in results:
        failed = []
        for d in oob_probes:
            if d["ret"] != 0:
                failed.append("idx=%d tag=%d ret=%d (expected 0)" % (d["idx"], d["tag"], d["ret"]))
            elif d["reg_unchanged"] != 1:
                failed.append(
                    "idx=%d tag=%d caused memory mutation (reg_unchanged=0)" % (d["idx"], d["tag"])
                )
        if failed:
            record("FR3", False, "out-of-bounds handling failed: " + "; ".join(failed[:5]))
        else:
            record("FR3", True)

    # -------------------------------------------------------------
    # SR1: protected indices (16..47), priv_tag=0 -> ret=0 and
    # after == before (no write occurred), for ALL 32 indices with
    # zero exceptions. This is the core authorization-bypass check
    # that the insecure baseline (only gating 16..31) fails.
    # -------------------------------------------------------------
    if "SR1" not in results:
        failed = []
        for idx in range(PROTECTED_LO, PROTECTED_HI + 1):
            key = (idx, 0)
            if key not in probes:
                failed.append("idx=%d missing probe" % idx)
                continue
            d = probes[key]
            if d["ret"] != 0:
                failed.append(
                    "idx=%d tag=0 ret=%d (expected 0, unauthorized write accepted)" % (idx, d["ret"])
                )
            elif d["after"] != d["before"]:
                failed.append(
                    "idx=%d tag=0 mutated reg_file despite ret check (before=%d after=%d)"
                    % (idx, d["before"], d["after"])
                )
        if failed:
            record(
                "SR1", False,
                "authorization bypass detected for protected indices: " + "; ".join(failed[:8])
            )
        else:
            record("SR1", True)

    # -------------------------------------------------------------
    # SR2: privileged writes (tag=1) succeed uniformly across the
    # full protected range -- guards against overcorrection into
    # denial-of-service.
    # -------------------------------------------------------------
    if "SR2" not in results:
        failed = []
        for idx in range(PROTECTED_LO, PROTECTED_HI + 1):
            key = (idx, 1)
            if key not in probes:
                failed.append("idx=%d missing probe" % idx)
                continue
            d = probes[key]
            expected_value = 1000 + idx * 7 + 1 * 3
            if d["ret"] != 1:
                failed.append(
                    "idx=%d tag=1 ret=%d (expected 1, privileged write rejected)" % (idx, d["ret"])
                )
            elif d["after"] != expected_value:
                failed.append(
                    "idx=%d tag=1 after=%d expected=%d (privileged write did not persist)"
                    % (idx, d["after"], expected_value)
                )
        if failed:
            record(
                "SR2", False,
                "privileged writes not uniformly accepted: " + "; ".join(failed[:8])
            )
        else:
            record("SR2", True)

    # -------------------------------------------------------------
    # SR3: unprotected indices remain writable under both tag
    # values, preserving intended functional behavior.
    # -------------------------------------------------------------
    if "SR3" not in results:
        unprotected = list(range(0, 16)) + list(range(48, REG_FILE_SIZE))
        failed = []
        for idx in unprotected:
            for tag in (0, 1):
                key = (idx, tag)
                if key not in probes:
                    failed.append("idx=%d tag=%d missing probe" % (idx, tag))
                    continue
                d = probes[key]
                expected_value = 1000 + idx * 7 + tag * 3
                if d["ret"] != 1:
                    failed.append(
                        "idx=%d tag=%d ret=%d (expected 1)" % (idx, tag, d["ret"])
                    )
                elif d["after"] != expected_value:
                    failed.append(
                        "idx=%d tag=%d after=%d expected=%d"
                        % (idx, tag, d["after"], expected_value)
                    )
        if failed:
            record(
                "SR3", False,
                "unprotected register writability regression: " + "; ".join(failed[:8])
            )
        else:
            record("SR3", True)

    # -------------------------------------------------------------
    # SR4: out-of-bounds probes across both tag values must all be
    # rejected (ret=0) with canaries and reg_file fully unchanged,
    # for at least 3 distinct out-of-bounds indices.
    # -------------------------------------------------------------
    if "SR4" not in results:
        failed = []
        distinct_oob_indices = set()
        for d in oob_probes:
            distinct_oob_indices.add(d["idx"])
            if d["ret"] != 0:
                failed.append(
                    "idx=%d tag=%d ret=%d (out-of-bounds write incorrectly accepted)"
                    % (d["idx"], d["tag"], d["ret"])
                )
            elif d["pre_canary"] != 1 or d["post_canary"] != 1:
                failed.append(
                    "idx=%d tag=%d corrupted canary region (pre_canary=%d post_canary=%d)"
                    % (d["idx"], d["tag"], d["pre_canary"], d["post_canary"])
                )
            elif d["reg_unchanged"] != 1:
                failed.append(
                    "idx=%d tag=%d mutated reg_file on out-of-bounds access" % (d["idx"], d["tag"])
                )
        if len(distinct_oob_indices) < 3:
            failed.append(
                "only %d distinct out-of-bounds indices probed (need >= 3)"
                % len(distinct_oob_indices)
            )
        if failed:
            record("SR4", False, "out-of-bounds authorization bypass: " + "; ".join(failed[:8]))
        else:
            record("SR4", True)

    # Ensure every requirement got a verdict (defensive fallback).
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            record(rid, False, "requirement not evaluated due to unexpected grader state")

    all_passed = all(results[rid][0] for rid in REQUIREMENT_IDS)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())