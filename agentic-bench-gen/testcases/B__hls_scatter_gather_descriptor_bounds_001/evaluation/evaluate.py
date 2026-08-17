#!/usr/bin/env python3
"""
evaluate.py -- Grader for hls_scatter_gather_descriptor_bounds_001

Compiles inputs/scatter_gather.cpp together with evaluation/harness_main.cpp,
runs the resulting binary once per probe (FR1-FR4, SR1-SR4), and derives
PASS/FAIL for each requirement purely from the printed RESULT line
(return status, dst content correctness/unmodified-ness, canary integrity).

No static source-text checks are used: every requirement here is decided
behaviorally by compiling and executing the submission.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"

SCATTER_GATHER_SRC = os.path.join(INPUTS_DIR, "scatter_gather.cpp")
DESIGN_BRIEF = os.path.join(INPUTS_DIR, "design_brief.md")
HARNESS_SRC = os.path.join(EVAL_DIR, "harness_main.cpp")

COMPILE_TIMEOUT_SEC = 60
RUN_TIMEOUT_SEC = 10

RESULT_LINE_RE = re.compile(
    r'^RESULT\s+(\S+)\s+status=(-?\d+)\s+dst_ok=([01])\s+canary_ok=([01])'
    r'(?:\s+subA_ok=([01])\s+subB_ok=([01]))?\s*$'
)


def emit_pass(req_id):
    print("[TEST] PASS: {}".format(req_id))


def emit_fail(req_id, reason):
    print("[TEST] FAIL: {}: {}".format(req_id, reason))


def check_setup_files():
    missing = []
    for path in (SCATTER_GATHER_SRC, DESIGN_BRIEF, HARNESS_SRC):
        if not os.path.isfile(path):
            missing.append(path)
    return missing


def compile_submission(tmpdir):
    binary_path = os.path.join(tmpdir, "harness")
    cmd = [
        "g++", "-std=c++17", "-Wall", "-Wextra", "-O0",
        "-o", binary_path,
        SCATTER_GATHER_SRC, HARNESS_SRC,
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMPILE_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return None, "compile timed out after {}s".format(COMPILE_TIMEOUT_SEC)
    except OSError as e:
        return None, "could not invoke g++: {}".format(e)

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        lines = [ln for ln in stderr_text.splitlines() if ln.strip()]
        summary = "\n".join(lines[:20]) if lines else "g++ exited with code {}".format(proc.returncode)
        return None, summary

    return binary_path, None


def run_probe(binary_path, probe_name):
    try:
        proc = subprocess.run(
            [binary_path, probe_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=RUN_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        return None, "run crashed/timed out"

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()
        reason = "run crashed/timed out (exit code {})".format(proc.returncode)
        if stderr_text:
            reason += ": " + stderr_text.splitlines()[0]
        return None, reason

    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    match = None
    for line in stdout_text.splitlines():
        line = line.strip()
        m = RESULT_LINE_RE.match(line)
        if m:
            match = m
            break

    if match is None:
        return None, "run crashed/timed out: no parseable RESULT line in output: {!r}".format(
            stdout_text.strip()[:200]
        )

    fields = {
        "name": match.group(1),
        "status": int(match.group(2)),
        "dst_ok": int(match.group(3)),
        "canary_ok": int(match.group(4)),
    }
    if match.group(5) is not None:
        fields["subA_ok"] = int(match.group(5))
    if match.group(6) is not None:
        fields["subB_ok"] = int(match.group(6))

    return fields, None


def verdict_functional_simple(req_id, fields):
    """FR1, FR2, FR4: require status == 0 and dst_ok == 1."""
    if fields["status"] != 0:
        return False, "expected status==0, got status={}".format(fields["status"])
    if fields["dst_ok"] != 1:
        return False, "expected dst_ok==1 (dst byte-exact/expected), got dst_ok=0"
    return True, ""


def verdict_fr3(fields):
    """FR3: compiled and linked successfully, and the process ran and
    printed a parseable RESULT line for the FR3 probe. That alone
    demonstrates C-linkage compatibility and runnability."""
    if fields.get("name") != "FR3":
        return False, "RESULT line name mismatch: expected FR3, got {}".format(fields.get("name"))
    return True, ""


def verdict_security(req_id, fields):
    """SR1-SR3: require status != 0, dst_ok == 1 (dst left unmodified),
    and canary_ok == 1 (no out-of-bounds corruption detected)."""
    if fields["status"] == 0:
        return False, "expected nonzero status (batch should be rejected), got status=0"
    if fields["dst_ok"] != 1:
        return False, "dst was modified despite invalid descriptor batch (dst_ok=0)"
    if fields["canary_ok"] != 1:
        return False, "canary/sentinel bytes were corrupted, indicating out-of-bounds access"
    return True, ""


def verdict_sr4(fields):
    """SR4: two sub-cases must both behave correctly.
    subA: offset+length == dst_len (exact fit) -> success, correct copy.
    subB: offset+length == dst_len + 1 (one byte over) -> rejection, dst unmodified.
    """
    subA = fields.get("subA_ok")
    subB = fields.get("subB_ok")
    if subA is None or subB is None:
        return False, "missing subA_ok/subB_ok fields in RESULT line for SR4"
    if subA != 1 and subB != 1:
        return False, "both boundary sub-cases failed (exact-fit accept and off-by-one reject)"
    if subA != 1:
        return False, "exact-fit boundary (offset+length==dst_len) was not accepted/copied correctly"
    if subB != 1:
        return False, "off-by-one boundary (offset+length==dst_len+1) was not rejected or left dst modified"
    return True, ""


def main():
    missing = check_setup_files()
    if missing:
        for path in missing:
            print("[TEST] FAIL: SETUP: {} not found".format(path))
        sys.exit(1)

    tmpdir = tempfile.mkdtemp(prefix="sg_eval_")
    try:
        binary_path, compile_error = compile_submission(tmpdir)

        if binary_path is None:
            summary = compile_error if compile_error else "unknown compilation error"
            for req_id in REQUIREMENT_IDS:
                emit_fail(req_id, "compile failed: {}".format(summary))
            sys.exit(1)

        all_pass = True
        results = {}

        for probe_name in REQUIREMENT_IDS:
            fields, run_error = run_probe(binary_path, probe_name)
            if fields is None:
                emit_fail(probe_name, run_error if run_error else "run crashed/timed out")
                all_pass = False
                continue
            results[probe_name] = fields

        for req_id in REQUIREMENT_IDS:
            if req_id not in results:
                continue

            fields = results[req_id]

            if req_id in ("FR1", "FR2", "FR4"):
                ok, reason = verdict_functional_simple(req_id, fields)
            elif req_id == "FR3":
                ok, reason = verdict_fr3(fields)
            elif req_id in ("SR1", "SR2", "SR3"):
                ok, reason = verdict_security(req_id, fields)
            elif req_id == "SR4":
                ok, reason = verdict_sr4(fields)
            else:
                ok, reason = False, "unknown requirement id"

            if ok:
                emit_pass(req_id)
            else:
                emit_fail(req_id, reason)
                all_pass = False

        sys.exit(0 if all_pass else 1)

    finally:
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()