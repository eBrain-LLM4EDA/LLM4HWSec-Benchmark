#!/usr/bin/env python3
"""
checks.py - Per-requirement grading functions for recovered_key.json.

Each function has signature (data: dict, netlist_text: str) -> (bool, str).
All functions are defensive: malformed/missing fields never raise, they
are treated as a failing condition with a descriptive reason.
"""

import re

import ground_truth as gt


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _get_key_bits_list(data):
    kb = data.get("key_bits")
    if not isinstance(kb, list):
        return None
    return kb


def check_fr1(data, netlist_text):
    try:
        key_bits = data.get("key_bits")
        key_gate_locations = data.get("key_gate_locations")
        topology_summary = data.get("topology_summary")

        if not isinstance(key_bits, list) or len(key_bits) == 0:
            return False, "key_bits is missing, not an array, or empty"

        if not isinstance(key_gate_locations, list) or len(key_gate_locations) == 0:
            return False, "key_gate_locations is missing, not an array, or empty"

        if not isinstance(topology_summary, str) or len(topology_summary.strip()) == 0:
            return False, "topology_summary is missing, not a string, or empty"

        seen = []
        dupes = []
        for entry in key_bits:
            if not isinstance(entry, dict):
                return False, "key_bits contains a non-object entry"
            ki = entry.get("key_input")
            if not isinstance(ki, str):
                return False, "key_bits entry missing string key_input"
            if ki in seen:
                dupes.append(ki)
            seen.append(ki)

        if dupes:
            return False, "key_bits has duplicate key_input entries: {}".format(sorted(set(dupes)))

        expected = set(gt.KEY_BIT_NAMES)
        actual = set(seen)

        missing = expected - actual
        extra = actual - expected

        if missing:
            return False, "key_bits is missing required key_input(s): {}".format(sorted(missing))

        if extra:
            return False, "key_bits contains unexpected key_input(s) not in declared range: {}".format(sorted(extra))

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_fr1: {}".format(e)


def check_fr2(data, netlist_text):
    try:
        key_bits = _get_key_bits_list(data)
        if key_bits is None:
            return False, "key_bits is missing or not an array"

        valid_range = set(gt.KEY_BIT_NAMES)
        for entry in key_bits:
            if not isinstance(entry, dict):
                return False, "key_bits contains a non-object entry"
            ki = entry.get("key_input")
            if not isinstance(ki, str):
                return False, "key_bits entry missing string key_input"
            if ki not in valid_range:
                return False, "key_input '{}' is outside the declared key bit range".format(ki)

        key_gate_locations = data.get("key_gate_locations")
        if not isinstance(key_gate_locations, list):
            return False, "key_gate_locations is missing or not an array"

        if not isinstance(netlist_text, str):
            return False, "netlist_text unavailable for cross-referencing"

        not_found = []
        for loc in key_gate_locations:
            if not isinstance(loc, str) or len(loc) == 0:
                return False, "key_gate_locations contains a non-string or empty entry"
            pattern = r'(?<![A-Za-z0-9_])' + re.escape(loc) + r'(?![A-Za-z0-9_])'
            if not re.search(pattern, netlist_text):
                not_found.append(loc)

        if not_found:
            return False, "key_gate_locations entries not found as standalone identifiers in locked_netlist.v: {}".format(not_found)

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_fr2: {}".format(e)


def check_fr3(data, netlist_text):
    try:
        key_bits = _get_key_bits_list(data)
        if key_bits is None:
            return False, "key_bits is missing or not an array"

        for entry in key_bits:
            if not isinstance(entry, dict):
                return False, "key_bits contains a non-object entry"
            value = entry.get("value")
            if value in ("0", "1"):
                ki = entry.get("key_input", "<unknown>")
                confidence = entry.get("confidence")
                if not _is_number(confidence):
                    return False, "key_input '{}' has non-numeric confidence".format(ki)
                if not (0 < confidence <= 1):
                    return False, "key_input '{}' has confidence {} outside (0,1]".format(ki, confidence)
                reasoning = entry.get("reasoning")
                if not isinstance(reasoning, str) or len(reasoning) < 15:
                    return False, "key_input '{}' has missing or too-short reasoning (<15 chars)".format(ki)

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_fr3: {}".format(e)


def check_fr4(data, netlist_text):
    try:
        key_bits = _get_key_bits_list(data)
        if key_bits is None:
            return False, "key_bits is missing or not an array"

        for entry in key_bits:
            if not isinstance(entry, dict):
                return False, "key_bits contains a non-object entry"
            value = entry.get("value")
            if value == "unknown":
                ki = entry.get("key_input", "<unknown>")
                confidence = entry.get("confidence")
                if not _is_number(confidence):
                    return False, "key_input '{}' marked unknown has non-numeric confidence".format(ki)
                if confidence != 0:
                    return False, "key_input '{}' marked unknown has confidence {} (must be exactly 0)".format(ki, confidence)

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_fr4: {}".format(e)


