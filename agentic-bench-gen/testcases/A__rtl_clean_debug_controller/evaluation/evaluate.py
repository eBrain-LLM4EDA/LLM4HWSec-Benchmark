#!/usr/bin/env python3
"""evaluate.py - Grades submission/trojan_report.json for rtl_clean_debug_controller."""

import json
import sys
import os

REQUIREMENTS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2"]
SUBMISSION_PATH = "submission/trojan_report.json"

def emit(verdict, req_id, reason=None):
    if verdict == "PASS":
        print(f"[TEST] PASS: {req_id}")
    else:
        msg = f"[TEST] FAIL: {req_id}"
        if reason:
            msg += f": {reason}"
        print(msg)

def main():
    # Check submission file exists
    if not os.path.isfile(SUBMISSION_PATH):
        for req in REQUIREMENTS:
            emit("FAIL", req, f"{SUBMISSION_PATH} not found")
        sys.exit(1)

    # FR1: valid JSON
    try:
        with open(SUBMISSION_PATH, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        emit("FAIL", "FR1", f"JSON parse error: {e}")
        # Cannot proceed with other checks
        for req in ["FR2", "FR3", "FR4", "SR1", "SR2"]:
            emit("FAIL", req, "cannot evaluate due to FR1 failure")
        sys.exit(1)
    emit("PASS", "FR1")

    # FR2: required fields and types
    fr2_ok = True
    if not isinstance(data, dict):
        emit("FAIL", "FR2", "top-level JSON is not an object")
        fr2_ok = False
    else:
        if "infected" not in data:
            emit("FAIL", "FR2", "missing 'infected' field")
            fr2_ok = False
        elif not isinstance(data["infected"], bool):
            emit("FAIL", "FR2", "'infected' is not a boolean")
            fr2_ok = False

        if "trojan_candidates" not in data:
            emit("FAIL", "FR2", "missing 'trojan_candidates' field")
            fr2_ok = False
        elif not isinstance(data["trojan_candidates"], list):
            emit("FAIL", "FR2", "'trojan_candidates' is not an array")
            fr2_ok = False

    if fr2_ok:
        emit("PASS", "FR2")

    # FR3: conditional structure when infected is true
    infected = data.get("infected", None)
    candidates = data.get("trojan_candidates", None)

    if infected is True:
        if not isinstance(candidates, list) or len(candidates) == 0:
            emit("FAIL", "FR3", "infected is true but trojan_candidates is empty or missing")
        else:
            fr3_ok = True
            for i, cand in enumerate(candidates):
                if not isinstance(cand, dict):
                    emit("FAIL", "FR3", f"trojan_candidates[{i}] is not an object")
                    fr3_ok = False
                    continue
                for field in ["signal_path", "trigger_condition", "payload_effect"]:
                    val = cand.get(field)
                    if not isinstance(val, str) or val.strip() == "":
                        emit("FAIL", "FR3", f"trojan_candidates[{i}] missing or empty '{field}'")
                        fr3_ok = False
            if fr3_ok:
                emit("PASS", "FR3")
    else:
        # If infected is not true, FR3 is vacuously satisfied
        emit("PASS", "FR3")

    # FR4: rationale must be non-empty string
    rationale = data.get("rationale", None)
    if isinstance(rationale, str) and rationale.strip() != "":
        emit("PASS", "FR4")
    else:
        emit("FAIL", "FR4", "rationale is missing or empty")

    # SR1: no trojan_candidate should reference debug_enable paths
    sr1_ok = True
    if isinstance(candidates, list):
        for i, cand in enumerate(candidates):
            if isinstance(cand, dict):
                sp = cand.get("signal_path", "")
                if isinstance(sp, str) and "debug_enable" in sp.lower():
                    emit("FAIL", "SR1", f"trojan_candidates[{i}] references debug_enable")
                    sr1_ok = False
    if sr1_ok:
        emit("PASS", "SR1")

    # SR2: infected must be false and trojan_candidates empty
    if infected is False and isinstance(candidates, list) and len(candidates) == 0:
        emit("PASS", "SR2")
    else:
        reason = []
        if infected is not False:
            reason.append(f"infected is {infected}, expected false")
        if not (isinstance(candidates, list) and len(candidates) == 0):
            reason.append("trojan_candidates is not an empty array")
        emit("FAIL", "SR2", "; ".join(reason))

    # Determine exit code
    # We need to check if any FAIL was emitted. We'll re-read our own output.
    # Simpler: track failures in a list.
    # We'll just re-parse stdout? Better to track internally.
    # Since we already emitted, we can't easily change. We'll just exit based on a flag.
    # Let's restructure slightly: collect results, then print and exit.
    # But the spec says emit markers during execution. We'll just exit based on a global flag.
    # We'll set a global variable.
    # For simplicity, we'll just exit 0 if all passed, else 1. We'll track with a list.
    # We'll modify the emit function to record failures.
    # Since we already defined emit, we'll use a closure or global list.
    # Let's just re-parse the output? No, that's fragile.
    # We'll use a global list.
    global failures
    if 'failures' not in globals():
        failures = []
    # But emit is already defined. We'll just check the list at the end.
    # We'll need to modify emit to append to failures.
    # Let's redefine emit to use a list.
    # Actually, we can just check if any FAIL was printed by capturing, but easier: use a list.
    # We'll just do a simple check: if any requirement failed, exit 1.
    # We'll track with a set.
    # Since we already printed, we can't easily change. We'll just exit based on a flag we set now.
    # We'll set a global variable 'any_fail' and update it in emit.
    # But emit is already defined. We'll just use a mutable list.
    # Let's just do a quick fix: we'll re-read the output? No.
    # We'll just assume that if we reach here, we can check the conditions again.
    # Actually, we can just compute the final verdict by re-evaluating the conditions.
    # That's redundant but works.
    # We'll just set a global list at the start.
    # Let's modify the script to use a list from the beginning.
    # Since we are writing the file now, we can design it properly.
    # We'll use a list to collect results, then print and exit.
    # But the spec says emit markers during execution. We can still collect and print at the end.
    # However, the spec also says "emit exactly one [TEST] PASS/FAIL per requirement". Order doesn't matter.
    # We'll collect tuples and print at the end.
    # Let's rewrite main to collect results.
    # We'll do that.

if __name__ == "__main__":
    # We'll use a results list to collect (verdict, req_id, reason)
    results = []

    def add_result(verdict, req_id, reason=None):
        results.append((verdict, req_id, reason))

    # Check submission file exists
    if not os.path.isfile(SUBMISSION_PATH):
        for req in REQUIREMENTS:
            add_result("FAIL", req, f"{SUBMISSION_PATH} not found")
        for verdict, req_id, reason in results:
            if verdict == "PASS":
                print(f"[TEST] PASS: {req_id}")
            else:
                msg = f"[TEST] FAIL: {req_id}"
                if reason:
                    msg += f": {reason}"
                print(msg)
        sys.exit(1)

    # FR1: valid JSON
    try:
        with open(SUBMISSION_PATH, "r") as f:
            data = json.load(f)
        add_result("PASS", "FR1")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        add_result("FAIL", "FR1", f"JSON parse error: {e}")
        for req in ["FR2", "FR3", "FR4", "SR1", "SR2"]:
            add_result("FAIL", req, "cannot evaluate due to FR1 failure")
        for verdict, req_id, reason in results:
            if verdict == "PASS":
                print(f"[TEST] PASS: {req_id}")
            else:
                msg = f"[TEST] FAIL: {req_id}"
                if reason:
                    msg += f": {reason}"
                print(msg)
        sys.exit(1)

    # FR2: required fields and types
    fr2_ok = True
    if not isinstance(data, dict):
        add_result("FAIL", "FR2", "top-level JSON is not an object")
        fr2_ok = False
    else:
        if "infected" not in data:
            add_result("FAIL", "FR2", "missing 'infected' field")
            fr2_ok = False
        elif not isinstance(data["infected"], bool):
            add_result("FAIL", "FR2", "'infected' is not a boolean")
            fr2_ok = False

        if "trojan_candidates" not in data:
            add_result("FAIL", "FR2", "missing 'trojan_candidates' field")
            fr2_ok = False
        elif not isinstance(data["trojan_candidates"], list):
            add_result("FAIL", "FR2", "'trojan_candidates' is not an array")
            fr2_ok = False

    if fr2_ok:
        add_result("PASS", "FR2")

    # FR3: conditional structure when infected is true
    infected = data.get("infected", None)
    candidates = data.get("trojan_candidates", None)

    if infected is True:
        if not isinstance(candidates, list) or len(candidates) == 0:
            add_result("FAIL", "FR3", "infected is true but trojan_candidates is empty or missing")
        else:
            fr3_ok = True
            for i, cand in enumerate(candidates):
                if not isinstance(cand, dict):
                    add_result("FAIL", "FR3", f"trojan_candidates[{i}] is not an object")
                    fr3_ok = False
                    continue
                for field in ["signal_path", "trigger_condition", "payload_effect"]:
                    val = cand.get(field)
                    if not isinstance(val, str) or val.strip() == "":
                        add_result("FAIL", "FR3", f"trojan_candidates[{i}] missing or empty '{field}'")
                        fr3_ok = False
            if fr3_ok:
                add_result("PASS", "FR3")
    else:
        # If infected is not true, FR3 is vacuously satisfied
        add_result("PASS", "FR3")

    # FR4: rationale must be non-empty string
    rationale = data.get("rationale", None)
    if isinstance(rationale, str) and rationale.strip() != "":
        add_result("PASS", "FR4")
    else:
        add_result("FAIL", "FR4", "rationale is missing or empty")

    # SR1: no trojan_candidate should reference debug_enable paths
    sr1_ok = True
    if isinstance(candidates, list):
        for i, cand in enumerate(candidates):
            if isinstance(cand, dict):
                sp = cand.get("signal_path", "")
                if isinstance(sp, str) and "debug_enable" in sp.lower():
                    add_result("FAIL", "SR1", f"trojan_candidates[{i}] references debug_enable")
                    sr1_ok = False
    if sr1_ok:
        add_result("PASS", "SR1")

    # SR2: infected must be false and trojan_candidates empty
    if infected is False and isinstance(candidates, list) and len(candidates) == 0:
        add_result("PASS", "SR2")
    else:
        reason = []
        if infected is not False:
            reason.append(f"infected is {infected}, expected false")
        if not (isinstance(candidates, list) and len(candidates) == 0):
            reason.append("trojan_candidates is not an empty array")
        add_result("FAIL", "SR2", "; ".join(reason))

    # Print all results
    any_fail = False
    for verdict, req_id, reason in results:
        if verdict == "PASS":
            print(f"[TEST] PASS: {req_id}")
        else:
            any_fail = True
            msg = f"[TEST] FAIL: {req_id}"
            if reason:
                msg += f": {reason}"
            print(msg)

    sys.exit(1 if any_fail else 0)