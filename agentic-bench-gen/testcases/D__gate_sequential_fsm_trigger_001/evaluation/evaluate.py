#!/usr/bin/env python3
"""evaluate.py – Grade a trojan_report.json submission against hidden ground truth."""

import json
import os
import sys

# ---------------------------------------------------------------------------
# Hidden ground truth (embedded directly to keep the harness self-contained)
# ---------------------------------------------------------------------------
TRIGGER_DFFS = {"u_trig_dff0", "u_trig_dff1", "u_trig_dff2", "u_trig_dff3"}
PAYLOAD_GATE = "u_xor_payload"
ROLE_MAP = {
    "u_trig_dff0": "trigger_logic",
    "u_trig_dff1": "trigger_logic",
    "u_trig_dff2": "trigger_logic",
    "u_trig_dff3": "trigger_logic",
    "u_xor_payload": "payload_gate",
}
MAX_FALSE_POSITIVES = 2

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def emit_pass(req_id: str) -> None:
    print(f"[TEST] PASS: {req_id}")

def emit_fail(req_id: str, reason: str) -> None:
    print(f"[TEST] FAIL: {req_id}: {reason}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    report_path = os.path.join("submission", "trojan_report.json")

    # --- FR1: valid JSON parseable -----------------------------------------
    if not os.path.isfile(report_path):
        emit_fail("FR1", f"{report_path} not found")
        # Cannot continue without the file – fail remaining FRs/SRs and exit
        for req in ("FR2", "FR3", "SR1", "SR2", "SR3"):
            emit_fail(req, "cannot grade because report file is missing")
        return 1

    try:
        with open(report_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        emit_fail("FR1", f"invalid JSON: {exc}")
        for req in ("FR2", "FR3", "SR1", "SR2", "SR3"):
            emit_fail(req, "cannot grade because report is not valid JSON")
        return 1
    except Exception as exc:
        emit_fail("FR1", f"unexpected error reading report: {exc}")
        for req in ("FR2", "FR3", "SR1", "SR2", "SR3"):
            emit_fail(req, "cannot grade because report could not be read")
        return 1

    emit_pass("FR1")

    # --- FR2: top-level key "suspect_nodes" is an array --------------------
    if not isinstance(data, dict):
        emit_fail("FR2", "top-level JSON value is not an object")
        for req in ("FR3", "SR1", "SR2", "SR3"):
            emit_fail(req, "cannot grade because report structure is invalid")
        return 1

    suspect_nodes = data.get("suspect_nodes")
    if suspect_nodes is None:
        emit_fail("FR2", "missing key 'suspect_nodes'")
        for req in ("FR3", "SR1", "SR2", "SR3"):
            emit_fail(req, "cannot grade because 'suspect_nodes' is missing")
        return 1

    if not isinstance(suspect_nodes, list):
        emit_fail("FR2", "'suspect_nodes' is not an array")
        for req in ("FR3", "SR1", "SR2", "SR3"):
            emit_fail(req, "cannot grade because 'suspect_nodes' is not an array")
        return 1

    emit_pass("FR2")

    # --- FR3: each element has string "node_name" and "role" ---------------
    fr3_ok = True
    for idx, node in enumerate(suspect_nodes):
        if not isinstance(node, dict):
            emit_fail("FR3", f"element {idx} is not an object")
            fr3_ok = False
            continue
        node_name = node.get("node_name")
        role = node.get("role")
        if not isinstance(node_name, str):
            emit_fail("FR3", f"element {idx}: 'node_name' missing or not a string")
            fr3_ok = False
        if not isinstance(role, str):
            emit_fail("FR3", f"element {idx}: 'role' missing or not a string")
            fr3_ok = False

    if fr3_ok:
        emit_pass("FR3")

    # If FR3 failed we can still attempt SR checks on the well-formed entries
    # Build sets from the report (only entries that passed FR3)
    reported_trigger = set()
    reported_payload = set()
    reported_all = set()
    role_by_node = {}

    for node in suspect_nodes:
        if not isinstance(node, dict):
            continue
        name = node.get("node_name")
        role = node.get("role")
        if not isinstance(name, str) or not isinstance(role, str):
            continue
        reported_all.add(name)
        role_by_node[name] = role
        if role == "trigger_logic":
            reported_trigger.add(name)
        elif role == "payload_gate":
            reported_payload.add(name)

    # --- SR1: all trigger DFFs identified with role "trigger_logic" --------
    missing_trigger = TRIGGER_DFFS - reported_trigger
    extra_trigger = reported_trigger - TRIGGER_DFFS
    if missing_trigger or extra_trigger:
        reason_parts = []
        if missing_trigger:
            reason_parts.append(f"missing={sorted(missing_trigger)}")
        if extra_trigger:
            reason_parts.append(f"extra={sorted(extra_trigger)}")
        emit_fail("SR1", "; ".join(reason_parts))
    else:
        emit_pass("SR1")

    # --- SR2: payload XOR gate identified, false positives ≤ 2 -------------
    # False positives = reported nodes that are NOT in the ground truth
    ground_truth_nodes = set(ROLE_MAP.keys())
    false_positives = reported_all - ground_truth_nodes

    if PAYLOAD_GATE not in reported_payload:
        emit_fail("SR2", f"payload gate '{PAYLOAD_GATE}' not reported with role 'payload_gate'")
    elif len(false_positives) > MAX_FALSE_POSITIVES:
        emit_fail("SR2", f"too many false positives: {len(false_positives)} (max {MAX_FALSE_POSITIVES})")
    else:
        emit_pass("SR2")

    # --- SR3: correct nodes have correct roles -----------------------------
    sr3_ok = True
    for node_name, expected_role in ROLE_MAP.items():
        if node_name not in reported_all:
            # Not reported at all – already caught by SR1/SR2, but still a role mismatch
            emit_fail("SR3", f"node '{node_name}' not reported")
            sr3_ok = False
            continue
        reported_role = role_by_node[node_name]
        if reported_role != expected_role:
            emit_fail("SR3", f"node='{node_name}' expected='{expected_role}' got='{reported_role}'")
            sr3_ok = False

    if sr3_ok:
        emit_pass("SR3")

    # -----------------------------------------------------------------------
    # Determine exit code
    # -----------------------------------------------------------------------
    # Collect all emitted lines to decide pass/fail (simple approach: re-read
    # from stdout is messy; we track failures with a flag).
    # We'll just check if any FAIL was emitted by scanning our own output.
    # A cleaner way: track failures in a list.
    # For simplicity, we re-parse the printed lines.
    # But since we are the only writer, we can just track a global flag.
    # Let's do it properly with a global list.
    # We'll refactor slightly: collect results in a list and print at the end.
    # However, the spec says "emit exactly one [TEST] PASS/FAIL per requirement"
    # and we already printed them.  We'll just exit based on a flag we maintain.
    # We'll set a module-level flag.
    global _any_failure
    return 1 if _any_failure else 0


_any_failure = False

# Monkey-patch emit_fail to set the flag
_original_emit_fail = emit_fail
def emit_fail(req_id: str, reason: str) -> None:
    global _any_failure
    _any_failure = True
    _original_emit_fail(req_id, reason)

# Rebind the name in this module's namespace
emit_fail = emit_fail


if __name__ == "__main__":
    sys.exit(main())