def check_sr1(data, netlist_text):
    try:
        key_gate_locations = data.get("key_gate_locations")
        if not isinstance(key_gate_locations, list):
            return False, "key_gate_locations is missing or not an array"

        present = [g for g in gt.REQUIRED_GATE_NAMES if g in key_gate_locations]
        count = len(present)

        if count < gt.SR1_MIN_MATCHES:
            return False, "only {} of {} required Anti-SAT gate names found in key_gate_locations (need >= {})".format(
                count, len(gt.REQUIRED_GATE_NAMES), gt.SR1_MIN_MATCHES
            )

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_sr1: {}".format(e)


def check_sr2(data, netlist_text):
    try:
        key_bits = _get_key_bits_list(data)
        if key_bits is None:
            return False, "key_bits is missing or not an array"

        by_input = {}
        for entry in key_bits:
            if isinstance(entry, dict):
                ki = entry.get("key_input")
                if isinstance(ki, str):
                    by_input[ki] = entry

        missing_bits = []
        wrong_value = []
        low_confidence = []

        for ki, expected_value in gt.CONSTANT_KEY_BITS.items():
            entry = by_input.get(ki)
            if entry is None:
                missing_bits.append(ki)
                continue
            value = entry.get("value")
            if value != expected_value:
                wrong_value.append("{} reported as '{}' expected '{}'".format(ki, value, expected_value))
            confidence = entry.get("confidence")
            if not _is_number(confidence) or confidence < gt.SR2_MIN_CONFIDENCE:
                low_confidence.append("{} confidence {} < {}".format(ki, confidence, gt.SR2_MIN_CONFIDENCE))

        problems = []
        if missing_bits:
            problems.append("missing entries for: {}".format(missing_bits))
        if wrong_value:
            problems.append("incorrect values: {}".format(wrong_value))
        if low_confidence:
            problems.append("insufficient confidence: {}".format(low_confidence))

        if problems:
            return False, "; ".join(problems)

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_sr2: {}".format(e)


def check_sr3(data, netlist_text):
    try:
        key_bits = _get_key_bits_list(data)
        if key_bits is None:
            return False, "key_bits is missing or not an array"

        fabricated = []
        for entry in key_bits:
            if not isinstance(entry, dict):
                return False, "key_bits contains a non-object entry"
            ki = entry.get("key_input")
            if not isinstance(ki, str):
                continue
            if ki in gt.CONSTANT_KEY_BITS:
                continue
            value = entry.get("value")
            confidence = entry.get("confidence")
            if value in ("0", "1") and _is_number(confidence) and confidence > gt.SR3_MAX_CONFIDENCE:
                fabricated.append("{} value={} confidence={}".format(ki, value, confidence))

        if fabricated:
            return False, "high-confidence (>{}) fabricated value(s) for non-structurally-tied key bit(s): {}".format(
                gt.SR3_MAX_CONFIDENCE, fabricated
            )

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_sr3: {}".format(e)


def check_sr4(data, netlist_text):
    try:
        topology_summary = data.get("topology_summary")
        if not isinstance(topology_summary, str) or len(topology_summary.strip()) == 0:
            return False, "topology_summary is missing, not a string, or empty"

        missing_parts = []

        if gt.FUNC_OUT_NET not in topology_summary:
            missing_parts.append("does not mention '{}'".format(gt.FUNC_OUT_NET))

        working_copy = topology_summary.replace(gt.FUNC_OUT_NET, "")
        pattern = r'(?<![A-Za-z0-9_])' + re.escape(gt.PRIMARY_OUTPUT_NET) + r'(?![A-Za-z0-9_])'
        if not re.search(pattern, working_copy):
            missing_parts.append("does not mention primary output net '{}' as a standalone token".format(gt.PRIMARY_OUTPUT_NET))

        lower_summary = topology_summary.lower()

        if not any(kw in lower_summary for kw in gt.SR4_MASK_KEYWORDS):
            missing_parts.append("does not describe a masking/gating combination (expected one of: {})".format(gt.SR4_MASK_KEYWORDS))

        if not any(kw in lower_summary for kw in gt.SR4_BRANCH_KEYWORDS):
            missing_parts.append("does not describe a two-branch/complementary structure (expected one of: {})".format(gt.SR4_BRANCH_KEYWORDS))

        if missing_parts:
            return False, "topology_summary rubric failed: {}".format("; ".join(missing_parts))

        return True, ""
    except Exception as e:
        return False, "unexpected error in check_sr4: {}".format(e)