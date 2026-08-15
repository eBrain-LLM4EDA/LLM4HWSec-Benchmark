#!/usr/bin/env python3
"""
evaluate.py - Grades submission/recovered_key.json against the hidden
ground truth derived structurally from inputs/locked_c880.v (via
evaluation/private/netlist_utils.py) combined with an embedded golden
key value (evaluation/private/golden_key.py) at the structurally-live
key bit indices.

Prints one '[TEST] PASS: <id>' or '[TEST] FAIL: <id>: <reason>' line per
requirement (FR1-FR4, SR1-SR4). Exits 0 iff all requirements pass.
"""

import sys
import os
import json
import re

VALID_GATE_TYPES = {"XOR", "XNOR", "MUX", "BUF", "UNKNOWN"}
VALID_KEY_CHARS = set("01x")

REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

_GATE_TYPE_SUFFIX_RE = re.compile(
    r'_(XOR|XNOR|MUX|BUF|UNKNOWN)$', re.IGNORECASE
)


def _normalize_gate_name(name):
    """
    Normalize a submitted gate_name for matching against real netlist
    instance names: lowercase, and strip an optional trailing
    '_<GATETYPE>' decoration (one of _XOR/_XNOR/_MUX/_BUF/_UNKNOWN,
    case-insensitive) that a submitter may have appended for readability.
    Returns a list of candidate normalized forms to try (with and without
    suffix stripped), since we don't know a priori whether the suffix was
    part of the real instance name or a decoration.
    """
    if not isinstance(name, str):
        return []
    candidates = set()
    lname = name.lower()
    candidates.add(lname)
    stripped = _GATE_TYPE_SUFFIX_RE.sub('', name)
    candidates.add(stripped.lower())
    return list(candidates)


def fail_setup(reason):
    print("[TEST] FAIL: SETUP: {}".format(reason))
    sys.exit(1)


