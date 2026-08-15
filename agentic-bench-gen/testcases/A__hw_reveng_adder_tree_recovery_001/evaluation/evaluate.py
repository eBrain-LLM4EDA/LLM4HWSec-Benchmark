#!/usr/bin/env python3
"""
evaluate.py - Main grading entry point for hw_reveng_adder_tree_recovery_001

Compiles submission/recovered_rtl.v against a generated testbench and the
reference flattened netlist (inputs/flattened_netlist.v) using iverilog,
simulates with vvp, and derives PASS/FAIL for FR1-FR4 from observed I/O
behavior. Also runs static fail-on-presence structural gates SR1/SR2.

FR1 is graded against an independently-computed Python ground truth
(va+vb+vc+vd mod 2^32) rather than against inputs/flattened_netlist.v's own
simulated output, because the reference netlist has a known stage-2
carry-truncation defect on overflowing vectors (see design brief / SR1
requirement_map notes). FR2's pinned constants are likewise hardcoded and
checked directly, independent of any netlist simulation.

Python stdlib only.
"""

import os
import re
import sys
import random
import subprocess
import tempfile

ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
SUBMISSION_DIR = os.path.join(REPO_ROOT, "submission")
EVALUATION_DIR = os.path.join(REPO_ROOT, "evaluation")

FLATTENED_NETLIST = os.path.join(INPUTS_DIR, "flattened_netlist.v")
PRIMITIVE_CELLS = os.path.join(INPUTS_DIR, "primitive_cells.v")
SUBMISSION_FILE = os.path.join(SUBMISSION_DIR, "recovered_rtl.v")
TB_FILE = os.path.join(EVALUATION_DIR, "tb_top.v")

VECTOR_COUNT = 2004
RANDOM_SEED = 20240607

results = {}


def emit(req_id, ok, reason=""):
    if req_id in results:
        # already recorded, do not double emit
        return
    if ok:
        print("[TEST] PASS: %s" % req_id)
        results[req_id] = True
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))
        results[req_id] = False


def fail_all_setup(missing_path, req_ids=None):
    ids = req_ids if req_ids is not None else ALL_REQ_IDS
    for rid in ids:
        emit(rid, False, "SETUP: %s not found" % missing_path)


def fail_all_reason(reason, req_ids):
    for rid in req_ids:
        emit(rid, False, reason)


