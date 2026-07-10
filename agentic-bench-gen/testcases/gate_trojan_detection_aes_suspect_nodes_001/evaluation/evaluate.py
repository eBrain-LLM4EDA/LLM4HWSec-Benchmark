import json
import re
import os
import sys

FAILURES = []
RESULTS = {}


def record_pass(req_id):
    RESULTS[req_id] = True
    print("[TEST] PASS: {}".format(req_id))


def record_fail(req_id, reason):
    RESULTS[req_id] = False
    FAILURES.append(req_id)
    print("[TEST] FAIL: {}: {}".format(req_id, reason))


def entry_matches_gold(entry, gold_name):
    return entry == gold_name or entry in gold_name or gold_name in entry


def check_sr1(fields, gold):
    """Return (ok: bool, reason: str). PASS iff infected == GOLD_INFECTED."""
    infected = fields.get("infected")
    if infected == gold["GOLD_INFECTED"]:
        return True, "infected matches ground truth"
    return False, "reported infected={} but ground truth infected={}".format(
        infected, gold["GOLD_INFECTED"]
    )


def check_sr2(fields, gold):
    """Return (ok: bool, reason: str). PASS iff trigger-tree coverage >= threshold
    AND payload node is present."""
    suspect_nodes = fields.get("suspect_nodes") or []
    trigger_nodes = gold["GOLD_TRIGGER_NODES"]
    min_coverage = gold["GOLD_TRIGGER_MIN_COVERAGE"]
    payload_node = gold["GOLD_PAYLOAD_NODE"]

    covered = []
    for gold_node in trigger_nodes:
        if any(entry_matches_gold(entry, gold_node) for entry in suspect_nodes):
            covered.append(gold_node)

    payload_present = any(entry_matches_gold(entry, payload_node) for entry in suspect_nodes)

    if len(covered) >= min_coverage and payload_present:
        return True, "trigger-tree coverage {}/{} and payload node present".format(
            len(covered), len(trigger_nodes)
        )

    reasons = []
    if len(covered) < min_coverage:
        reasons.append(
            "only {}/{} trigger-tree nodes covered (need >= {}): covered={}".format(
                len(covered), len(trigger_nodes), min_coverage, covered
            )
        )
    if not payload_present:
        reasons.append("payload node '{}' not present in suspect_nodes".format(payload_node))
    return False, "; ".join(reasons)


def check_sr3(fields, gold):
    """Return (ok: bool, reason: str). PASS iff primary_output_affected == GOLD_OUTPUT."""
    primary_output_affected = fields.get("primary_output_affected")
    gold_output = gold["GOLD_OUTPUT"]
    if primary_output_affected == gold_output:
        return True, "primary_output_affected matches ground truth"
    return False, "primary_output_affected='{}' does not match ground truth '{}'".format(
        primary_output_affected, gold_output
    )


def check_sr4(fields, gold):
    """Return (ok: bool, reason: str). PASS iff rationale hits keywords from
    at least 2 distinct semantic keyword groups."""
    rationale = fields.get("rationale") or ""
    rationale_lower = rationale.lower()
    keyword_groups = gold["GOLD_RATIONALE_KEYWORD_GROUPS"]
    hit_groups = 0
    for group in keyword_groups:
        if any(keyword.lower() in rationale_lower for keyword in group):
            hit_groups += 1
    if hit_groups >= 2:
        return True, "rationale touches {} semantic keyword groups".format(hit_groups)
    return False, "rationale touches only {} of the required semantic keyword groups (need >= 2)".format(
        hit_groups
    )


NAIVE_BASELINE_FIXTURE = {
    "infected": False,
    "suspect_nodes": [],
    "rationale": "",
    "primary_output_affected": "",
}


def is_naive_equivalent(fields):
    """A submission is 'naive-equivalent' if it reports no infection, no
    suspect nodes, and no affected output -- i.e. it carries no substantive
    finding at all, regardless of what its rationale text says."""
    infected = fields.get("infected")
    suspect_nodes = fields.get("suspect_nodes") or []
    primary_output_affected = fields.get("primary_output_affected")
    return (
        infected is False
        and len(suspect_nodes) == 0
        and (primary_output_affected == "" or primary_output_affected is None)
    )


