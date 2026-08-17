#!/usr/bin/env python3
"""
evaluate.py -- grader for sca_trng_reseed_fault_lockout_001

Grades submission/vulnerability_report.json against the ground truth
derivable from inputs/trng_postproc.v, inputs/fault_model.json and
inputs/design_brief.md.

Checks FR1-FR4 (format/presence) and SR1-SR4 (substantive correctness).
An optional iverilog/vvp simulation of evaluation/tb_reseed_fault.v against
inputs/trng_postproc.v is used only to corroborate SR1/SR2; it never causes
a FAIL on its own if the toolchain is unavailable or the simulation fails.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

INPUTS_DIR = "inputs"
SUBMISSION_PATH = os.path.join("submission", "vulnerability_report.json")
RTL_PATH = os.path.join(INPUTS_DIR, "trng_postproc.v")
FAULT_MODEL_PATH = os.path.join(INPUTS_DIR, "fault_model.json")
DESIGN_BRIEF_PATH = os.path.join(INPUTS_DIR, "design_brief.md")
TB_PATH = os.path.join("evaluation", "tb_reseed_fault.v")

VALID_OUTPUTS = {"rand_out", "seed_valid"}


def emit(status, req_id, reason=None):
    if status == "PASS":
        print(f"[TEST] PASS: {req_id}")
    else:
        if reason:
            print(f"[TEST] FAIL: {req_id}: {reason}")
        else:
            print(f"[TEST] FAIL: {req_id}")


def fail_all_setup(reason):
    for rid in REQUIREMENT_IDS:
        emit("FAIL", "SETUP" if False else rid, reason)
    # Also print a single SETUP marker so infra failures are legible.
    print(f"[TEST] FAIL: SETUP: {reason}")


def normalize_hex(s):
    if not isinstance(s, str):
        return None
    t = s.strip().lower()
    if t.startswith("0x"):
        t = t[2:]
    elif t.startswith("32'h"):
        t = t[4:]
    elif t.startswith("h"):
        t = t[1:]
    t = t.strip()
    if not re.fullmatch(r"[0-9a-f]+", t):
        return None
    # zero-pad / validate to 8 hex digits (32-bit)
    if len(t) > 8:
        return None
    t = t.zfill(8)
    return "0x" + t


def extract_ground_truth_fixed_constant(rtl_text):
    """
    Locate the fixed default constant loaded into seed_reg when
    entropy_ready is low during reseed_req. We search for the branch
    handling reseed_req && !entropy_ready and pull the 32-bit hex literal
    assigned to seed_reg there. We also fall back to scanning documentation
    comments referencing a "fixed"/"default"/"fallback" constant near a
    32'h... literal, to remain robust to stylistic differences.
    """
    # Strategy 1: find an `else if` (or similar) branch mentioning
    # reseed_req and !entropy_ready (in either order / spacing), then look
    # for the next seed_reg <= 32'hXXXXXXXX assignment within that block.
    hex_lit_re = re.compile(r"32'[hH]([0-9a-fA-F]{1,8})")

    # Find all conditional blocks that reference reseed_req and a negation
    # of entropy_ready (e.g. !entropy_ready, ~entropy_ready).
    cond_pattern = re.compile(
        r"if\s*\([^)]*reseed_req[^)]*\)|if\s*\([^)]*entropy_ready[^)]*\)",
        re.IGNORECASE,
    )

    lines = rtl_text.splitlines()
    candidate = None

    # Walk through, tracking whether we're inside an "entropy not ready"
    # reseed branch, based on textual heuristics.
    in_not_ready_branch = False
    brace_depth_marker = 0
    for i, line in enumerate(lines):
        low = line.lower()
        has_reseed = "reseed_req" in low
        has_not_ready = ("!entropy_ready" in low.replace(" ", "")) or (
            "~entropy_ready" in low.replace(" ", "")
        )
        # A branch header line that requests reseed while entropy is NOT ready
        if ("if" in low or "else" in low) and has_reseed and has_not_ready:
            in_not_ready_branch = True
            # search this line and following lines (small window) for the
            # seed_reg assignment
            window = "\n".join(lines[i : i + 8])
            m_assign = re.search(
                r"seed_reg\s*<=\s*32'[hH]([0-9a-fA-F]{1,8})", window
            )
            if m_assign:
                candidate = m_assign.group(1)
                break
        # Also handle case where the "not ready" condition is implicit via
        # a preceding `if (reseed_req && entropy_ready)` ... `else` block:
        # capture an `else` branch that assigns seed_reg to a fixed literal
        # and is textually distinct from the entropy_in assignment.
        if "else" in low and "seed_reg" not in low:
            window = "\n".join(lines[i : i + 8])
            if "seed_reg" in window and "entropy_in" not in window.split(
                "seed_reg"
            )[1].split("\n")[0]:
                m_assign = re.search(
                    r"seed_reg\s*<=\s*32'[hH]([0-9a-fA-F]{1,8})", window
                )
                if m_assign and candidate is None:
                    candidate = m_assign.group(1)

    if candidate:
        return normalize_hex(candidate)

    # Strategy 2 (fallback): look for a comment near a hex literal that
    # mentions "fixed"/"default"/"fallback" wording, and pull the literal
    # from that comment or the following code line.
    comment_re = re.compile(
        r"(fixed|default|fallback)[^\n]{0,80}?32'[hH]([0-9a-fA-F]{1,8})",
        re.IGNORECASE,
    )
    m = comment_re.search(rtl_text)
    if m:
        return normalize_hex(m.group(2))

    # Strategy 3: any comment line containing both "default" and a bare hex
    # constant like 0xXXXXXXXX or 32'hXXXXXXXX, take the first occurrence
    # that is NOT the reset-value literal for seed_reg (best-effort: if two
    # distinct literals are found, prefer the second one referenced in the
    # file since reset default typically appears first).
    all_hex = hex_lit_re.findall(rtl_text)
    if len(all_hex) >= 2:
        return normalize_hex(all_hex[1])
    elif len(all_hex) == 1:
        return normalize_hex(all_hex[0])

    return None


def contains_any(text, phrases):
    low = text.lower()
    return any(p in low for p in phrases)


def contains_all(text, phrases):
    low = text.lower()
    return all(p in low for p in phrases)


def check_mitigation_semantics(mitigation_text):
    """
    Returns (ok: bool, reason: str or None)
    Requires evidence of BOTH:
      (a) counting/tracking repeated reseed failures / consecutive faults /
          health-check concept
      (b) gating/blocking of output (rand_out/seed_valid/"trustworthy
          output") until fresh entropy is confirmed
    """
    if not isinstance(mitigation_text, str) or not mitigation_text.strip():
        return False, "mitigation field is empty or not a string"

    low = mitigation_text.lower()

    counting_terms = [
        "counter",
        "count",
        "consecutive",
        "repetition",
        "repeated",
        "health-check",
        "health check",
        "healthcheck",
        "track",
        "tally",
        "attempts without",
        "failed reseed",
        "reseed attempts",
    ]
    gating_terms = [
        "gate",
        "gating",
        "block",
        "blocks",
        "blocking",
        "inhibit",
        "suppress",
        "deassert",
        "withhold",
        "disable",
        "invalidate",
        "prevent",
        "hold off",
        "mask",
    ]
    output_terms = [
        "rand_out",
        "seed_valid",
        "output",
        "trustworthy",
        "downstream",
    ]
    freshness_terms = [
        "fresh entropy",
        "entropy_ready",
        "entropy_ready=1",
        "entropy_ready high",
        "genuine reseed",
        "confirmed",
        "confirm",
        "real entropy",
        "actual entropy",
        "successful reseed",
    ]

    has_counting = contains_any(low, counting_terms)
    has_gating = contains_any(low, gating_terms)
    has_output = contains_any(low, output_terms)
    has_freshness = contains_any(low, freshness_terms)

    # Superficial-fix rejection: mitigation that ONLY proposes cosmetic
    # changes without any gating/counting concept.
    superficial_only_terms = [
        "add ecc",
        "wider register",
        "widen the register",
        "bigger register",
        "add a crc",
        "use a crc",
        "more randomness",
        "add more entropy bits",
    ]
    is_superficial_flavor = contains_any(low, superficial_only_terms)

    if has_counting and has_gating and (has_output or has_freshness):
        return True, None

    if is_superficial_flavor and not (has_counting and has_gating):
        return False, (
            "mitigation appears to propose a superficial/cosmetic fix "
            "without a repetition-count/health-check gating mechanism"
        )

    missing = []
    if not has_counting:
        missing.append("consecutive-failure/health-check counting concept")
    if not has_gating:
        missing.append("output-gating/blocking concept")
    if not (has_output or has_freshness):
        missing.append("reference to blocking output until fresh entropy confirmed")

    return False, (
        "mitigation lacks: " + "; ".join(missing)
    )


def run_iverilog_corroboration(expected_hex_norm):
    """
    Best-effort optional corroboration. Returns a dict:
      {"attempted": bool, "success": bool, "seed_reg_hex": str or None,
       "detail": str}
    Never raises; any failure just yields attempted/success flags.
    """
    result = {
        "attempted": False,
        "success": False,
        "seed_reg_hex": None,
        "detail": "",
    }

    if not os.path.isfile(RTL_PATH) or not os.path.isfile(TB_PATH):
        result["detail"] = "rtl or testbench file missing"
        return result

    result["attempted"] = True

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_path = os.path.join(tmpdir, "sim.vvp")
        try:
            compile_proc = subprocess.run(
                ["iverilog", "-g2012", "-o", sim_path, RTL_PATH, TB_PATH],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            result["detail"] = f"iverilog invocation failed: {e}"
            return result

        if compile_proc.returncode != 0:
            result["detail"] = (
                "iverilog compile failed: "
                + (compile_proc.stderr or compile_proc.stdout)[:400]
            )
            return result

        try:
            run_proc = subprocess.run(
                ["vvp", sim_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            result["detail"] = f"vvp invocation failed: {e}"
            return result

        out = run_proc.stdout or ""
        m = re.search(r"SEED_REG=0x([0-9a-fA-F]{1,8})", out)
        if not m:
            result["detail"] = "no SEED_REG= line found in simulation output"
            return result

        sim_hex = normalize_hex(m.group(1))
        result["seed_reg_hex"] = sim_hex
        if expected_hex_norm is not None and sim_hex == expected_hex_norm:
            result["success"] = True
            result["detail"] = "simulation confirms seed_reg matches parsed constant"
        else:
            result["detail"] = (
                f"simulation seed_reg={sim_hex} did not match parsed "
                f"constant={expected_hex_norm}"
            )
        return result


def main():
    results = {}  # req_id -> (status, reason)

    # --- Load inputs/trng_postproc.v (required reference artifact) ---
    if not os.path.isfile(RTL_PATH):
        for rid in REQUIREMENT_IDS:
            emit("FAIL", rid, f"SETUP: {RTL_PATH} not found")
        sys.exit(1)

    try:
        with open(RTL_PATH, "r") as f:
            rtl_text = f.read()
    except Exception as e:
        for rid in REQUIREMENT_IDS:
            emit("FAIL", rid, f"SETUP: could not read {RTL_PATH}: {e}")
        sys.exit(1)

    # fault_model.json and design_brief.md are referenced by spec but not
    # strictly needed for grading logic beyond existence checks used for
    # context; still validate their presence per the SETUP contract.
    if not os.path.isfile(FAULT_MODEL_PATH):
        for rid in REQUIREMENT_IDS:
            emit("FAIL", rid, f"SETUP: {FAULT_MODEL_PATH} not found")
        sys.exit(1)
    if not os.path.isfile(DESIGN_BRIEF_PATH):
        for rid in REQUIREMENT_IDS:
            emit("FAIL", rid, f"SETUP: {DESIGN_BRIEF_PATH} not found")
        sys.exit(1)

    # --- Load submission ---
    if not os.path.isfile(SUBMISSION_PATH):
        for rid in REQUIREMENT_IDS:
            emit("FAIL", rid, f"SETUP: {SUBMISSION_PATH} not found")
        sys.exit(1)

    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw_text = f.read()
    except Exception as e:
        for rid in REQUIREMENT_IDS:
            emit("FAIL", rid, f"SETUP: could not read {SUBMISSION_PATH}: {e}")
        sys.exit(1)

    report = None
    parse_error = None
    try:
        report = json.loads(raw_text)
    except Exception as e:
        parse_error = str(e)

    # FR4: valid JSON object
    if parse_error is not None:
        results["FR4"] = ("FAIL", f"JSON parse error: {parse_error}")
    elif not isinstance(report, dict):
        results["FR4"] = ("FAIL", "top-level JSON value is not an object")
    else:
        results["FR4"] = ("PASS", None)

    if not isinstance(report, dict):
        # Cannot meaningfully grade any other requirement.
        for rid in REQUIREMENT_IDS:
            if rid == "FR4":
                continue
            results[rid] = ("FAIL", "cannot evaluate: report is not a valid JSON object")
        for rid in REQUIREMENT_IDS:
            status, reason = results[rid]
            emit(status, rid, reason)
        sys.exit(1)

    # --- FR1: required string fields present with correct types ---
    fr1_fields = ["faultable_signal", "fixed_state_value", "trigger_condition", "mitigation"]
    fr1_missing = []
    fr1_wrong_type = []
    for field in fr1_fields:
        if field not in report:
            fr1_missing.append(field)
        elif not isinstance(report[field], str):
            fr1_wrong_type.append(field)

    fixed_state_value_raw = report.get("fixed_state_value")
    fixed_state_norm = None
    fr1_hex_ok = True
    fr1_hex_reason = None
    if isinstance(fixed_state_value_raw, str):
        fixed_state_norm = normalize_hex(fixed_state_value_raw)
        if fixed_state_norm is None:
            fr1_hex_ok = False
            fr1_hex_reason = (
                f"fixed_state_value '{fixed_state_value_raw}' is not a valid "
                "0x-prefixed 32-bit hex string"
            )

    if fr1_missing or fr1_wrong_type or not fr1_hex_ok:
        reasons = []
        if fr1_missing:
            reasons.append("missing fields: " + ", ".join(fr1_missing))
        if fr1_wrong_type:
            reasons.append("wrong type for fields: " + ", ".join(fr1_wrong_type))
        if not fr1_hex_ok:
            reasons.append(fr1_hex_reason)
        results["FR1"] = ("FAIL", "; ".join(reasons))
    else:
        results["FR1"] = ("PASS", None)

    # --- FR2: affected_outputs subset of {rand_out, seed_valid}; documented_reseed_behavior_correct boolean ---
    fr2_reasons = []
    affected_outputs = report.get("affected_outputs")
    if not isinstance(affected_outputs, list) or not all(
        isinstance(x, str) for x in affected_outputs
    ):
        fr2_reasons.append("affected_outputs missing or not an array of strings")
    else:
        bad_entries = [x for x in affected_outputs if x not in VALID_OUTPUTS]
        if bad_entries:
            fr2_reasons.append(
                f"affected_outputs contains invalid entries: {bad_entries}"
            )

    documented_flag = report.get("documented_reseed_behavior_correct")
    if not isinstance(documented_flag, bool):
        fr2_reasons.append(
            "documented_reseed_behavior_correct missing or not a JSON boolean"
        )

    if fr2_reasons:
        results["FR2"] = ("FAIL", "; ".join(fr2_reasons))
    else:
        results["FR2"] = ("PASS", None)

    # --- FR3: simulation_trace_description present, non-empty, references key concepts ---
    sim_trace = report.get("simulation_trace_description")
    if not isinstance(sim_trace, str) or not sim_trace.strip():
        results["FR3"] = (
            "FAIL",
            "simulation_trace_description missing, empty, or not a string",
        )
    else:
        low = sim_trace.lower()
        has_reset = contains_any(low, ["reset", "rst_n"])
        has_reseed = "reseed_req" in low
        has_entropy_ready = "entropy_ready" in low
        has_low_indication = contains_any(
            low, ["low", "deassert", "0", "not ready", "held low", "false"]
        )
        if has_reset and has_reseed and has_entropy_ready and has_low_indication:
            results["FR3"] = ("PASS", None)
        else:
            missing_concepts = []
            if not has_reset:
                missing_concepts.append("reset")
            if not has_reseed:
                missing_concepts.append("reseed_req")
            if not has_entropy_ready:
                missing_concepts.append("entropy_ready")
            if not has_low_indication:
                missing_concepts.append("entropy_ready-low indication")
            results["FR3"] = (
                "FAIL",
                "simulation_trace_description missing concepts: "
                + ", ".join(missing_concepts),
            )

    # --- Extract ground-truth fixed constant from RTL for SR2 / corroboration ---
    gt_fixed_hex = extract_ground_truth_fixed_constant(rtl_text)

    # --- SR1: faultable_signal normalized match to entropy_ready ---
    faultable_signal = report.get("faultable_signal")
    if isinstance(faultable_signal, str):
        norm_signal = re.sub(r"[^a-z0-9_]", "", faultable_signal.strip().lower())
        if norm_signal == "entropy_ready" or (
            "entropy_ready" in norm_signal and "reseed_req" not in norm_signal
        ):
            results["SR1"] = ("PASS", None)
        else:
            results["SR1"] = (
                "FAIL",
                f"faultable_signal '{faultable_signal}' does not match "
                "expected handshake signal 'entropy_ready'",
            )
    else:
        results["SR1"] = ("FAIL", "faultable_signal missing or not a string")

    # --- SR2: fixed_state_value normalized match against ground-truth constant ---
    if fixed_state_norm is None:
        results["SR2"] = (
            "FAIL",
            "fixed_state_value missing or malformed; cannot compare to ground truth",
        )
    elif gt_fixed_hex is None:
        results["SR2"] = (
            "FAIL",
            "could not extract ground-truth fixed constant from inputs/trng_postproc.v "
            "to compare against",
        )
    elif fixed_state_norm == gt_fixed_hex:
        results["SR2"] = ("PASS", None)
    else:
        results["SR2"] = (
            "FAIL",
            f"fixed_state_value '{fixed_state_value_raw}' (normalized "
            f"{fixed_state_norm}) does not match documented default constant "
            f"{gt_fixed_hex} found in inputs/trng_postproc.v",
        )

    # --- SR3: mitigation semantic check ---
    mitigation_text = report.get("mitigation")
    sr3_ok, sr3_reason = check_mitigation_semantics(mitigation_text)
    if sr3_ok:
        results["SR3"] = ("PASS", None)
    else:
        results["SR3"] = ("FAIL", sr3_reason)

    # --- SR4: affected_outputs includes rand_out; documented flag true; trigger_condition mentions both concepts ---
    sr4_reasons = []
    if not (isinstance(affected_outputs, list) and "rand_out" in affected_outputs):
        sr4_reasons.append("affected_outputs does not include 'rand_out'")

    if documented_flag is not True:
        sr4_reasons.append(
            "documented_reseed_behavior_correct is not true "
            "(fault-free entropy_ready=1 reseed path must be documented as correct)"
        )

    trigger_condition = report.get("trigger_condition")
    if isinstance(trigger_condition, str):
        low = trigger_condition.lower()
        mentions_reseed_asserted = "reseed_req" in low and contains_any(
            low, ["assert", "high", "1", "request"]
        )
        mentions_entropy_low = "entropy_ready" in low and contains_any(
            low, ["low", "deassert", "0", "not ready", "false", "held low"]
        )
        if not (mentions_reseed_asserted and mentions_entropy_low):
            sr4_reasons.append(
                "trigger_condition does not clearly describe reseed_req "
                "asserted concurrently with entropy_ready low"
            )
    else:
        sr4_reasons.append("trigger_condition missing or not a string")

    if sr4_reasons:
        results["SR4"] = ("FAIL", "; ".join(sr4_reasons))
    else:
        results["SR4"] = ("PASS", None)

    # --- Optional iverilog corroboration for SR1/SR2 (never downgrades a PASS to FAIL by itself if toolchain unavailable; only used informationally) ---
    corroboration = run_iverilog_corroboration(gt_fixed_hex)
    if corroboration["attempted"]:
        print(f"[INFO] iverilog corroboration: {corroboration['detail']}")
        # If simulation succeeded and clearly contradicts a PASS verdict on
        # SR2 (i.e. report's claimed value does NOT match what the RTL
        # actually does when simulated), downgrade SR2 to FAIL to catch
        # reports that happen to match a mis-parsed ground truth but not
        # actual RTL behavior.
        if (
            corroboration["success"]
            and fixed_state_norm is not None
            and corroboration["seed_reg_hex"] is not None
            and fixed_state_norm != corroboration["seed_reg_hex"]
        ):
            results["SR2"] = (
                "FAIL",
                f"reported fixed_state_value {fixed_state_norm} contradicted by "
                f"iverilog simulation showing seed_reg={corroboration['seed_reg_hex']} "
                "after the reseed edge",
            )
    else:
        print(f"[INFO] iverilog corroboration skipped: {corroboration['detail']}")

    # --- Emit all results in requirement order ---
    any_fail = False
    for rid in REQUIREMENT_IDS:
        status, reason = results.get(rid, ("FAIL", "requirement not evaluated"))
        emit(status, rid, reason)
        if status != "PASS":
            any_fail = True

    sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()