def main():
    # ------------------------------------------------------------------
    # Step 1: verify input artifacts exist
    # ------------------------------------------------------------------
    if not os.path.isfile(FLATTENED_NETLIST):
        fail_all_setup("inputs/flattened_netlist.v")
        return 1
    if not os.path.isfile(PRIMITIVE_CELLS):
        fail_all_setup("inputs/primitive_cells.v")
        return 1

    # ------------------------------------------------------------------
    # Step 2: verify submission exists
    # ------------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_FILE):
        fail_all_setup("submission/recovered_rtl.v")
        return 1

    if not os.path.isfile(TB_FILE):
        fail_all_setup("evaluation/tb_top.v")
        return 1

    with open(SUBMISSION_FILE, "r", encoding="utf-8", errors="replace") as f:
        submission_text = f.read()
    with open(FLATTENED_NETLIST, "r", encoding="utf-8", errors="replace") as f:
        reference_netlist_text = f.read()

    # ------------------------------------------------------------------
    # Step 3: static SR1/SR2 checks (unconditional)
    # ------------------------------------------------------------------
    private_dir = os.path.join(EVALUATION_DIR, "private")
    if private_dir not in sys.path:
        sys.path.insert(0, private_dir)
    try:
        import security_checks  # noqa: E402
    except Exception as exc:
        # Infrastructure problem: our own harness file missing/broken
        fail_all_setup("evaluation/private/security_checks.py (%s)" % exc,
                        req_ids=["SR1", "SR2"])
        security_checks = None

    if security_checks is not None:
        try:
            sr1_ok, sr1_reason = security_checks.check_sr1(
                submission_text, reference_netlist_text
            )
            emit("SR1", sr1_ok, sr1_reason)
        except Exception as exc:
            emit("SR1", False, "SR1 check crashed: %s" % exc)

        try:
            sr2_ok, sr2_reason = security_checks.check_sr2(submission_text)
            emit("SR2", sr2_ok, sr2_reason)
        except Exception as exc:
            emit("SR2", False, "SR2 check crashed: %s" % exc)

    # ------------------------------------------------------------------
    # Step 4: generate deterministic vector list (single source of truth)
    # ------------------------------------------------------------------
    vectors = []
    # idx0: pinned FR2 vector 1
    vectors.append((0x0001, 0x0002, 0x0003, 0x0004))
    # idx1: pinned FR2 vector 2 / all-max corner
    vectors.append((0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF))
    # idx2: all-zero corner
    vectors.append((0x0000, 0x0000, 0x0000, 0x0000))

    rng = random.Random(RANDOM_SEED)
    for _ in range(2000):
        va = rng.randint(0, 0xFFFF)
        vb = rng.randint(0, 0xFFFF)
        vc = rng.randint(0, 0xFFFF)
        vd = rng.randint(0, 0xFFFF)
        vectors.append((va, vb, vc, vd))

    # idx2003: duplicate of idx0 (statelessness probe for FR4)
    vectors.append(vectors[0])

    assert len(vectors) == VECTOR_COUNT, "internal error: vector count mismatch"

    # Independently-computed Python ground truth for each vector, used to
    # grade FR1/FR2 without trusting the reference netlist's own (possibly
    # defective) simulated output.
    expected_hexes = [
        format((va + vb + vc + vd) & 0xFFFFFFFF, "08x")
        for (va, vb, vc, vd) in vectors
    ]

    tmpdir = tempfile.mkdtemp(prefix="hwreveng_eval_")

    vecfile_path = os.path.join(tmpdir, "vectors.txt")
    with open(vecfile_path, "w") as f:
        f.write("%d\n" % VECTOR_COUNT)
        for (va, vb, vc, vd) in vectors:
            f.write("%04x %04x %04x %04x\n" % (va, vb, vc, vd))

    # ------------------------------------------------------------------
    # Step 5: build temp copy of reference netlist with renamed module
    # ------------------------------------------------------------------
    renamed_ref_path = os.path.join(tmpdir, "reference_renamed.v")
    module_decl_re = re.compile(r'\bmodule\s+recovered_design\b')
    renamed_text, n_subs = module_decl_re.subn(
        "module reference_design", reference_netlist_text, count=1
    )
    if n_subs == 0:
        # Could not find declaration to rename; treat as setup failure for
        # behavioral requirements only.
        fail_all_reason(
            "SETUP: could not locate 'module recovered_design' declaration "
            "in inputs/flattened_netlist.v to rename",
            ["FR1", "FR2", "FR3", "FR4"],
        )
        return finalize()

    with open(renamed_ref_path, "w") as f:
        f.write(renamed_text)

    # ------------------------------------------------------------------
    # Step 6: compile with iverilog
    # ------------------------------------------------------------------
    sim_path = os.path.join(tmpdir, "sim.vvp")
    compile_cmd = [
        "iverilog",
        "-g2012",
        "-o", sim_path,
        SUBMISSION_FILE,
        renamed_ref_path,
        PRIMITIVE_CELLS,
        TB_FILE,
    ]

    try:
        compile_proc = subprocess.run(
            compile_cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        fail_all_reason(
            "compile failed: iverilog invocation timed out",
            ["FR1", "FR2", "FR3", "FR4"],
        )
        return finalize()
    except FileNotFoundError as exc:
        fail_all_reason(
            "compile failed: iverilog not found (%s)" % exc,
            ["FR1", "FR2", "FR3", "FR4"],
        )
        return finalize()

    if compile_proc.returncode != 0:
        stderr_text = compile_proc.stderr.decode("utf-8", errors="replace")
        first_line = next(
            (ln for ln in stderr_text.splitlines() if ln.strip()), stderr_text
        ).strip()
        if not first_line:
            first_line = "iverilog returned nonzero exit code %d" % compile_proc.returncode
        fail_all_reason(
            "compile failed: %s" % first_line,
            ["FR1", "FR2", "FR3", "FR4"],
        )
        return finalize()

    # ------------------------------------------------------------------
    # Step 7: run vvp
    # ------------------------------------------------------------------
    run_cmd = ["vvp", sim_path, "+VECFILE=%s" % vecfile_path]
    try:
        run_proc = subprocess.run(
            run_cmd,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        fail_all_reason(
            "run crashed/timed out: vvp invocation timed out",
            ["FR1", "FR2", "FR3", "FR4"],
        )
        return finalize()
    except FileNotFoundError as exc:
        fail_all_reason(
            "run crashed/timed out: vvp not found (%s)" % exc,
            ["FR1", "FR2", "FR3", "FR4"],
        )
        return finalize()

    stdout_text = run_proc.stdout.decode("utf-8", errors="replace")

    # ------------------------------------------------------------------
    # Step 8: parse output and derive FR1-FR4 verdicts
    # ------------------------------------------------------------------
    vec_line_re = re.compile(
        r'^VEC\s+(\d+)\s+([0-9a-fA-F]{1,8})\s+([0-9a-fA-F]{1,8})\s*$'
    )
    done_re = re.compile(r'^VEC_DONE\s+(\d+)\s*$')

    parsed = {}  # idx -> (rec_hex, ref_hex)
    done_count = None

    for line in stdout_text.splitlines():
        line = line.strip()
        m = vec_line_re.match(line)
        if m:
            idx = int(m.group(1))
            rec_hex = m.group(2).lower().zfill(8)
            ref_hex = m.group(3).lower().zfill(8)
            parsed[idx] = (rec_hex, ref_hex)
            continue
        m2 = done_re.match(line)
        if m2:
            done_count = int(m2.group(1))

    crashed = (run_proc.returncode != 0)

    if not parsed or done_count is None:
        reason = "run crashed/timed out: no VEC output observed (exit code %d)" % run_proc.returncode
        fail_all_reason(reason, ["FR1", "FR2", "FR3", "FR4"])
        return finalize()

    # --- FR3: build succeeded, vvp ran cleanly, exact count of vectors ---
    fr3_ok = True
    fr3_reason = ""
    if crashed:
        fr3_ok = False
        fr3_reason = "run crashed/timed out: vvp exited with code %d" % run_proc.returncode
    elif len(parsed) != VECTOR_COUNT:
        fr3_ok = False
        fr3_reason = (
            "expected %d VEC lines, observed %d" % (VECTOR_COUNT, len(parsed))
        )
    elif done_count != VECTOR_COUNT:
        fr3_ok = False
        fr3_reason = (
            "expected VEC_DONE %d, observed VEC_DONE %d" % (VECTOR_COUNT, done_count)
        )
    emit("FR3", fr3_ok, fr3_reason)

    # --- FR1: all vectors match independently-computed Python ground truth ---
    if len(parsed) != VECTOR_COUNT:
        fr1_ok = False
        fr1_reason = "incomplete vector set: only %d/%d vectors observed" % (
            len(parsed), VECTOR_COUNT
        )
    else:
        mismatches = [
            idx for idx in range(VECTOR_COUNT)
            if parsed[idx][0] != expected_hexes[idx]
        ]
        if mismatches:
            first_bad = sorted(mismatches)[0]
            rec_hex, ref_hex = parsed[first_bad]
            fr1_ok = False
            fr1_reason = (
                "vector idx %d mismatched: recovered=0x%s expected=0x%s "
                "(netlist_observed=0x%s)"
                % (first_bad, rec_hex, expected_hexes[first_bad], ref_hex)
            )
        else:
            fr1_ok = True
            fr1_reason = ""
    emit("FR1", fr1_ok, fr1_reason)

    # --- FR2: pinned known vectors (hardcoded constants, independent of netlist) ---
    fr2_ok = True
    fr2_reasons = []
    if 0 not in parsed:
        fr2_ok = False
        fr2_reasons.append("idx 0 (1,2,3,4) result not observed")
    else:
        rec0, _ = parsed[0]
        if rec0 != "0000000a":
            fr2_ok = False
            fr2_reasons.append(
                "idx 0 (a=1,b=2,c=3,d=4) expected sum=0x0000000a, got 0x%s" % rec0
            )
    if 1 not in parsed:
        fr2_ok = False
        fr2_reasons.append("idx 1 (ffff,ffff,ffff,ffff) result not observed")
    else:
        rec1, _ = parsed[1]
        if rec1 != "0003fffc":
            fr2_ok = False
            fr2_reasons.append(
                "idx 1 (a=b=c=d=ffff) expected sum=0x0003fffc, got 0x%s" % rec1
            )
    emit("FR2", fr2_ok, "; ".join(fr2_reasons))

    # --- FR4: statelessness probe (idx 2003 duplicate of idx 0) ---
    last_idx = VECTOR_COUNT - 1
    if 0 not in parsed or last_idx not in parsed:
        fr4_ok = False
        fr4_reason = "could not locate idx 0 and/or idx %d for statelessness comparison" % last_idx
    else:
        rec0, _ = parsed[0]
        rec_last, _ = parsed[last_idx]
        if rec0 != rec_last:
            fr4_ok = False
            fr4_reason = (
                "identical input vector at idx 0 and idx %d produced different "
                "outputs (0x%s vs 0x%s): design is not purely combinational"
                % (last_idx, rec0, rec_last)
            )
        else:
            fr4_ok = True
            fr4_reason = ""
    emit("FR4", fr4_ok, fr4_reason)

    return finalize()


def finalize():
    # Ensure every requirement id has a verdict; if any requirement was never
    # emitted due to an unexpected early return, mark it as a setup failure.
    for rid in ALL_REQ_IDS:
        if rid not in results:
            emit(rid, False, "SETUP: requirement not evaluated")

    return 0 if all(results.get(rid, False) for rid in ALL_REQ_IDS) else 1


if __name__ == "__main__":
    sys.exit(main())