def main():
    # ---------------------------------------------------------------
    # Load private gold truth
    # ---------------------------------------------------------------
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "private"))
    try:
        import gold_truth
    except Exception as e:
        # This is our own infrastructure; treat as SETUP failure for all reqs.
        for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
            record_fail(req_id, "SETUP: could not load gold_truth module: {}".format(e))
        sys.exit(1)

    gold = {
        "GOLD_INFECTED": gold_truth.GOLD_INFECTED,
        "GOLD_TRIGGER_NODES": gold_truth.GOLD_TRIGGER_NODES,
        "GOLD_PAYLOAD_NODE": gold_truth.GOLD_PAYLOAD_NODE,
        "GOLD_OUTPUT": gold_truth.GOLD_OUTPUT,
        "GOLD_TRIGGER_MIN_COVERAGE": gold_truth.GOLD_TRIGGER_MIN_COVERAGE,
        "GOLD_RATIONALE_KEYWORD_GROUPS": gold_truth.GOLD_RATIONALE_KEYWORD_GROUPS,
    }

    # ---------------------------------------------------------------
    # Evaluator self-test: verify the rubric is internally consistent
    # by asserting that the naive baseline fixture independently fails
    # SR1-SR4 against gold. This is a sanity check on the evaluator
    # itself, not on the participant's submission. If this ever fails
    # it indicates a broken rubric (e.g. gold data misconfigured), and
    # we abort distinctly from normal grading.
    # ---------------------------------------------------------------
    try:
        fixture_checks = [
            ("SR1", check_sr1),
            ("SR2", check_sr2),
            ("SR3", check_sr3),
            ("SR4", check_sr4),
        ]
        unexpected_passes = []
        for req_id, check_fn in fixture_checks:
            fixture_ok, _fixture_reason = check_fn(NAIVE_BASELINE_FIXTURE, gold)
            if fixture_ok:
                unexpected_passes.append(req_id)
        assert not unexpected_passes, (
            "naive baseline fixture unexpectedly PASSed: {} "
            "(rubric is not self-consistent)".format(unexpected_passes)
        )
        print(
            "[EVALUATOR SELF-TEST] OK: naive baseline fixture independently "
            "fails SR1-SR4 as expected"
        )
    except AssertionError as e:
        print("[EVALUATOR SELF-TEST] BROKEN RUBRIC: {}".format(e))
        sys.exit(97)

    # ---------------------------------------------------------------
    # Load required input artifacts
    # ---------------------------------------------------------------
    netlist_path = "inputs/aes_sub_netlist.v"
    portmap_path = "inputs/port_map.json"
    submission_path = "submission/trojan_report.json"

    if not os.path.isfile(netlist_path):
        for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
            record_fail(req_id, "SETUP: {} not found".format(netlist_path))
        sys.exit(1)

    if not os.path.isfile(portmap_path):
        for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
            record_fail(req_id, "SETUP: {} not found".format(portmap_path))
        sys.exit(1)

    if not os.path.isfile(submission_path):
        for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
            record_fail(req_id, "SETUP: {} not found".format(submission_path))
        sys.exit(1)

    with open(netlist_path, "r", encoding="utf-8") as f:
        netlist_text = f.read()

    with open(portmap_path, "r", encoding="utf-8") as f:
        try:
            portmap_json = json.load(f)
        except Exception as e:
            for req_id in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4", "SR5"]:
                record_fail(req_id, "SETUP: could not parse {}: {}".format(portmap_path, e))
            sys.exit(1)

    # ---------------------------------------------------------------
    # Parse real gate instance names from the netlist (structural,
    # independent of any submission wording).
    # ---------------------------------------------------------------
    instance_pattern = re.compile(
        r'\b(?:and|or|xor|not|nand|nor)\s+(\w+)\s*\('
    )
    parsed_instances = set(instance_pattern.findall(netlist_text))

    # ---------------------------------------------------------------
    # Parse output port names from port_map.json
    # ---------------------------------------------------------------
    output_ports = set()
    try:
        for port in portmap_json.get("ports", []):
            if isinstance(port, dict) and port.get("direction") == "output":
                name = port.get("name")
                if isinstance(name, str):
                    output_ports.add(name)
    except Exception:
        output_ports = set()

    # ---------------------------------------------------------------
    # Load submission
    # ---------------------------------------------------------------
    with open(submission_path, "r", encoding="utf-8") as f:
        raw = f.read()

    report = None
    parse_error = None
    try:
        report = json.loads(raw)
    except Exception as e:
        parse_error = str(e)

    # ---------------------------------------------------------------
    # FR1: valid JSON with required fields/types
    # ---------------------------------------------------------------
    infected = None
    suspect_nodes = None
    rationale = None
    fr1_ok = True

    if parse_error is not None:
        record_fail("FR1", "submission is not valid JSON: {}".format(parse_error))
        fr1_ok = False
    elif not isinstance(report, dict):
        record_fail("FR1", "top-level JSON value is not an object")
        fr1_ok = False
    else:
        infected = report.get("infected", None)
        suspect_nodes = report.get("suspect_nodes", None)
        rationale = report.get("rationale", None)

        reasons = []
        if not isinstance(infected, bool):
            reasons.append("'infected' missing or not boolean")
        if not isinstance(suspect_nodes, list) or not all(isinstance(x, str) for x in (suspect_nodes or [])):
            reasons.append("'suspect_nodes' missing or not an array of strings")
        if not isinstance(rationale, str) or len(rationale.strip()) == 0:
            reasons.append("'rationale' missing or empty string")

        if reasons:
            record_fail("FR1", "; ".join(reasons))
            fr1_ok = False
        else:
            record_pass("FR1")

    # Normalize for downstream checks even if FR1 failed, to still produce
    # deterministic FAILs for dependent requirements rather than crashing.
    if not isinstance(infected, bool):
        infected = False
    if not isinstance(suspect_nodes, list):
        suspect_nodes = []
    else:
        suspect_nodes = [x for x in suspect_nodes if isinstance(x, str)]
    if not isinstance(rationale, str):
        rationale = ""

    primary_output_affected = None
    if isinstance(report, dict):
        primary_output_affected = report.get("primary_output_affected", None)
    if not isinstance(primary_output_affected, str):
        primary_output_affected = None

    # ---------------------------------------------------------------
    # FR2: every suspect_nodes entry corresponds to a real instance
    # ---------------------------------------------------------------
    if not fr1_ok:
        record_fail("FR2", "cannot evaluate: FR1 failed (malformed report)")
    else:
        bad_entries = []
        for entry in suspect_nodes:
            match = False
            for name in parsed_instances:
                if entry == name or entry in name or name in entry:
                    match = True
                    break
            if not match:
                bad_entries.append(entry)
        if bad_entries:
            record_fail("FR2", "suspect_nodes entries not found in netlist instances: {}".format(bad_entries))
        else:
            record_pass("FR2")

    # ---------------------------------------------------------------
    # FR3: infected/suspect_nodes count consistency
    # ---------------------------------------------------------------
    if not fr1_ok:
        record_fail("FR3", "cannot evaluate: FR1 failed (malformed report)")
    else:
        if infected is True:
            if len(suspect_nodes) >= 2:
                record_pass("FR3")
            else:
                record_fail("FR3", "infected==true but suspect_nodes has fewer than 2 entries")
        else:
            if len(suspect_nodes) == 0:
                record_pass("FR3")
            else:
                record_fail("FR3", "infected==false but suspect_nodes is not empty")

    # ---------------------------------------------------------------
    # FR4: primary_output_affected format
    # ---------------------------------------------------------------
    if not fr1_ok:
        record_fail("FR4", "cannot evaluate: FR1 failed (malformed report)")
    elif primary_output_affected is None:
        record_fail("FR4", "'primary_output_affected' missing or not a string")
    else:
        if infected is False:
            if primary_output_affected == "":
                record_pass("FR4")
            else:
                record_fail("FR4", "infected==false but primary_output_affected is not empty string")
        else:
            if primary_output_affected in output_ports:
                record_pass("FR4")
            else:
                record_fail(
                    "FR4",
                    "primary_output_affected '{}' is not a declared output port ({})".format(
                        primary_output_affected, sorted(output_ports)
                    ),
                )

    # ---------------------------------------------------------------
    # Build the actual-submission fields dict used by check_sr1..check_sr4
    # ---------------------------------------------------------------
    submission_fields = {
        "infected": infected,
        "suspect_nodes": suspect_nodes,
        "rationale": rationale,
        "primary_output_affected": primary_output_affected,
    }

    # ---------------------------------------------------------------
    # SR1-SR4: run against the actual submission fields
    # ---------------------------------------------------------------
    sr1_ok = None
    sr2_ok = None
    sr3_ok = None
    sr4_ok = None

    if not fr1_ok:
        record_fail("SR1", "cannot evaluate: FR1 failed (malformed report)")
        sr1_ok = False
    else:
        sr1_ok, reason = check_sr1(submission_fields, gold)
        if sr1_ok:
            record_pass("SR1")
        else:
            record_fail("SR1", reason)

    if not fr1_ok:
        record_fail("SR2", "cannot evaluate: FR1 failed (malformed report)")
        sr2_ok = False
    else:
        sr2_ok, reason = check_sr2(submission_fields, gold)
        if sr2_ok:
            record_pass("SR2")
        else:
            record_fail("SR2", reason)

    if not fr1_ok:
        record_fail("SR3", "cannot evaluate: FR1 failed (malformed report)")
        sr3_ok = False
    else:
        sr3_ok, reason = check_sr3(submission_fields, gold)
        if sr3_ok:
            record_pass("SR3")
        else:
            record_fail("SR3", reason)

    if not fr1_ok:
        record_fail("SR4", "cannot evaluate: FR1 failed (malformed report)")
        sr4_ok = False
    else:
        sr4_ok, reason = check_sr4(submission_fields, gold)
        if sr4_ok:
            record_pass("SR4")
        else:
            record_fail("SR4", reason)

    # ---------------------------------------------------------------
    # SR5: genuinely grades the submission's own content.
    #
    # SR5 fails if the submission is functionally equivalent to the
    # naive/empty baseline (infected=false, suspect_nodes=[],
    # primary_output_affected='') UNLESS that same submission
    # independently satisfies SR1-SR4 (which is impossible given the
    # gold data used here, since GOLD_INFECTED is True and a naive
    # submission cannot list trigger/payload nodes or a correct
    # affected output -- but we check it honestly rather than
    # hardcoding the outcome, so the logic self-corrects if gold ever
    # changes). SR5 passes for any submission that is not naive-
    # equivalent, regardless of whether it is fully correct on
    # SR1-SR4 (that correctness is separately graded by SR1-SR4
    # themselves) -- SR5's job is only to catch the "did nothing"
    # case slipping through as a pass.
    # ---------------------------------------------------------------
    if not fr1_ok:
        record_fail("SR5", "cannot evaluate: FR1 failed (malformed report)")
    else:
        naive_equivalent = is_naive_equivalent(submission_fields)
        all_sr_pass = bool(sr1_ok) and bool(sr2_ok) and bool(sr3_ok) and bool(sr4_ok)

        if naive_equivalent and not all_sr_pass:
            record_fail(
                "SR5",
                "submission is functionally equivalent to the naive/empty baseline "
                "(infected=false, suspect_nodes=[], primary_output_affected='') and "
                "does not independently satisfy SR1-SR4",
            )
        else:
            record_pass("SR5")

    # ---------------------------------------------------------------
    # Final verdict
    # ---------------------------------------------------------------
    if FAILURES:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()