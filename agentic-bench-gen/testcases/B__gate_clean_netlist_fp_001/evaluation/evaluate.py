#!/usr/bin/env python3
"""
evaluate.py - Grader for gate_trojan_detection / gate_clean_netlist_fp_001

Reads the reference input artifacts under inputs/ and grades the submitted
answer file at submission/trojan_report.json against the pinned schema
(FR1-FR4) and the hidden ground truth for this clean-design case (SR1-SR3).

Usage: python3 evaluation/evaluate.py
Exit code: 0 if all requirements PASS, 1 otherwise.
"""

import json
import os
import sys

# Make sure we can import the sibling helper module regardless of CWD.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import netlist_utils  # noqa: E402

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3"]

INPUT_FILES = {
    "netlist": "inputs/gate_netlist.v",
    "brief": "inputs/design_brief.md",
    "primary_io": "inputs/primary_io.txt",
}

SUBMISSION_PATH = "submission/trojan_report.json"


def emit_pass(req_id):
    print("[TEST] PASS: {}".format(req_id))


def emit_fail(req_id, reason):
    print("[TEST] FAIL: {}: {}".format(req_id, reason))


def read_file_or_setup_fail(path, results):
    """Return file contents, or None and record a SETUP failure for every
    requirement id if the file is missing."""
    if not os.path.isfile(path):
        for rid in REQUIREMENT_IDS:
            results[rid] = (False, "SETUP: {} not found".format(path))
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as exc:
        for rid in REQUIREMENT_IDS:
            results[rid] = (False, "SETUP: could not read {}: {}".format(path, exc))
        return None


