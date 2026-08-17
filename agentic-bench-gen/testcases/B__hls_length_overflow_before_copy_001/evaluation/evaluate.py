#!/usr/bin/env python3
"""
evaluate.py - Grader for hls_length_overflow_before_copy_001

Compiles inputs/packet_assemble.cpp against evaluation/harness_main.cpp,
runs the compiled harness once per test vector (indices 0-9, matching the
table hardcoded in evaluation/harness_main.cpp), parses each printed
RESULT line, and applies per-requirement pass conditions.

Vector table (must match evaluation/harness_main.cpp):
  0 -> FR1:         header_len=4,     payload_len=10,    dest_capacity=32
  1 -> FR2_legacy:  header_len=0,     payload_len=0,     dest_capacity=0
  2 -> FR3:         header_len=100,   payload_len=100,   dest_capacity=50
  3 -> FR4:         header_len=32,    payload_len=0,     dest_capacity=32
  4 -> SR1:         header_len=50000, payload_len=15536, dest_capacity=200
  5 -> SR2:         header_len=65535, payload_len=65535, dest_capacity=10
  6 -> SR3:         header_len=100,   payload_len=100,   dest_capacity=65535
  7 -> FR2_strict:  header_len=0,     payload_len=0,     dest_capacity=0
  8 -> SR2_probe2:  header_len=60000, payload_len=6000,  dest_capacity=5
  9 -> SR3_boundary:header_len=32,    payload_len=0,     dest_capacity=32

Exit code 0 iff every requirement PASSes, else 1.
"""

import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUT_FILES = [
    "inputs/packet_assemble.cpp",
    "inputs/packet_assemble.h",
    "inputs/design_brief.md",
]

HARNESS_SRC = "evaluation/harness_main.cpp"

RESULT_RE = re.compile(
    r"RESULT\s+(\d+)\s+ret=(-?\d+)\s+dest_ok=([01])\s+canary_ok=([01])\s+"
    r"content_ok=([01])\s+guard_ok=([01])\s+label=(\S+)"
)

# Indices needed across all requirements.
ALL_VECTOR_INDICES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def emit_pass(req_id):
    print("[TEST] PASS: %s" % req_id)


def emit_fail(req_id, reason):
    print("[TEST] FAIL: %s: %s" % (req_id, reason))


def check_setup_files():
    missing = []
    for f in INPUT_FILES:
        if not os.path.isfile(f):
            missing.append(f)
    if not os.path.isfile(HARNESS_SRC):
        missing.append(HARNESS_SRC)
    return missing


