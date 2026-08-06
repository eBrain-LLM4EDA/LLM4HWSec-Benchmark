import sys
import os
import json

def main():
    all_ids = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]
    results = {}

    # ---- Load inputs/secure_boot_check.v ----
    rtl_path = os.path.join("inputs", "secure_boot_check.v")
    if not os.path.isfile(rtl_path):
        print("[TEST] FAIL: SETUP: inputs/secure_boot_check.v not found")
        sys.exit(1)
    with open(rtl_path, "r", encoding="utf-8") as f:
        rtl_text = f.read()

    total_lines = rtl_text.count("\n") + 1

    # ---- Load submission/vulnerability_report.json ----
    sub_path = os.path.join("submission", "vulnerability_report.json")
    if not os.path.isfile(sub_path):
        print("[TEST] FAIL: SETUP: submission/vulnerability_report.json not found")
        sys.exit(1)
    with open(sub_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # ---- Import private helpers ----
    private_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private")
    if private_dir not in sys.path:
        sys.path.insert(0, private_dir)
    try:
        import rtl_analysis
        import report_checks
    except Exception as e:
        print("[TEST] FAIL: SETUP: could not import private helper modules: %s" % e)
        sys.exit(1)

    # ---- Parse submitted JSON (parse errors count against FR4, not SETUP) ----
    parse_error = None
    report = {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            report = parsed
        else:
            parse_error = "top-level JSON value is not an object"
    except Exception as e:
        parse_error = "JSON parse error: %s" % e

    # ---- Compute ground truth from RTL via private static analysis ----
    try:
        registers = rtl_analysis.extract_registers(rtl_text)
    except Exception as e:
        registers = []
        registers_error = str(e)
    else:
        registers_error = None

    try:
        fsm_states_truth = set(rtl_analysis.extract_fsm_states(rtl_text))
    except Exception as e:
        fsm_states_truth = set()
        fsm_states_error = str(e)
    else:
        fsm_states_error = None

    try:
        gating = rtl_analysis.find_output_gating_signal(rtl_text)
    except Exception as e:
        gating = {}
        gating_error = str(e)
    else:
        gating_error = None

    auth_signal = gating.get("auth_signal") if isinstance(gating, dict) else None
    state_signal = gating.get("state_signal") if isinstance(gating, dict) else None
    done_state = gating.get("done_state") if isinstance(gating, dict) else None
    compare_state = gating.get("compare_state") if isinstance(gating, dict) else None

    reg_by_name = {}
    for r in registers:
        if isinstance(r, dict) and "name" in r:
            reg_by_name[r["name"]] = r

    def safe_list(key):
        val = report.get(key)
        return val if isinstance(val, list) else []

    analyzed_registers = safe_list("analyzed_registers")
    submitted_fsm_states = safe_list("fsm_states")
    critical_nodes = safe_list("critical_nodes")
    hardening_recs = safe_list("hardening_recommendations")

    def find_entry_by_field(entries, field, value):
        for e in entries:
            if isinstance(e, dict) and e.get(field) == value:
                return e
        return None

    def entry_text(e, *fields):
        parts = []
        for fld in fields:
            v = e.get(fld) if isinstance(e, dict) else None
            if isinstance(v, str):
                parts.append(v)
        return " ".join(parts)

    # ---------------- FR1 ----------------
    def check_FR1():
        if not isinstance(report.get("analyzed_registers"), list):
            return False, "analyzed_registers missing or not a list"
        if len(analyzed_registers) < 6:
            return False, "analyzed_registers has fewer than 6 entries"
        if registers_error:
            return False, "internal error deriving ground-truth registers: %s" % registers_error
        if not registers:
            return False, "could not derive any real registers from RTL (internal error)"
        submitted_names = set()
        for e in analyzed_registers:
            if isinstance(e, dict) and isinstance(e.get("name"), str):
                submitted_names.add(e["name"])
        missing = [r["name"] for r in registers if r["name"] not in submitted_names]
        if missing:
            return False, "missing real registers in analyzed_registers: %s" % ", ".join(sorted(missing))
        return True, ""

    # ---------------- FR2 ----------------
    def check_FR2():
        if not registers:
            return False, "no ground-truth registers available to check against"
        problems = []
        matched_any = False
        for e in analyzed_registers:
            if not isinstance(e, dict):
                continue
            name = e.get("name")
            if name not in reg_by_name:
                continue
            matched_any = True
            truth = reg_by_name[name]
            width = e.get("width")
            line = e.get("line")

            # (a) width must exactly match the statically-derived declared width
            if not isinstance(width, int) or isinstance(width, bool) or width != truth.get("width"):
                problems.append("%s: width mismatch (got %r expected %r)" % (name, width, truth.get("width")))
                continue

            # (b) lenient format/bounds validation of 'line' only
            line_ok = False
            if isinstance(line, int) and not isinstance(line, bool):
                if 1 <= line <= total_lines:
                    line_ok = True
            elif isinstance(line, list) and len(line) == 2:
                start, end = line[0], line[1]
                if (isinstance(start, int) and not isinstance(start, bool) and
                        isinstance(end, int) and not isinstance(end, bool)):
                    if 1 <= start <= end <= total_lines:
                        line_ok = True
            if not line_ok:
                problems.append(
                    "%s: 'line' is malformed or out of bounds (got %r; must be an int or "
                    "[start,end] int pair within 1..%d)" % (name, line, total_lines)
                )

        if problems:
            return False, "; ".join(problems[:5])
        if not matched_any:
            return False, "no submitted analyzed_registers entries matched real register names"
        return True, ""

    # ---------------- FR3 ----------------
    def check_FR3():
        if fsm_states_error:
            return False, "internal error deriving ground-truth fsm states: %s" % fsm_states_error
        if not fsm_states_truth:
            return False, "could not derive fsm states from RTL (internal error)"
        if not isinstance(report.get("fsm_states"), list):
            return False, "fsm_states missing or not a list"
        submitted = set(s for s in submitted_fsm_states if isinstance(s, str))
        missing = fsm_states_truth - submitted
        if missing:
            return False, "missing fsm states: %s" % ", ".join(sorted(missing))
        return True, ""

    # ---------------- FR4 ----------------
    def check_FR4():
        if parse_error:
            return False, parse_error
        required_keys = ["analyzed_registers", "fsm_states", "critical_nodes", "hardening_recommendations"]
        for k in required_keys:
            if k not in report:
                return False, "missing required top-level key '%s'" % k
        if not isinstance(report["analyzed_registers"], list):
            return False, "analyzed_registers is not a list"
        if not isinstance(report["fsm_states"], list):
            return False, "fsm_states is not a list"
        if not isinstance(report["critical_nodes"], list):
            return False, "critical_nodes is not a list"
        if not isinstance(report["hardening_recommendations"], list):
            return False, "hardening_recommendations is not a list"

        names_to_check = []
        for e in report["analyzed_registers"]:
            if isinstance(e, dict) and isinstance(e.get("name"), str):
                names_to_check.append(e["name"])
        for s in report["fsm_states"]:
            if isinstance(s, str):
                names_to_check.append(s)
        for e in report["critical_nodes"]:
            if isinstance(e, dict) and isinstance(e.get("signal"), str):
                names_to_check.append(e["signal"])
        for e in report["hardening_recommendations"]:
            if isinstance(e, dict) and isinstance(e.get("target_signal"), str):
                names_to_check.append(e["target_signal"])

        for name in names_to_check:
            if name not in rtl_text:
                return False, "identifier '%s' not found verbatim in secure_boot_check.v" % name

        return True, ""

    # ---------------- SR1 ----------------
    def check_SR1():
        if gating_error or not auth_signal:
            return False, "internal error deriving auth-result signal: %s" % (gating_error or "not found")
        node = find_entry_by_field(critical_nodes, "signal", auth_signal)
        if node is None:
            return False, "no critical_nodes entry with signal == '%s'" % auth_signal
        text = entry_text(node, "exploit_scenario", "reason")
        if not report_checks.is_bypass_language(text):
            return False, "critical_nodes entry for '%s' lacks bypass/force narrative" % auth_signal
        return True, ""

    # ---------------- SR2 ----------------
    def check_SR2():
        if gating_error or not state_signal:
            return False, "internal error deriving state-control signal: %s" % (gating_error or "not found")
        node = find_entry_by_field(critical_nodes, "signal", state_signal)
        if node is None:
            return False, "no critical_nodes entry with signal == '%s'" % state_signal
        text = entry_text(node, "exploit_scenario", "reason")
        if not report_checks.is_bypass_language(text):
            return False, "critical_nodes entry for '%s' lacks bypass/force narrative" % state_signal
        lowered = text.lower()
        state_refs_ok = False
        for lit in (done_state, compare_state):
            if lit and lit.lower() in lowered:
                state_refs_ok = True
                break
        if not state_refs_ok:
            return False, "critical_nodes entry for '%s' does not reference the DONE/COMPARE state transition" % state_signal
        return True, ""

    # ---------------- SR3 ----------------
    def check_SR3():
        if gating_error or not auth_signal or not state_signal:
            return False, "internal error deriving critical signal names for hardening check"
        missing_targets = []
        for sig in (auth_signal, state_signal):
            rec = find_entry_by_field(hardening_recs, "target_signal", sig)
            if rec is None:
                missing_targets.append(sig)
                continue
            text = entry_text(rec, "technique", "rationale")
            if not report_checks.is_hardening_technique(text):
                missing_targets.append(sig)
        if missing_targets:
            return False, "missing substantive hardening recommendation(s) for: %s" % ", ".join(missing_targets)
        return True, ""

    # ---------------- SR4 ----------------
    def check_SR4():
        if gating_error or not auth_signal or not state_signal:
            return False, "internal error deriving critical signal names"
        auth_node = find_entry_by_field(critical_nodes, "signal", auth_signal)
        state_node = find_entry_by_field(critical_nodes, "signal", state_signal)
        if auth_node is None and state_node is None:
            return False, "critical_nodes omits both the auth-result and state-control signals"
        if auth_node is None:
            return False, "critical_nodes omits the auth-result signal '%s'" % auth_signal
        if state_node is None:
            return False, "critical_nodes omits the state-control signal '%s'" % state_signal
        return True, ""

    checks = {
        "FR1": check_FR1,
        "FR2": check_FR2,
        "FR3": check_FR3,
        "FR4": check_FR4,
        "SR1": check_SR1,
        "SR2": check_SR2,
        "SR3": check_SR3,
        "SR4": check_SR4,
    }

    all_passed = True
    for rid in all_ids:
        try:
            ok, reason = checks[rid]()
        except Exception as e:
            ok, reason = False, "unexpected error during check: %s" % e
        if ok:
            print("[TEST] PASS: %s" % rid)
        else:
            print("[TEST] FAIL: %s: %s" % (rid, reason))
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()