def main():
    results = {}  # req_id -> (bool ok, reason str)

    # ------------------------------------------------------------------
    # Load reference input artifacts (all must be present).
    # ------------------------------------------------------------------
    netlist_text = read_file_or_setup_fail(INPUT_FILES["netlist"], results)
    if netlist_text is None:
        return finish(results)

    brief_text = read_file_or_setup_fail(INPUT_FILES["brief"], results)
    if brief_text is None:
        return finish(results)

    primary_io_text = read_file_or_setup_fail(INPUT_FILES["primary_io"], results)
    if primary_io_text is None:
        return finish(results)

    # ------------------------------------------------------------------
    # Load the submission file.
    # ------------------------------------------------------------------
    if not os.path.isfile(SUBMISSION_PATH):
        for rid in REQUIREMENT_IDS:
            results[rid] = (False, "SETUP: {} not found".format(SUBMISSION_PATH))
        return finish(results)

    try:
        with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as exc:
        for rid in REQUIREMENT_IDS:
            results[rid] = (False, "SETUP: could not read {}: {}".format(SUBMISSION_PATH, exc))
        return finish(results)

    try:
        report = json.loads(raw_text)
    except Exception as exc:
        reason = "submission JSON parse error: {}".format(exc)
        for rid in REQUIREMENT_IDS:
            results[rid] = (False, reason)
        return finish(results)

    if not isinstance(report, dict):
        reason = "submission JSON top-level value is not an object"
        for rid in REQUIREMENT_IDS:
            results[rid] = (False, reason)
        return finish(results)

    # ------------------------------------------------------------------
    # FR1: exact schema - keys and types.
    # ------------------------------------------------------------------
    expected_keys = {"infected", "suspect_nodes", "rationale", "confidence"}
    actual_keys = set(report.keys())

    fr1_ok = True
    fr1_reasons = []

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    if missing:
        fr1_ok = False
        fr1_reasons.append("missing keys: {}".format(sorted(missing)))
    if extra:
        fr1_ok = False
        fr1_reasons.append("unexpected extra keys: {}".format(sorted(extra)))

    infected_val = report.get("infected", None)
    suspect_nodes_val = report.get("suspect_nodes", None)
    rationale_val = report.get("rationale", None)
    confidence_val = report.get("confidence", None)

    if "infected" in report and not isinstance(infected_val, bool):
        fr1_ok = False
        fr1_reasons.append("'infected' must be a boolean")

    if "suspect_nodes" in report:
        if not isinstance(suspect_nodes_val, list) or not all(
            isinstance(x, str) for x in suspect_nodes_val
        ):
            fr1_ok = False
            fr1_reasons.append("'suspect_nodes' must be an array of strings")

    if "rationale" in report:
        if not isinstance(rationale_val, str) or len(rationale_val.strip()) == 0:
            fr1_ok = False
            fr1_reasons.append("'rationale' must be a non-empty string")

    if "confidence" in report:
        is_number = isinstance(confidence_val, (int, float)) and not isinstance(
            confidence_val, bool
        )
        if not is_number:
            fr1_ok = False
            fr1_reasons.append("'confidence' must be a number")
        elif not (0 <= float(confidence_val) <= 1):
            fr1_ok = False
            fr1_reasons.append("'confidence' must be within [0,1]")

    if fr1_ok:
        results["FR1"] = (True, "")
    else:
        results["FR1"] = (False, "; ".join(fr1_reasons))

    # From here on, use best-effort defaults for fields that may be malformed
    # so subsequent requirement checks can still run deterministically.
    suspect_nodes = suspect_nodes_val if isinstance(suspect_nodes_val, list) else []
    suspect_nodes = [x for x in suspect_nodes if isinstance(x, str)]
    rationale = rationale_val if isinstance(rationale_val, str) else ""
    infected = infected_val if isinstance(infected_val, bool) else None

    # ------------------------------------------------------------------
    # FR2: every suspect_nodes entry must be a verbatim token in netlist.
    # ------------------------------------------------------------------
    if len(suspect_nodes) == 0:
        results["FR2"] = (True, "")
    else:
        bad = [
            n for n in suspect_nodes if not netlist_utils.identifier_present(n, netlist_text)
        ]
        if bad:
            results["FR2"] = (
                False,
                "suspect_nodes entries not found verbatim in gate_netlist.v: {}".format(bad),
            )
        else:
            results["FR2"] = (True, "")

    # ------------------------------------------------------------------
    # FR3: infected/suspect_nodes consistency.
    # ------------------------------------------------------------------
    if infected is None:
        results["FR3"] = (False, "'infected' missing or not a boolean; cannot check consistency")
    elif infected is True:
        if len(suspect_nodes) >= 1:
            results["FR3"] = (True, "")
        else:
            results["FR3"] = (False, "infected=true but suspect_nodes is empty")
    else:  # infected is False
        if len(suspect_nodes) == 0:
            results["FR3"] = (True, "")
        else:
            results["FR3"] = (
                False,
                "infected=false but suspect_nodes is non-empty: {}".format(suspect_nodes),
            )

    # ------------------------------------------------------------------
    # FR4: rationale must reference a genuine netlist-derived identifier.
    # ------------------------------------------------------------------
    sig_ids = netlist_utils.significant_identifiers(netlist_text)
    rationale_lower_tokens = netlist_utils.tokenize(rationale)
    matched = [tok for tok in rationale_lower_tokens if tok in sig_ids]

    if len(rationale.strip()) == 0:
        results["FR4"] = (False, "rationale is empty")
    elif matched:
        results["FR4"] = (True, "")
    else:
        results["FR4"] = (
            False,
            "rationale does not reference any specific identifier from gate_netlist.v",
        )

    # ------------------------------------------------------------------
    # SR1: infected must be exactly False (ground truth: clean design).
    # ------------------------------------------------------------------
    if infected is None:
        results["SR1"] = (False, "'infected' missing or not a boolean")
    elif infected is False:
        results["SR1"] = (True, "")
    else:
        results["SR1"] = (
            False,
            "infected=true but ground truth design (gate_netlist.v) is Trojan-free",
        )

    # ------------------------------------------------------------------
    # SR2: suspect_nodes must be empty (no over-flagging of benign rare nets).
    # ------------------------------------------------------------------
    if len(suspect_nodes) == 0:
        results["SR2"] = (True, "")
    else:
        results["SR2"] = (
            False,
            "suspect_nodes must be empty for this clean design; got: {}".format(suspect_nodes),
        )

    # ------------------------------------------------------------------
    # SR3: rationale must ground its verdict in >=2 of the 3 documented
    # benign-rare-signal categories via a keyword AND a nearby explanatory
    # connective phrase (not merely naming the categories/identifiers).
    # ------------------------------------------------------------------
    grounded_count = netlist_utils.category_grounded_count(rationale)

    if grounded_count >= 2:
        results["SR3"] = (True, "")
    else:
        results["SR3"] = (
            False,
            "rationale substantively grounds (keyword + nearby explanatory connective) only "
            "{} of the 3 documented benign-rare-signal categories "
            "(reset_sync/init_counter/saturation); need >=2. A bare list of net names "
            "without an explanatory clause (e.g. 'because...', 'is expected since...', "
            "'by design...') does not satisfy this requirement.".format(grounded_count),
        )

    return finish(results)


def finish(results):
    all_ok = True
    for rid in REQUIREMENT_IDS:
        if rid not in results:
            # Should never happen, but guard against silent omissions.
            results[rid] = (False, "requirement was not evaluated")
        ok, reason = results[rid]
        if ok:
            emit_pass(rid)
        else:
            all_ok = False
            emit_fail(rid, reason)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())