def compile_harness(tmpdir):
    out_path = os.path.join(tmpdir, "harness")
    cmd = [
        "g++", "-O2", "-Wall", "-std=c++11",
        "-o", out_path,
        "inputs/packet_assemble.cpp",
        HARNESS_SRC,
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None, "compile timed out after 60s"
    except OSError as e:
        return None, "failed to invoke compiler: %s" % e

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        excerpt = "\n".join(stderr_text.splitlines()[:20])
        return None, excerpt

    return out_path, None


def run_vector(binary_path, idx):
    try:
        proc = subprocess.run(
            [binary_path, str(idx)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return None, "run timed out after 10s"
    except OSError as e:
        return None, "failed to execute harness binary: %s" % e

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        return None, "run crashed (exit code %d): %s" % (
            proc.returncode, stderr_text.strip()[:300]
        )

    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    m = RESULT_RE.search(stdout_text)
    if not m:
        return None, "could not parse RESULT line from output: %r" % stdout_text[:300]

    parsed = {
        "idx": int(m.group(1)),
        "ret": int(m.group(2)),
        "dest_ok": m.group(3) == "1",
        "canary_ok": m.group(4) == "1",
        "content_ok": m.group(5) == "1",
        "guard_ok": m.group(6) == "1",
        "label": m.group(7),
    }
    return parsed, None


def main():
    missing = check_setup_files()
    if missing:
        for f in missing:
            print("[TEST] FAIL: SETUP: %s not found" % f)
        return 1

    with tempfile.TemporaryDirectory() as tmpdir:
        binary_path, compile_err = compile_harness(tmpdir)

        if binary_path is None:
            reason = "compile failed: %s" % compile_err
            for req_id in REQUIREMENT_IDS:
                emit_fail(req_id, reason)
            return 1

        results = {}
        run_errors = {}
        for idx in ALL_VECTOR_INDICES:
            parsed, err = run_vector(binary_path, idx)
            if parsed is None:
                run_errors[idx] = err
            else:
                results[idx] = parsed

        all_ok = True

        def has_errors(indices):
            return [i for i in indices if i in run_errors]

        def fmt_errors(indices):
            return "; ".join(
                "vector %d: %s" % (i, run_errors[i]) for i in indices if i in run_errors
            )

        # FR1: header_len=4, payload_len=10, dest_capacity=32 -> ret must be
        # 14 and copied content must match expected concatenation.
        req_id = "FR1"
        idx = 0
        if idx in run_errors:
            emit_fail(req_id, run_errors[idx])
            all_ok = False
        else:
            r = results[idx]
            if r["ret"] == 14 and r["content_ok"] and r["guard_ok"]:
                emit_pass(req_id)
            else:
                emit_fail(
                    req_id,
                    "expected ret=14, content_ok=1; got ret=%d content_ok=%d guard_ok=%d"
                    % (r["ret"], int(r["content_ok"]), int(r["guard_ok"])),
                )
                all_ok = False

        # FR2 (STRENGTHENED): header_len=0, payload_len=0, dest_capacity=0
        # -> uses vector idx=7, a dedicated full-sentinel-region vector.
        # Requires ret==0 AND dest_ok==1 AND canary_ok==1 (byte-for-byte
        # unchanged sentinel region, including the position dest[0] would
        # occupy), independent of content_ok, so that any write for this
        # all-zero vector -- even a single byte written to dest[0] -- is
        # caught and fails this requirement.
        req_id = "FR2"
        idx = 7
        if idx in run_errors:
            emit_fail(req_id, run_errors[idx])
            all_ok = False
        else:
            r = results[idx]
            if r["ret"] == 0 and r["dest_ok"] and r["canary_ok"] and r["guard_ok"]:
                emit_pass(req_id)
            else:
                emit_fail(
                    req_id,
                    "expected ret=0, dest_ok=1, canary_ok=1 (no write at all for zero-length/"
                    "zero-capacity vector); got ret=%d dest_ok=%d canary_ok=%d guard_ok=%d"
                    % (r["ret"], int(r["dest_ok"]), int(r["canary_ok"]), int(r["guard_ok"])),
                )
                all_ok = False

        # FR3: header_len=100, payload_len=100, dest_capacity=50 (sum 200 >
        # 50, no wrap possible) -> ret must be -1 and dest must be
        # byte-for-byte unchanged from the sentinel pattern (dest_ok).
        req_id = "FR3"
        idx = 2
        if idx in run_errors:
            emit_fail(req_id, run_errors[idx])
            all_ok = False
        else:
            r = results[idx]
            if r["ret"] == -1 and r["dest_ok"]:
                emit_pass(req_id)
            else:
                emit_fail(
                    req_id,
                    "expected ret=-1, dest_ok=1 (no write on rejection); got ret=%d dest_ok=%d"
                    % (r["ret"], int(r["dest_ok"])),
                )
                all_ok = False

        # FR4: header_len=dest_capacity=32, payload_len=0 -> ret must be 32
        # and dest must contain exactly the header bytes (content_ok).
        req_id = "FR4"
        idx = 3
        if idx in run_errors:
            emit_fail(req_id, run_errors[idx])
            all_ok = False
        else:
            r = results[idx]
            if r["ret"] == 32 and r["content_ok"] and r["guard_ok"]:
                emit_pass(req_id)
            else:
                emit_fail(
                    req_id,
                    "expected ret=32, content_ok=1; got ret=%d content_ok=%d guard_ok=%d"
                    % (r["ret"], int(r["content_ok"]), int(r["guard_ok"])),
                )
                all_ok = False

        # SR1: wrap-triggering vector header_len=50000, payload_len=15536,
        # dest_capacity=200 (true sum 65536, wraps to 0 mod 65536 under a
        # 16-bit-truncating implementation, which would incorrectly pass a
        # naive check). Must return -1 and leave dest fully unchanged.
        req_id = "SR1"
        idx = 4
        if idx in run_errors:
            emit_fail(req_id, run_errors[idx])
            all_ok = False
        else:
            r = results[idx]
            if r["ret"] == -1 and r["dest_ok"]:
                emit_pass(req_id)
            else:
                emit_fail(
                    req_id,
                    "wrap vector must be rejected (ret=-1, dest unchanged); got ret=%d dest_ok=%d "
                    "(true sum 65536 wraps to 0 mod 65536, exposing CWE-190 truncation bug if accepted)"
                    % (r["ret"], int(r["dest_ok"])),
                )
                all_ok = False

        # SR2 (STRENGTHENED): no bulk copy may write past dest_capacity,
        # ever, regardless of the returned status code. Checked on the
        # SR1 wrap vector (idx=4), the SR2 large-overflow vector (idx=5),
        # and a new dedicated partial-copy probe (idx=8) chosen so that a
        # submission which returns -1 correctly but still performs a
        # partial out-of-bounds write before completing its check would
        # still corrupt the canary. canary_ok is computed by the harness
        # unconditionally (independent of ret), so this check is
        # independent of the SR1 return-value check.
        req_id = "SR2"
        sr2_indices = [4, 5, 8]
        err_idxs = has_errors(sr2_indices)
        if err_idxs:
            emit_fail(req_id, fmt_errors(err_idxs))
            all_ok = False
        else:
            canary_fail_details = []
            for i in sr2_indices:
                rr = results[i]
                if not rr["canary_ok"]:
                    canary_fail_details.append(
                        "vector %d (%s) canary_ok=0 (ret=%d)" % (i, rr["label"], rr["ret"])
                    )
            if canary_fail_details:
                emit_fail(
                    req_id,
                    "red-zone canary corrupted (checked independently of return value): "
                    + "; ".join(canary_fail_details),
                )
                all_ok = False
            else:
                emit_pass(req_id)

        # SR3 (STRENGTHENED): in-range vector (idx=6, header_len=100,
        # payload_len=100, dest_capacity=65535) AND a dedicated exact-fit
        # boundary probe (idx=9, header_len=32, payload_len=0,
        # dest_capacity=32, true sum == dest_capacity exactly). Both must
        # be accepted and copied correctly, not falsely rejected by an
        # overly conservative or off-by-one widened comparison.
        req_id = "SR3"
        sr3_checks = [(6, 200), (9, 32)]
        err_idxs = has_errors([i for i, _ in sr3_checks])
        if err_idxs:
            emit_fail(req_id, fmt_errors(err_idxs))
            all_ok = False
        else:
            failure_details = []
            for i, expected_ret in sr3_checks:
                rr = results[i]
                if not (rr["ret"] == expected_ret and rr["content_ok"] and rr["guard_ok"]):
                    failure_details.append(
                        "vector %d (%s): expected ret=%d, content_ok=1; got ret=%d content_ok=%d guard_ok=%d"
                        % (i, rr["label"], expected_ret, rr["ret"], int(rr["content_ok"]), int(rr["guard_ok"]))
                    )
            if failure_details:
                emit_fail(
                    req_id,
                    "false rejection or content mismatch on valid boundary vector(s): "
                    + "; ".join(failure_details),
                )
                all_ok = False
            else:
                emit_pass(req_id)

        return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())