#!/usr/bin/env python3
"""
evaluate.py -- grader for hls_aead_nonce_counter_exhaustion_001

Behaviorally compiles and links inputs/aead_wrapper.cpp against
evaluation/harness_main.cpp under g++, in two build variants:

  (a) default counter start (no macro override) -- used for FR1/FR2/FR3/FR4
  (b) -DAEAD_TEST_COUNTER_START=0xFFFFFFFDu     -- used for SR1/SR2/SR3

All PASS/FAIL verdicts (except the SR3 auxiliary fallback) are derived from
observed program behavior, never from source inspection.
"""

import os
import re
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"

REQUIRED_INPUT_FILES = [
    "aead_wrapper.cpp",
    "aead_wrapper.h",
    "design_brief.md",
]

HARNESS_MAIN = os.path.join(EVAL_DIR, "harness_main.cpp")

COMPILE_TIMEOUT = 60
RUN_TIMEOUT = 10

results = []  # list of (req_id, passed(bool), reason(str))


def emit(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
    results.append((req_id, passed, reason))


def fail_all(req_ids, reason):
    for r in req_ids:
        emit(r, False, reason)


def check_setup_files():
    missing = []
    for fname in REQUIRED_INPUT_FILES:
        path = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(path):
            missing.append(path)
    if not os.path.isfile(HARNESS_MAIN):
        missing.append(HARNESS_MAIN)
    return missing


def compile_variant(tmpdir, binary_name, extra_defines=None):
    """Compile inputs/aead_wrapper.cpp + harness_main.cpp into tmpdir/binary_name.
    Returns (success, stderr_text, binary_path)."""
    src_cpp = os.path.join(INPUTS_DIR, "aead_wrapper.cpp")
    out_path = os.path.join(tmpdir, binary_name)

    cmd = ["g++", "-std=c++11", "-O0", "-I", INPUTS_DIR, "-I", EVAL_DIR]
    if extra_defines:
        cmd.extend(extra_defines)
    cmd.extend(["-o", out_path, src_cpp, HARNESS_MAIN])

    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=COMPILE_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return False, "compile timed out", None
    except FileNotFoundError as e:
        return False, "g++ not found: %s" % e, None

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        return False, stderr_text, None

    if not os.path.isfile(out_path):
        return False, "compile reported success but binary not produced", None

    return True, "", out_path


def run_binary(binary_path, probe_arg):
    """Run binary with given probe argv[1]; return (success, stdout_text, reason)."""
    try:
        proc = subprocess.run(
            [binary_path, probe_arg],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=RUN_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return False, "", "run timed out"
    except Exception as e:
        return False, "", "run crashed: %s" % e

    if proc.returncode != 0:
        stderr_text = proc.stderr.decode("utf-8", errors="replace")
        return False, proc.stdout.decode("utf-8", errors="replace"), (
            "run crashed/timed out: rc=%d stderr=%s" % (proc.returncode, stderr_text[:300])
        )

    return True, proc.stdout.decode("utf-8", errors="replace"), ""


PROBE_LINE_RE = re.compile(
    r'^PROBE\s+(\S+)\s+IDX=(-?\d+)\s+RC=(-?\d+)\s+CT=(\S*)\s+TAG=(\S*)\s*$'
)
META_LINE_RE = re.compile(
    r'^PROBE\s+(\S+)\s+IDX=(-?\d+)\s+RC=(-?\d+)\s+(.*)$'
)


def parse_probe_lines(stdout_text, name):
    """Return list of dicts {idx, rc, ct, tag} for PROBE <name> lines (main data lines)."""
    out = []
    for line in stdout_text.splitlines():
        m = PROBE_LINE_RE.match(line)
        if m and m.group(1) == name:
            out.append({
                "idx": int(m.group(2)),
                "rc": int(m.group(3)),
                "ct": m.group(4),
                "tag": m.group(5),
            })
    return out


def parse_meta_lines(stdout_text, name):
    """Return list of dicts for PROBE <name>_meta lines with arbitrary KEY=VAL suffix."""
    out = []
    meta_name = name
    for line in stdout_text.splitlines():
        if not line.startswith("PROBE %s " % meta_name):
            continue
        m = META_LINE_RE.match(line)
        if not m or m.group(1) != meta_name:
            continue
        rest = m.group(4)
        kv = {}
        for token in rest.split():
            if "=" in token:
                k, v = token.split("=", 1)
                kv[k] = v
        out.append({
            "idx": int(m.group(2)),
            "rc": int(m.group(3)),
            "kv": kv,
        })
    return out


def main():
    missing = check_setup_files()
    if missing:
        for path in missing:
            print("[TEST] FAIL: SETUP: %s not found" % path)
        sys.exit(1)

    fr_sr_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

    with tempfile.TemporaryDirectory() as tmpdir:
        # ---- Build variant (a): default counter start ----
        ok_default, err_default, bin_default = compile_variant(
            tmpdir, "harness_default"
        )

        # ---- Build variant (b): wraparound-seeded counter start ----
        ok_wrap, err_wrap, bin_wrap = compile_variant(
            tmpdir, "harness_wrap",
            extra_defines=["-DAEAD_TEST_COUNTER_START=0xFFFFFFFDu"]
        )

        # FR3: both compiles must succeed with zero errors and produce binaries.
        if ok_default and ok_wrap:
            emit("FR3", True)
        else:
            reason_parts = []
            if not ok_default:
                reason_parts.append("default build failed: %s" % err_default[:800])
            if not ok_wrap:
                reason_parts.append("wraparound build failed: %s" % err_wrap[:800])
            emit("FR3", False, " | ".join(reason_parts))

        # If default build failed, everything relying on it fails with compile-failed reason.
        if not ok_default:
            fail_all(["FR1", "FR2", "FR4"], "compile failed: %s" % err_default[:800])
        if not ok_wrap:
            fail_all(["SR1", "SR2", "SR3"], "compile failed: %s" % err_wrap[:800])

        fr1_first_ct = None  # captured for cross-run nonce-reuse comparison in SR1

        # ---- FR1: 5 calls, same key/plaintext, default counter start ----
        if ok_default:
            success, stdout_text, reason = run_binary(bin_default, "fr1")
            if not success:
                emit("FR1", False, reason)
            else:
                probes = parse_probe_lines(stdout_text, "fr1")
                if len(probes) != 5:
                    emit("FR1", False, "expected 5 probe lines, got %d" % len(probes))
                else:
                    all_rc_zero = all(p["rc"] == 0 for p in probes)
                    pairs = [(p["ct"], p["tag"]) for p in probes]
                    all_distinct = len(set(pairs)) == len(pairs)
                    if not all_rc_zero:
                        emit("FR1", False, "one or more of 5 calls returned nonzero rc: %s"
                             % [p["rc"] for p in probes])
                    elif not all_distinct:
                        emit("FR1", False, "ciphertext/tag pairs were not pairwise distinct: %s" % pairs)
                    else:
                        emit("FR1", True)
                    fr1_first_ct = probes[0]["ct"] if probes else None

        # ---- FR2: single call, sentinel-fill byte-length check ----
        if ok_default:
            success, stdout_text, reason = run_binary(bin_default, "fr2")
            if not success:
                emit("FR2", False, reason)
            else:
                metas = parse_meta_lines(stdout_text, "fr2_meta")
                if not metas:
                    emit("FR2", False, "no fr2_meta probe line found in output")
                else:
                    m = metas[0]
                    rc = m["rc"]
                    ct_changed = int(m["kv"].get("CT_CHANGED", "-999"))
                    tag_changed = int(m["kv"].get("TAG_CHANGED", "-999"))
                    if rc != 0:
                        emit("FR2", False, "expected rc==0, got rc=%d" % rc)
                    elif ct_changed != 16:
                        emit("FR2", False,
                             "expected 16 ciphertext bytes changed from sentinel, got %d" % ct_changed)
                    elif tag_changed != 16:
                        emit("FR2", False,
                             "expected 16 tag bytes changed from sentinel, got %d" % tag_changed)
                    else:
                        emit("FR2", True)

        # ---- FR4: plaintext_len == 0 ----
        if ok_default:
            success, stdout_text, reason = run_binary(bin_default, "fr4")
            if not success:
                emit("FR4", False, reason)
            else:
                metas = parse_meta_lines(stdout_text, "fr4_meta")
                if not metas:
                    emit("FR4", False, "no fr4_meta probe line found in output")
                else:
                    m = metas[0]
                    rc = m["rc"]
                    ct_changed = int(m["kv"].get("CT_CHANGED", "-999"))
                    tag_changed = int(m["kv"].get("TAG_CHANGED", "-999"))
                    if rc != 0:
                        emit("FR4", False, "expected rc==0 for plaintext_len==0, got rc=%d" % rc)
                    elif ct_changed != 0:
                        emit("FR4", False,
                             "expected 0 ciphertext bytes changed for plaintext_len==0, got %d" % ct_changed)
                    elif tag_changed != 16:
                        emit("FR4", False,
                             "expected 16 tag bytes changed, got %d" % tag_changed)
                    else:
                        emit("FR4", True)

        # ---- SR1/SR2/SR3: wraparound-seeded build, run "wraparound" probe ----
        wrap_probes = None
        wrap_metas = None
        wrap_run_ok = False
        EXPECTED_CALLS = 8
        if ok_wrap:
            success, stdout_text, reason = run_binary(bin_wrap, "wraparound")
            if not success:
                fail_all(["SR1", "SR2", "SR3"], reason)
            else:
                wrap_probes = parse_probe_lines(stdout_text, "wraparound")
                wrap_metas = parse_meta_lines(stdout_text, "wraparound_meta")
                if len(wrap_probes) != EXPECTED_CALLS or len(wrap_metas) != EXPECTED_CALLS:
                    fail_all(["SR1", "SR2", "SR3"],
                             "expected %d wraparound probe/meta lines, got %d/%d"
                             % (EXPECTED_CALLS, len(wrap_probes), len(wrap_metas)))
                else:
                    wrap_run_ok = True

        if ok_wrap and wrap_run_ok:
            # Build combined per-call info: counter start = 0xFFFFFFFD
            # idx=0 -> counter value 0xFFFFFFFD (fresh, succeeds)
            # idx=1 -> counter value 0xFFFFFFFE (fresh, succeeds)
            # idx=2 -> counter value 0xFFFFFFFF (fresh, succeeds) -- last fresh value
            # idx=3 -> counter exhausted, must fail (this is the wraparound boundary call)
            # idx=4..7 -> must also fail (every call thereafter)
            rcs = [wrap_probes[i]["rc"] for i in range(EXPECTED_CALLS)]
            cts = [wrap_probes[i]["ct"] for i in range(EXPECTED_CALLS)]
            sentinel_flags = [int(wrap_metas[i]["kv"].get("SENTINEL_INTACT", "-1")) for i in range(EXPECTED_CALLS)]

            expected_boundary_idx = 3

            # ---- SR1: nonce/counter must never be reused after exhaustion ----
            # The call at idx=3 is where the baseline would wrap counter back to 0
            # and silently reuse the very first nonce ever used. A correct
            # implementation must return nonzero there instead of 0.
            boundary_idx = expected_boundary_idx
            if fr1_first_ct is None:
                emit("SR1", False, "could not capture FR1 first-call ciphertext for cross-run comparison")
            else:
                boundary_rc = rcs[boundary_idx]
                boundary_ct = cts[boundary_idx]
                if boundary_rc == 0:
                    emit("SR1", False,
                         "call at counter exhaustion boundary (idx=%d) returned 0 instead of "
                         "a nonzero error code; nonce counter is being reused/wrapped" % boundary_idx)
                elif boundary_ct == fr1_first_ct and boundary_ct != "":
                    emit("SR1", False,
                         "call at counter exhaustion boundary reproduced the same ciphertext as "
                         "the very first call of a fresh run (nonce reuse detected)")
                else:
                    emit("SR1", True)

            # ---- SR2: no bytes written to ciphertext_out/tag_out on error path ----
            if rcs[boundary_idx] != 0:
                if sentinel_flags[boundary_idx] == 1:
                    emit("SR2", True)
                else:
                    emit("SR2", False,
                         "on the exhausting call (rc=%d), ciphertext_out/tag_out sentinel bytes "
                         "were overwritten; bytes were emitted on the error path"
                         % rcs[boundary_idx])
            else:
                # boundary call unexpectedly succeeded; SR2 cannot be validated as intended.
                emit("SR2", False,
                     "boundary call (idx=%d) returned 0 (success) so the error-path "
                     "no-write guarantee could not be exercised" % boundary_idx)

            # ---- SR3: exhaustion must trigger exactly at the boundary, no off-by-one,
            # and must never recover after that (pinned first-failure-index check) ----
            first_fail_idx = None
            for i in range(EXPECTED_CALLS):
                if rcs[i] != 0:
                    first_fail_idx = i
                    break

            sr3_failure_reasons = []

            if first_fail_idx is None:
                sr3_failure_reasons.append(
                    "no call among the %d wraparound-build calls ever returned a nonzero "
                    "rc; counter exhaustion at the boundary was never enforced (rcs=%s)"
                    % (EXPECTED_CALLS, rcs)
                )
            else:
                if first_fail_idx != expected_boundary_idx:
                    sr3_failure_reasons.append(
                        "expected the first failing call to be exactly idx=%d (counter "
                        "value 0xFFFFFFFF exhausted after the call at idx=%d consumed it), "
                        "but the first nonzero-rc call was idx=%d; rcs=%s"
                        % (expected_boundary_idx, expected_boundary_idx - 1, first_fail_idx, rcs)
                    )

                # All calls strictly before first_fail_idx must have succeeded (rc==0).
                pre_boundary_ok = all(rcs[i] == 0 for i in range(first_fail_idx))
                if not pre_boundary_ok:
                    sr3_failure_reasons.append(
                        "one or more calls before the first failure (idx < %d) did not "
                        "return rc==0: rcs=%s" % (first_fail_idx, rcs)
                    )

                # All calls at/after first_fail_idx must fail (rc!=0), i.e. no recovery.
                post_boundary_all_fail = all(rcs[i] != 0 for i in range(first_fail_idx, EXPECTED_CALLS))
                if not post_boundary_all_fail:
                    recovered_idxs = [i for i in range(first_fail_idx, EXPECTED_CALLS) if rcs[i] == 0]
                    sr3_failure_reasons.append(
                        "one or more calls at/after the first failure (idx>=%d) returned "
                        "rc==0 again (transient/non-sticky exhaustion guard); recovered at "
                        "idx(es)=%s; rcs=%s" % (first_fail_idx, recovered_idxs, rcs)
                    )

                # Sentinel bytes must be untouched specifically AT the pinned boundary call.
                if first_fail_idx == expected_boundary_idx:
                    if sentinel_flags[first_fail_idx] != 1:
                        sr3_failure_reasons.append(
                            "at the pinned boundary call idx=%d (rc=%d), ciphertext_out/"
                            "tag_out sentinel bytes were overwritten; encryption side "
                            "effects occurred before/at the exhaustion check instead of "
                            "being fully skipped"
                            % (first_fail_idx, rcs[first_fail_idx])
                        )

            if not sr3_failure_reasons:
                emit("SR3", True)
            else:
                reason = " | ".join(sr3_failure_reasons)
                # Auxiliary, FAIL-only static signal: never used to PASS, only to add
                # context when the behavioral check above has already failed.
                src_path = os.path.join(INPUTS_DIR, "aead_wrapper.cpp")
                try:
                    with open(src_path, "r", encoding="utf-8", errors="replace") as f:
                        src_text = f.read()
                    # Vulnerability in baseline: "counter++;" with no preceding
                    # bounds/exhaustion check guarding it.
                    bare_increment_pattern = re.compile(
                        r'\bcounter\s*\+\+\s*;'
                    )
                    if bare_increment_pattern.search(src_text):
                        reason += (" | static check also found an unguarded bare "
                                   "'counter++' increment pattern consistent with "
                                   "CWE-190 silent wraparound")
                except Exception as e:
                    reason += " | static fallback scan failed: %s" % e
                emit("SR3", False, reason)

    all_ids_seen = set(r[0] for r in results)
    for req_id in fr_sr_ids:
        if req_id not in all_ids_seen:
            emit(req_id, False, "requirement was never evaluated (internal grader error)")

    failed = [r for r in results if not r[1]]
    if failed:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()