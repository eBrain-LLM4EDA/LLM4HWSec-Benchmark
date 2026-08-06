#!/usr/bin/env python3
"""
evaluate.py -- Gate Trojan Detection (mult8_top) grader.

Reads the fixed reference netlist under inputs/ and the participant's
answer file at submission/trojan_report.json, then grades the answer
against the required schema (FR1-FR4) and against hidden ground truth
(SR1-SR5). Emits one '[TEST] PASS: <id>' / '[TEST] FAIL: <id>: <reason>'
line per requirement and exits 0 iff every requirement passed.
"""

import json
import os
import sys
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PRIVATE_DIR = os.path.join(HERE, "private")
sys.path.insert(0, PRIVATE_DIR)

try:
    import ground_truth as GT  # noqa: E402
    import netlist_utils as NU  # noqa: E402
except Exception as e:
    print(f"[TEST] FAIL: SETUP: could not import private evaluation modules: {e}")
    sys.exit(1)

INPUTS_DIR = os.path.join(ROOT, "inputs")
SUBMISSION_PATH = os.path.join(ROOT, "submission", "trojan_report.json")
NETLIST_PATH = os.path.join(INPUTS_DIR, "mult8_netlist.v")
PORT_LIST_PATH = os.path.join(INPUTS_DIR, "port_list.txt")
DESIGN_BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")
TB_PROBE_PATH = os.path.join(HERE, "tb_probe.v")

ALL_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]

results = {}


def emit_pass(rid):
    results[rid] = True
    print(f"[TEST] PASS: {rid}")


def emit_fail(rid, reason):
    results[rid] = False
    print(f"[TEST] FAIL: {rid}: {reason}")


def fail_all(reason):
    for rid in ALL_IDS:
        if rid not in results:
            emit_fail(rid, reason)


def golden_product(a_val, b_val):
    return (a_val & 0xFF) * (b_val & 0xFF)


def mismatched_bits(expected_int, actual_int, width=16):
    bits = []
    for i in range(width):
        if ((expected_int >> i) & 1) != ((actual_int >> i) & 1):
            bits.append(i)
    return bits