def main():
    results = {}  # rid -> (bool, reason)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(base_dir)
    private_dir = os.path.join(base_dir, "private")

    netlist_path = os.path.join(repo_root, "inputs", "locked_c880.v")
    brief_path = os.path.join(repo_root, "inputs", "design_brief.md")
    oracle_path = os.path.join(repo_root, "inputs", "oracle_vectors.txt")
    submission_path = os.path.join(repo_root, "submission", "recovered_key.json")

    # ---- Mandatory infra presence checks ----
    if not os.path.isfile(netlist_path):
        fail_setup("{} not found".format(netlist_path))
    if not os.path.isfile(brief_path):
        fail_setup("{} not found".format(brief_path))
    if not os.path.isfile(oracle_path):
        fail_setup("{} not found".format(oracle_path))
    if not os.path.isfile(submission_path):
        fail_setup("{} not found".format(submission_path))

    if private_dir not in sys.path:
        sys.path.insert(0, private_dir)

    try:
        import netlist_utils  # noqa: E402
        import golden_key  # noqa: E402
    except Exception as e:
        fail_setup("failed to import private helper modules: {}".format(e))

    # ---- Parse the fixed netlist for structural ground truth ----
    try:
        parsed = netlist_utils.parse_netlist(netlist_path)
    except Exception as e:
        fail_setup("failed to parse {}: {}".format(netlist_path, e))

    try:
        key_width_gt = int(parsed["key_width"])
        all_instance_names = set(parsed["all_instance_names"])
        key_gate_table = parsed["key_gate_table"]  # idx(int) -> {gate_type, gate_name, output_net}
        live_indices = sorted(int(i) for i in parsed["live_indices"])
        dead_indices = sorted(int(i) for i in parsed["dead_indices"])
    except Exception as e:
        fail_setup("malformed structural parse result from netlist_utils: {}".format(e))

    if len(live_indices) == 0:
        fail_setup("structural parse produced zero live key indices; reference derivation broken")

    # Build a normalized-name lookup set for real instance names (lowercase).
    normalized_instance_names = set(n.lower() for n in all_instance_names)

    # ---- Obtain embedded golden key bit values ----
    try:
        golden_bits_all = golden_key.get_golden_key_bits()
        if not isinstance(golden_bits_all, dict):
            raise ValueError("get_golden_key_bits() did not return a dict")
        golden_bits = {}
        missing = []
        for idx in live_indices:
            if idx not in golden_bits_all:
                missing.append(idx)
                continue
            val = golden_bits_all[idx]
            if val not in ("0", "1"):
                missing.append(idx)
                continue
            golden_bits[idx] = val
        if missing:
            raise ValueError(
                "golden_key.py missing/invalid values for live index(es) {}".format(missing)
            )
    except Exception as e:
        fail_setup("failed to obtain golden key reference: {}".format(e))

    # ---- Load submission JSON (failure here is graded as FR1, not SETUP) ----
    sub = None
    sub_json_error = None
    try:
        with open(submission_path) as f:
            raw = f.read()
        sub = json.loads(raw)
    except Exception as e:
        sub_json_error = str(e)

    # =========================================================
    # FR1: valid JSON with required top-level keys/types
    # =========================================================
    try:
        if sub_json_error is not None:
            raise ValueError("submission is not valid JSON: {}".format(sub_json_error))
        if not isinstance(sub, dict):
            raise ValueError("top-level submission JSON is not an object")
        if "key_width" not in sub:
            raise ValueError("missing 'key_width'")
        if "recovered_key" not in sub:
            raise ValueError("missing 'recovered_key'")
        if "key_gates" not in sub:
            raise ValueError("missing 'key_gates'")
        if not isinstance(sub["key_width"], int) or isinstance(sub["key_width"], bool):
            raise ValueError("'key_width' is not an integer")
        if not isinstance(sub["recovered_key"], str):
            raise ValueError("'recovered_key' is not a string")
        if not isinstance(sub["key_gates"], list):
            raise ValueError("'key_gates' is not a list")
        results["FR1"] = (True, "")
    except Exception as e:
        results["FR1"] = (False, str(e))

    # =========================================================
    # FR2: key_width matches netlist bus width
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check key_width: {}".format(results["FR1"][1]))
        sub_key_width = sub["key_width"]
        if sub_key_width != key_width_gt:
            raise ValueError(
                "submission key_width={} does not match netlist keyIn width={}".format(
                    sub_key_width, key_width_gt
                )
            )
        results["FR2"] = (True, "")
    except Exception as e:
        results["FR2"] = (False, str(e))

    # =========================================================
    # FR3: every key_gates[].gate_name exists in netlist instances,
    #      gate_type in allowed set. Matching is case-insensitive and
    #      tolerates an optional trailing '_<GATETYPE>' decoration.
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check key_gates: {}".format(results["FR1"][1]))
        key_gates = sub["key_gates"]
        bad_entries = []
        for idx, entry in enumerate(key_gates):
            if not isinstance(entry, dict):
                bad_entries.append("entry {} is not an object".format(idx))
                continue
            gname = entry.get("gate_name")
            gtype = entry.get("gate_type")

            found_name = False
            if isinstance(gname, str):
                if gname in all_instance_names:
                    found_name = True
                else:
                    for cand in _normalize_gate_name(gname):
                        if cand in normalized_instance_names:
                            found_name = True
                            break
            if not found_name:
                bad_entries.append(
                    "entry {} gate_name '{}' not found in netlist instances".format(idx, gname)
                )
                continue
            if not isinstance(gtype, str) or gtype.upper() not in VALID_GATE_TYPES:
                bad_entries.append(
                    "entry {} gate_type '{}' not in allowed set".format(idx, gtype)
                )
        if bad_entries:
            raise ValueError("; ".join(bad_entries[:5]) + (" (+more)" if len(bad_entries) > 5 else ""))
        results["FR3"] = (True, "")
    except Exception as e:
        results["FR3"] = (False, str(e))

    # =========================================================
    # FR4: recovered_key length == key_width, chars in {0,1,x}
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check recovered_key: {}".format(results["FR1"][1]))
        rk = sub["recovered_key"]
        sub_key_width = sub.get("key_width")
        expected_len = sub_key_width if isinstance(sub_key_width, int) else key_width_gt
        if len(rk) != expected_len:
            raise ValueError(
                "recovered_key length {} != key_width {}".format(len(rk), expected_len)
            )
        bad_chars = set(rk) - VALID_KEY_CHARS
        if bad_chars:
            raise ValueError("recovered_key contains invalid characters: {}".format(sorted(bad_chars)))
        results["FR4"] = (True, "")
    except Exception as e:
        results["FR4"] = (False, str(e))

    # =========================================================
    # SR1: >=5 of 6 live key gates matched by gate_name + gate_type
    #      (name matching is case-insensitive and tolerates an optional
    #      trailing '_<GATETYPE>' decoration)
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check key_gates: {}".format(results["FR1"][1]))
        key_gates = sub["key_gates"]
        matches = 0
        mismatched_idx = []
        for idx in live_indices:
            gt = key_gate_table.get(idx)
            if gt is None:
                continue
            gt_name = gt["gate_name"]
            gt_name_lower = gt_name.lower()
            gt_type = gt["gate_type"].upper()
            found = False
            for entry in key_gates:
                if not isinstance(entry, dict):
                    continue
                ename = entry.get("gate_name")
                etype = entry.get("gate_type")
                if not isinstance(ename, str) or not isinstance(etype, str):
                    continue
                if etype.upper() != gt_type:
                    continue
                if ename == gt_name:
                    found = True
                    break
                if gt_name_lower in _normalize_gate_name(ename):
                    found = True
                    break
            if found:
                matches += 1
            else:
                mismatched_idx.append(idx)
        total_live = len(live_indices)
        required = max(0, total_live - 1)  # at least total_live-1
        if total_live == 6:
            required = 5
        if matches < required:
            raise ValueError(
                "only {}/{} live key gates correctly localized (need >= {}); missed indices {}".format(
                    matches, total_live, required, mismatched_idx
                )
            )
        results["SR1"] = (True, "")
    except Exception as e:
        results["SR1"] = (False, str(e))

    # =========================================================
    # SR2: recovered_key matches golden key at live index positions
    #      (golden derived from embedded ground truth in golden_key.py,
    #      restricted to the structurally-live indices computed above)
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check recovered_key: {}".format(results["FR1"][1]))

        rk = sub["recovered_key"]
        mismatches = []
        for idx in live_indices:
            if idx >= len(rk):
                mismatches.append(idx)
                continue
            if rk[idx] != golden_bits[idx]:
                mismatches.append(idx)

        if mismatches:
            raise ValueError(
                "recovered_key mismatches golden key at live index positions {}".format(mismatches)
            )
        results["SR2"] = (True, "")
    except Exception as e:
        results["SR2"] = (False, str(e))

    # =========================================================
    # SR3: no brute-force enumeration / contradictory duplicates
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check key_gates: {}".format(results["FR1"][1]))
        key_gates = sub["key_gates"]
        sub_key_width = sub.get("key_width")
        kw = sub_key_width if isinstance(sub_key_width, int) and sub_key_width > 0 else key_width_gt

        if len(key_gates) > 2 * kw:
            raise ValueError(
                "key_gates has {} entries, exceeding 2*key_width={} "
                "(looks like brute-force enumeration of the whole netlist)".format(
                    len(key_gates), 2 * kw
                )
            )

        by_idx = {}
        contradictions = []
        for entry in key_gates:
            if not isinstance(entry, dict):
                continue
            kbi = entry.get("key_bit_index")
            gname = entry.get("gate_name")
            gtype = entry.get("gate_type")
            if not isinstance(kbi, int):
                continue
            norm_name = gname.lower() if isinstance(gname, str) else gname
            key_tuple = (norm_name, (gtype.upper() if isinstance(gtype, str) else gtype))
            if kbi in by_idx and by_idx[kbi] != key_tuple:
                contradictions.append(kbi)
            else:
                by_idx[kbi] = key_tuple

        if contradictions:
            raise ValueError(
                "contradictory/duplicate entries for key_bit_index(es) {}".format(
                    sorted(set(contradictions))
                )
            )
        results["SR3"] = (True, "")
    except Exception as e:
        results["SR3"] = (False, str(e))

    # =========================================================
    # SR4: not the trivial/empty naive answer
    # =========================================================
    try:
        if results["FR1"][0] is False:
            raise ValueError("cannot check triviality: {}".format(results["FR1"][1]))
        rk = sub["recovered_key"]
        key_gates = sub["key_gates"]
        all_x = len(rk) > 0 and all(c == "x" for c in rk)
        empty_gates = len(key_gates) == 0
        if all_x and empty_gates:
            raise ValueError(
                "submission is a trivial/naive answer: all-'x' recovered_key with empty key_gates"
            )
        results["SR4"] = (True, "")
    except Exception as e:
        results["SR4"] = (False, str(e))

    # ---- Emit results ----
    all_pass = True
    for rid in REQ_IDS:
        ok, reason = results.get(rid, (False, "requirement not evaluated"))
        if ok:
            print("[TEST] PASS: {}".format(rid))
        else:
            print("[TEST] FAIL: {}: {}".format(rid, reason))
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()