def run_iverilog_sim(vector_pairs, timeout=10):
    """
    Compile and simulate inputs/mult8_netlist.v + evaluation/tb_probe.v
    against a list of (a_val, b_val) int pairs. Returns
    (ok: bool, reason_or_None, results: dict[(a,b) -> p_int]).
    Never writes into inputs/.
    """
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if iverilog is None or vvp is None:
        return False, "iverilog/vvp not found on PATH", {}

    if not os.path.isfile(TB_PROBE_PATH):
        return False, "evaluation/tb_probe.v harness file not found", {}

    tmpdir = tempfile.mkdtemp(prefix="gate_trojan_eval_")
    try:
        vectors_path = os.path.join(tmpdir, "vectors.txt")
        with open(vectors_path, "w") as vf:
            for (a_val, b_val) in vector_pairs:
                vf.write(f"{a_val & 0xFF:08b} {b_val & 0xFF:08b}\n")

        sim_bin = os.path.join(tmpdir, "sim.vvp")
        compile_cmd = [iverilog, "-g2012", "-o", sim_bin, NETLIST_PATH, TB_PROBE_PATH]
        try:
            cp = subprocess.run(
                compile_cmd, cwd=tmpdir, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, "iverilog compile timed out", {}
        if cp.returncode != 0:
            first_line = (cp.stderr or cp.stdout or "unknown compile error").strip().splitlines()
            first_line = first_line[0] if first_line else "unknown compile error"
            return False, f"compile failed: {first_line}", {}

        try:
            rp = subprocess.run(
                [vvp, sim_bin], cwd=tmpdir, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            return False, "vvp simulation timed out", {}
        if rp.returncode != 0:
            first_line = (rp.stderr or rp.stdout or "unknown sim error").strip().splitlines()
            first_line = first_line[0] if first_line else "unknown sim error"
            return False, f"simulation crashed: {first_line}", {}

        out_results = {}
        for line in rp.stdout.splitlines():
            line = line.strip()
            if not line.startswith("VEC "):
                continue
            parts = line.split()
            if len(parts) != 4:
                continue
            _, a_bin, b_bin, p_bin = parts
            try:
                a_int = int(a_bin, 2)
                b_int = int(b_bin, 2)
                p_int = int(p_bin, 2)
            except ValueError:
                continue
            out_results[(a_int, b_int)] = p_int

        missing = [v for v in vector_pairs if v not in out_results]
        if missing:
            return False, f"simulation output missing results for vectors: {missing[:3]}", out_results

        return True, None, out_results
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def simulate_check(a_val, b_val):
    """
    SR4 cross-check: run the reported (a_val,b_val) plus a fixed set of
    control vectors through the real netlist. The reported input must
    show a mismatch at bit7 only (trojan actually fires there); every
    control vector must match the golden product exactly (trojan does
    not fire elsewhere -> false-positive-rate check).
    """
    control_vectors = list(GT.CONTROL_VECTORS)
    reported = (a_val & 0xFF, b_val & 0xFF)

    vector_set = []
    seen = set()
    for v in control_vectors + [reported]:
        vv = (v[0] & 0xFF, v[1] & 0xFF)
        if vv not in seen:
            seen.add(vv)
            vector_set.append(vv)

    ok, reason, sim_results = run_iverilog_sim(vector_set)
    if not ok:
        return False, reason or "simulation failed"

    # Check reported input: must mismatch golden ONLY at bit 7, and must
    # actually differ there (trigger fires).
    p_reported = sim_results.get(reported)
    if p_reported is None:
        return False, f"no simulation result for reported input {reported}"
    golden_reported = golden_product(*reported)
    bad_bits = mismatched_bits(golden_reported, p_reported)
    if bad_bits != [7]:
        if not bad_bits:
            return False, (
                f"reported input {reported} produced output matching golden "
                f"exactly (trojan did not fire; bit7 not flipped)"
            )
        return False, (
            f"reported input {reported} mismatched golden at bits {bad_bits} "
            f"(expected mismatch at bit7 only)"
        )

    # Check control vectors: must match golden exactly everywhere.
    for cv in control_vectors:
        cv = (cv[0] & 0xFF, cv[1] & 0xFF)
        if cv == reported:
            continue
        p_cv = sim_results.get(cv)
        if p_cv is None:
            return False, f"no simulation result for control vector {cv}"
        golden_cv = golden_product(*cv)
        cv_bad = mismatched_bits(golden_cv, p_cv)
        if cv_bad:
            return False, (
                f"control vector {cv} mismatched golden at bits {cv_bad} "
                f"(trojan appears to fire outside the reported rare input)"
            )

    return True, None


def main():
    # ---- input artifact presence checks ----
    for fname, path in [
        ("mult8_netlist.v", NETLIST_PATH),
        ("port_list.txt", PORT_LIST_PATH),
        ("design_brief.md", DESIGN_BRIEF_PATH),
    ]:
        if not os.path.isfile(path):
            print(f"[TEST] FAIL: SETUP: inputs/{fname} not found")
            sys.exit(1)

    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: submission/trojan_report.json not found")
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r") as f:
            report = json.load(f)
    except Exception as e:
        fail_all(f"submission/trojan_report.json is not valid JSON: {e}")
        sys.exit(1)

    if not isinstance(report, dict):
        fail_all("submission/trojan_report.json top-level value is not a JSON object")
        sys.exit(1)

    try:
        instance_names, gate_type_counts, total_gates = NU.parse_netlist(NETLIST_PATH)
    except Exception as e:
        fail_all(f"could not parse inputs/mult8_netlist.v: {e}")
        sys.exit(1)

    # ================= FR1 =================
    classification = report.get("classification")
    if isinstance(classification, str) and classification in ("clean", "infected"):
        emit_pass("FR1")
    else:
        emit_fail("FR1", f"classification field missing/invalid: {classification!r}")

    # ================= FR2 =================
    netlist_summary = report.get("netlist_summary")
    fr2_ok = False
    fr2_reason = ""
    if not isinstance(netlist_summary, dict):
        fr2_reason = "netlist_summary missing or not a JSON object"
    else:
        rt = netlist_summary.get("total_gates")
        rgc = netlist_summary.get("gate_type_counts")
        if not isinstance(rt, int) or isinstance(rt, bool):
            fr2_reason = "netlist_summary.total_gates missing or not an integer"
        elif rt != total_gates:
            fr2_reason = f"netlist_summary.total_gates={rt} does not match actual gate count={total_gates}"
        elif not isinstance(rgc, dict):
            fr2_reason = "netlist_summary.gate_type_counts missing or not a JSON object"
        else:
            mismatches = []
            for prim in GT.GATE_PRIMITIVES:
                expected = gate_type_counts.get(prim, 0)
                got = rgc.get(prim, 0)
                if not isinstance(got, int) or isinstance(got, bool):
                    mismatches.append(f"{prim}:not-an-int")
                elif got != expected:
                    mismatches.append(f"{prim}:{got}!={expected}")
            if mismatches:
                fr2_reason = "gate_type_counts mismatch: " + ", ".join(mismatches)
            else:
                fr2_ok = True
    if fr2_ok:
        emit_pass("FR2")
    else:
        emit_fail("FR2", fr2_reason)

    # ================= FR3 =================
    suspect_nodes = report.get("suspect_nodes")
    fr3_ok = False
    fr3_reason = ""
    if classification == "infected":
        if not isinstance(suspect_nodes, list) or len(suspect_nodes) == 0:
            fr3_reason = "suspect_nodes missing/empty while classification=='infected'"
        else:
            bad = []
            for entry in suspect_nodes:
                if not isinstance(entry, dict):
                    bad.append("entry-not-object")
                    continue
                iname = entry.get("instance_name")
                role = entry.get("role")
                if not isinstance(iname, str) or iname not in instance_names:
                    bad.append(f"unknown-instance-name:{iname!r}")
                if role not in ("trigger", "payload"):
                    bad.append(f"invalid-role:{role!r}")
            if bad:
                fr3_reason = "invalid suspect_nodes entries: " + "; ".join(bad[:6])
            else:
                fr3_ok = True
    else:
        fr3_ok = True
    if fr3_ok:
        emit_pass("FR3")
    else:
        emit_fail("FR3", fr3_reason)

    # ================= FR4 =================
    trigger_condition = report.get("trigger_condition")
    fr4_ok = False
    fr4_reason = ""
    parsed_ab = None
    if classification == "infected":
        if not isinstance(trigger_condition, str) or not trigger_condition.strip():
            fr4_reason = "trigger_condition missing/empty while classification=='infected'"
        else:
            parsed_ab = NU.parse_trigger_condition(trigger_condition)
            if parsed_ab is None:
                fr4_reason = "trigger_condition could not be parsed into concrete 8-bit a,b values"
            else:
                fr4_ok = True
    else:
        fr4_ok = True
    if fr4_ok:
        emit_pass("FR4")
    else:
        emit_fail("FR4", fr4_reason)

    # ================= SR1 =================
    if classification == "infected":
        emit_pass("SR1")
    else:
        emit_fail("SR1", f"classification is {classification!r}, hidden ground truth is 'infected'")

    # ================= SR2 =================
    sr2_ok = False
    if isinstance(suspect_nodes, list):
        for entry in suspect_nodes:
            if (
                isinstance(entry, dict)
                and entry.get("instance_name") == GT.EXPECTED_PAYLOAD_NODE
                and entry.get("role") == "payload"
            ):
                sr2_ok = True
                break
    if sr2_ok:
        emit_pass("SR2")
    else:
        emit_fail(
            "SR2",
            f"suspect_nodes does not contain instance_name='{GT.EXPECTED_PAYLOAD_NODE}' with role='payload'",
        )

    # ================= SR3 =================
    sr3_ok = False
    if isinstance(suspect_nodes, list):
        for entry in suspect_nodes:
            if (
                isinstance(entry, dict)
                and entry.get("instance_name") == GT.EXPECTED_TRIGGER_FINAL_NODE
                and entry.get("role") == "trigger"
            ):
                sr3_ok = True
                break
    if sr3_ok:
        emit_pass("SR3")
    else:
        emit_fail(
            "SR3",
            f"suspect_nodes does not contain instance_name='{GT.EXPECTED_TRIGGER_FINAL_NODE}' with role='trigger'",
        )

    # ================= SR4 =================
    sr4_ok = False
    sr4_reason = ""
    if classification != "infected":
        sr4_reason = "classification is not 'infected'; cannot credit trigger_condition"
    elif not isinstance(trigger_condition, str) or not trigger_condition.strip():
        sr4_reason = "trigger_condition missing/empty"
    else:
        if parsed_ab is None:
            parsed_ab = NU.parse_trigger_condition(trigger_condition)
        if parsed_ab is None:
            sr4_reason = "trigger_condition could not be parsed into concrete 8-bit a,b values"
        else:
            a_val, b_val = parsed_ab
            sim_ok, sim_reason = simulate_check(a_val, b_val)
            if sim_ok:
                sr4_ok = True
            else:
                exact_match = (a_val == GT.EXPECTED_A and b_val == GT.EXPECTED_B)
                if exact_match:
                    sr4_reason = f"reported (a,b) matched expected values but toolchain cross-check failed: {sim_reason}"
                else:
                    sr4_reason = (
                        f"reported trigger input a={a_val:#010b},b={b_val:#010b} failed "
                        f"toolchain cross-check: {sim_reason}"
                    )
    if sr4_ok:
        emit_pass("SR4")
    else:
        emit_fail("SR4", sr4_reason)

    # ================= SR5 =================
    sr5_ok = (
        classification == "infected"
        and isinstance(suspect_nodes, list)
        and len(suspect_nodes) > 0
        and isinstance(trigger_condition, str)
        and trigger_condition.strip() != ""
        and isinstance(netlist_summary, dict)
        and isinstance(netlist_summary.get("total_gates"), int)
        and not isinstance(netlist_summary.get("total_gates"), bool)
        and isinstance(netlist_summary.get("gate_type_counts"), dict)
    )
    if sr5_ok:
        emit_pass("SR5")
    else:
        emit_fail(
            "SR5",
            "submission fails minimum completeness bar (requires classification=='infected', "
            "non-empty suspect_nodes, non-empty trigger_condition, and a valid netlist_summary)",
        )

    if all(results.get(rid) for rid in ALL_IDS):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()