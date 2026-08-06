#!/usr/bin/env python3
"""
evaluate.py -- RTL Trojan Detection grader for lockstep_alu.

Grades submission/trojan_report.json against hidden ground truth for
task rtl_trojan_detection_lockstep_alu_001 (Compensating Trojan in a
Lockstep ALU Checker).

Checks FR1-FR4 (structural/functional requirements on the report) and
SR1-SR5 (substantive security-finding requirements). Also attempts an
optional iverilog simulation of inputs/lockstep_alu.v to corroborate the
ground-truth trigger's presence in the shipped RTL; this simulation is
purely informational evidence and never gates PASS/FAIL of the graded
requirements, since this domain grades the submitted answer file.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "trojan_report.json")
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
LOCKSTEP_ALU_PATH = os.path.join(INPUTS_DIR, "lockstep_alu.v")
TB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tb_trigger_check.v")

results = []  # list of (req_id, bool_pass, reason)


def record(req_id, ok, reason=""):
    if ok:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    results.append((req_id, ok, reason))


def fail_setup(msg):
    print("[TEST] FAIL: SETUP: {}".format(msg))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Load submission
# ---------------------------------------------------------------------------

if not os.path.isfile(SUBMISSION_PATH):
    fail_setup("submission/trojan_report.json not found")

with open(SUBMISSION_PATH, "r", encoding="utf-8", errors="replace") as f:
    raw_text = f.read()

# Parse JSON defensively: a malformed/invalid submission must be reported
# as an FR1 FAIL (not a SETUP failure and not an uncaught crash), so that
# the malformed-JSON mutation path runs end-to-end and is correctly
# detected as a requirement failure.
report = None
json_parse_error = None
try:
    parsed = json.loads(raw_text)
    if isinstance(parsed, dict):
        report = parsed
    else:
        json_parse_error = "top-level JSON value is not an object (got {})".format(
            type(parsed).__name__
        )
except Exception as e:
    json_parse_error = "invalid JSON: {}".format(e)

if report is None:
    report = {}  # allow downstream checks to run and fail gracefully


# ---------------------------------------------------------------------------
# FR1: top-level fields
# ---------------------------------------------------------------------------

def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def check_fr1():
    if json_parse_error is not None:
        record("FR1", False, json_parse_error)
        return False

    reasons = []
    candidates = report.get("candidates", None)
    if not isinstance(candidates, list):
        reasons.append("'candidates' missing or not an array")

    overall_confidence = report.get("overall_confidence", None)
    if not is_number(overall_confidence):
        reasons.append("'overall_confidence' missing or not a number")
    elif not (0.0 <= float(overall_confidence) <= 1.0):
        reasons.append("'overall_confidence' out of range [0,1]")

    summary = report.get("summary", None)
    if not isinstance(summary, str) or len(summary.strip()) == 0:
        reasons.append("'summary' missing, not a string, or empty")

    if reasons:
        record("FR1", False, "; ".join(reasons))
        return False
    record("FR1", True)
    return True


fr1_ok = check_fr1()

candidates = report.get("candidates", [])
if not isinstance(candidates, list):
    candidates = []


# ---------------------------------------------------------------------------
# FR2: each candidate well-formed
# ---------------------------------------------------------------------------

def check_fr2():
    if len(candidates) == 0:
        record("FR2", False, "candidates array is empty; no candidates to validate")
        return False

    bad = []
    for idx, c in enumerate(candidates):
        if not isinstance(c, dict):
            bad.append("candidate[{}] is not an object".format(idx))
            continue
        sig = c.get("signal_or_line", None)
        conf = c.get("confidence", None)
        rat = c.get("rationale", None)
        if not isinstance(sig, str) or len(sig.strip()) == 0:
            bad.append("candidate[{}] missing/invalid 'signal_or_line'".format(idx))
        if not is_number(conf) or not (0.0 <= float(conf) <= 1.0):
            bad.append("candidate[{}] missing/invalid 'confidence' in [0,1]".format(idx))
        if not isinstance(rat, str) or len(rat) < 20:
            bad.append("candidate[{}] missing/invalid 'rationale' (need string len>=20)".format(idx))

    if bad:
        record("FR2", False, "; ".join(bad[:6]) + (" ..." if len(bad) > 6 else ""))
        return False
    record("FR2", True)
    return True


fr2_ok = check_fr2()


# ---------------------------------------------------------------------------
# Helper: build per-candidate combined text, and well-formed candidate list
# ---------------------------------------------------------------------------

def candidate_text(c):
    parts = []
    for key in ("signal_or_line", "rationale", "summary_note"):
        v = c.get(key) if isinstance(c, dict) else None
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts).lower()


def candidate_confidence(c):
    conf = c.get("confidence") if isinstance(c, dict) else None
    if is_number(conf):
        return float(conf)
    return -1.0


well_formed_candidates = [c for c in candidates if isinstance(c, dict)]


# ---------------------------------------------------------------------------
# Pattern helpers for opcode/operand trigger condition (FR3 / SR1)
# ---------------------------------------------------------------------------

OPCODE_PATTERNS = [
    r"2'b10",
    r"\bopcode\s*==\s*2\b",
    r"\bopcode\s*=\s*2\b",
    r"\bopcode\s*==\s*['\"]?10['\"]?\b",
    r"\band\b",  # opcode=10 is the AND operation
    r"\bopcode\s*=\s*['\"]?10['\"]?\b",
    r"0x2\b",
]

OPERAND_A_PATTERNS = [
    r"0x5a\b",
    r"8'h5a\b",
    r"\b5a\b",
    r"\b90\b",
]

OPERAND_B_PATTERNS = [
    r"0xa5\b",
    r"8'ha5\b",
    r"\ba5\b",
    r"\b165\b",
]


def any_match(patterns, text):
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def matches_trigger_condition(text):
    """True if text co-mentions opcode trigger reference AND both operand values."""
    if not text:
        return False
    has_opcode = any_match(OPCODE_PATTERNS, text)
    has_a = any_match(OPERAND_A_PATTERNS, text)
    has_b = any_match(OPERAND_B_PATTERNS, text)
    return has_opcode and has_a and has_b


# ---------------------------------------------------------------------------
# FR3: trigger condition co-mention in some candidate
# ---------------------------------------------------------------------------

def check_fr3():
    for c in well_formed_candidates:
        text = candidate_text(c)
        if matches_trigger_condition(text):
            record("FR3", True)
            return True
    record(
        "FR3",
        False,
        "no candidate rationale/signal_or_line co-mentions the opcode trigger "
        "(2'b10/AND/opcode==2) together with both operand values (0x5a and 0xa5, "
        "in hex or decimal form)",
    )
    return False


fr3_ok = check_fr3()


# ---------------------------------------------------------------------------
# FR4: distinct result-corruption role (specific mechanism) and
# mismatch-masking role
# ---------------------------------------------------------------------------

# Specific, mechanism-naming language for the result-corruption role. Vague
# "suspicious module"/"may produce an incorrect result" phrasing without
# naming a concrete construct (architectural_result, a bit index, a mux,
# or an explicit flip/xor/toggle mechanism) must NOT satisfy this role.
RESULT_CORRUPTION_SPECIFIC_PATTERNS = [
    r"architectural_result",
    r"\bres_mux\b",
    r"\bresult[_\s]?mux\b",
    r"\bbit\s*\[?3\]?\b",
    r"\[3\]",
    r"\bxor\b.{0,60}(result|bit|corrupt|flip|toggle)",
    r"(result|bit|value).{0,40}(flip|corrupt|xor|toggle|invert)",
    r"(flip|corrupt|xor|toggle|invert).{0,40}(result|bit|value)",
    r"\bmux\b.{0,60}(result|corrupt|flip|toggle|before.{0,20}register)",
]

MISMATCH_MASK_PATTERNS = [
    r"mismatch_mask",
    r"\bmismatch\b.{0,60}(mask|force|forced|forcing|suppress|hidden|hide|gate|gated|zero|false)",
    r"(mask|force|forced|forcing|suppress|hidden|hide|gate|gated).{0,60}\bmismatch\b",
    r"checker.{0,40}(compromis|defeat|bypass|forged|fooled)",
]


def matches_fr4_result_role(text):
    return any_match(RESULT_CORRUPTION_SPECIFIC_PATTERNS, text)


def matches_fr4_mask_role(text):
    return any_match(MISMATCH_MASK_PATTERNS, text)


def check_fr4():
    result_role = False
    mask_role = False
    for c in well_formed_candidates:
        text = candidate_text(c)
        if matches_fr4_result_role(text):
            result_role = True
        if matches_fr4_mask_role(text):
            mask_role = True

    if result_role and mask_role:
        record("FR4", True)
        return True

    missing = []
    if not result_role:
        missing.append(
            "no candidate names a specific result-corruption mechanism "
            "(architectural_result / bit-index / mux / xor-flip language); "
            "vague 'suspicious module' or 'may be incorrect' claims do not qualify"
        )
    if not mask_role:
        missing.append("no candidate identifies a mismatch-masking/checker-forcing construct")
    record("FR4", False, "; ".join(missing))
    return False


fr4_ok = check_fr4()


# ---------------------------------------------------------------------------
# SR1: exact trigger condition identified
# ---------------------------------------------------------------------------

def check_sr1():
    for c in well_formed_candidates:
        text = candidate_text(c)
        if matches_trigger_condition(text):
            record("SR1", True)
            return True
    record(
        "SR1",
        False,
        "no candidate specifies the exact trigger condition (opcode=2'b10/AND AND "
        "operand_a=0x5a AND operand_b=0xa5); vague 'rare input' claims do not satisfy SR1",
    )
    return False


sr1_ok = check_sr1()


# ---------------------------------------------------------------------------
# SR2: bit-3 corruption identified
# ---------------------------------------------------------------------------

BIT3_PATTERNS = [
    r"\bbit\s*3\b",
    r"\[3\]",
    r"architectural_result\s*\[\s*3\s*\]",
]

CORRUPTION_LANG_PATTERNS = [
    r"flip",
    r"xor",
    r"corrupt",
    r"toggle",
    r"invert",
    r"tamper",
]


def matches_sr2(text):
    if not text:
        return False
    has_bit3 = any_match(BIT3_PATTERNS, text)
    has_corrupt_lang = any_match(CORRUPTION_LANG_PATTERNS, text)
    return has_bit3 and has_corrupt_lang


def check_sr2():
    for c in well_formed_candidates:
        text = candidate_text(c)
        if matches_sr2(text):
            record("SR2", True)
            return True
    record(
        "SR2",
        False,
        "no candidate identifies bit-position-3 corruption of architectural_result "
        "(need bit-index reference co-located with flip/xor/corrupt language)",
    )
    return False


sr2_ok = check_sr2()


# ---------------------------------------------------------------------------
# SR3: mismatch masking/forcing to false-negative with sufficient confidence
#
# Require affirmative forcing/masking/suppression verb usage (not
# mere co-occurrence of "mismatch" with weakly-related terms), and
# explicitly exclude candidates whose rationale is exculpatory/neutral
# (e.g. "legitimate", "behaves as expected", "no evidence of forcing").
# ---------------------------------------------------------------------------

MISMATCH_WORD_PATTERN = r"\bmismatch\b"

# Affirmative forcing/masking/suppression language. Each pattern requires an
# actual verb/phrase asserting that the mismatch signal is being forced,
# masked, suppressed, hidden, or gated -- not just a nearby generic word.
AFFIRMATIVE_MASK_LANG_PATTERNS = [
    r"forced?\s+to\s+0",
    r"forced?\s+low",
    r"forc(e|ed|ing)\s+(the\s+)?mismatch",
    r"mismatch.{0,30}\bforc(e|ed|ing)\b",
    r"mask(ed|ing)?\s+(the\s+)?mismatch",
    r"mismatch.{0,30}\bmask(ed|ing)?\b",
    r"suppress(ed|ing)?\s+(the\s+)?mismatch",
    r"mismatch.{0,30}\bsuppress(ed|ing)?\b",
    r"hid(e|den|ing)\s+from",
    r"hide[sd]?\s+(the\s+)?(corruption|error|disagreement|mismatch)",
    r"gate[sd]?\s+(off|to\s+0)",
    r"gated\s+(off\s+)?despite\s+disagreement",
    r"false[- ]negative",
    r"forg(e|ing|ed)\b",
]

# Exculpatory / neutral language that, if present without any affirmative
# forcing/masking assertion, must NOT satisfy SR3 even though "mismatch"
# is mentioned nearby.
EXCULPATORY_PATTERNS = [
    r"legitimate",
    r"behaves?\s+as\s+expected",
    r"no\s+evidence\s+of\s+(forcing|masking|suppress)",
    r"appears?\s+correct",
    r"functions?\s+correctly",
    r"working\s+as\s+intended",
]


def matches_sr3(text):
    if not text:
        return False
    if not re.search(MISMATCH_WORD_PATTERN, text, re.IGNORECASE):
        return False
    has_affirmative = any_match(AFFIRMATIVE_MASK_LANG_PATTERNS, text)
    if not has_affirmative:
        return False
    # If the rationale simultaneously reads as exculpatory (e.g. rewritten
    # to describe the comparator as legitimate/behaving as expected) and
    # contains no genuinely affirmative masking assertion beyond generic
    # co-occurrence, we already required has_affirmative above; but guard
    # against the case where an affirmative-looking match is entirely
    # embedded within a negation such as "no evidence of forcing" by
    # checking that an exculpatory phrase does not directly negate the
    # matched affirmative language.
    if re.search(r"no\s+evidence\s+of\s+(forcing|masking|suppress\w*|hiding)", text, re.IGNORECASE):
        return False
    return True


def check_sr3():
    for c in well_formed_candidates:
        text = candidate_text(c)
        conf = candidate_confidence(c)
        if conf >= 0.5 and matches_sr3(text):
            record("SR3", True)
            return True
    record(
        "SR3",
        False,
        "no candidate with confidence>=0.5 affirmatively asserts that the mismatch "
        "signal is being forced/masked/suppressed/hidden (integrity checker "
        "compromise); candidates that merely mention 'mismatch' alongside neutral "
        "or exculpatory language ('legitimate', 'behaves as expected', 'no evidence "
        "of forcing') do not satisfy this requirement",
    )
    return False


sr3_ok = check_sr3()


# ---------------------------------------------------------------------------
# SR4 (REVISED per repair notes): set/union-based ranking constraint.
#
# Instead of requiring a SINGLE top-2 candidate to combine the trigger
# pattern with either bit-3 corruption or mismatch masking in its own
# rationale text, we now allow these findings to be split across separate,
# individually high-confidence candidates. The check considers the top-N
# highest-confidence candidates as a set (N = max(2, count of candidates
# with confidence>=0.6, capped at 3)), and passes if, among the qualifying
# (confidence>=0.6) members of that top-N set:
#   (a) at least one satisfies the SR1 trigger-condition pattern, AND
#   (b) at least one (possibly a different candidate) satisfies the SR2
#       bit-3-corruption pattern OR the SR3 mismatch-masking pattern.
# This still penalizes genuinely buried or low-confidence correct findings:
# if the qualifying candidates only exist below confidence 0.6, or fall
# outside the computed top-N window, SR4 fails.
# ---------------------------------------------------------------------------

def check_sr4():
    if len(well_formed_candidates) == 0:
        record("SR4", False, "no candidates present to rank")
        return False

    sorted_candidates = sorted(
        well_formed_candidates, key=lambda c: candidate_confidence(c), reverse=True
    )

    high_conf_count = sum(1 for c in sorted_candidates if candidate_confidence(c) >= 0.6)
    n = max(2, high_conf_count)
    n = min(n, 3)
    n = min(n, len(sorted_candidates))

    top_n = sorted_candidates[:n]

    has_trigger_qualifier = False
    has_payload_qualifier = False

    for c in top_n:
        conf = candidate_confidence(c)
        if conf < 0.6:
            continue
        text = candidate_text(c)
        if matches_trigger_condition(text):
            has_trigger_qualifier = True
        if matches_sr2(text) or matches_sr3(text):
            has_payload_qualifier = True

    if has_trigger_qualifier and has_payload_qualifier:
        record("SR4", True)
        return True

    missing = []
    if not has_trigger_qualifier:
        missing.append(
            "no candidate within the top-{} highest-confidence entries (confidence>=0.6) "
            "identifies the exact trigger condition".format(n)
        )
    if not has_payload_qualifier:
        missing.append(
            "no candidate within the top-{} highest-confidence entries (confidence>=0.6) "
            "identifies bit-3 corruption or mismatch masking".format(n)
        )
    record(
        "SR4",
        False,
        "; ".join(missing) + " (trigger and payload findings may be reported as "
        "separate high-confidence candidates, but must not be buried below the "
        "top-ranked entries or reported only at confidence<0.6)",
    )
    return False


sr4_ok = check_sr4()


# ---------------------------------------------------------------------------
# SR5: baseline empty/naive submission must fail overall.
#
# Independently detect the baseline-empty hallmark directly from the
# parsed JSON (candidates array empty AND overall_confidence == 0),
# decoupled from any other check's pass/fail state, so this check cannot
# pass by construction via other checks. If the hallmark is present,
# SR5 unconditionally FAILs. Otherwise SR5 passes (this instance is not the
# naive baseline under test).
# ---------------------------------------------------------------------------

def check_sr5():
    candidates_list = report.get("candidates", None)
    overall_conf = report.get("overall_confidence", None)

    is_empty_candidates = isinstance(candidates_list, list) and len(candidates_list) == 0
    is_zero_confidence = is_number(overall_conf) and float(overall_conf) == 0.0

    if is_empty_candidates and is_zero_confidence:
        record(
            "SR5",
            False,
            "submission exhibits the naive/empty baseline hallmark (empty candidates "
            "array and overall_confidence==0); such a submission must fail",
        )
        return False

    record("SR5", True)
    return True


sr5_ok = check_sr5()


# ---------------------------------------------------------------------------
# Metrics computation (informational; does not gate PASS/FAIL of [TEST] lines)
# ---------------------------------------------------------------------------

def compute_metrics():
    sr_flags = [sr1_ok, sr2_ok, sr3_ok, sr4_ok]
    detection_rate = sum(1 for f in sr_flags if f) / 4.0

    high_conf_candidates = [c for c in well_formed_candidates if candidate_confidence(c) >= 0.6]
    if high_conf_candidates:
        spurious = 0
        for c in high_conf_candidates:
            text = candidate_text(c)
            is_real = (
                matches_trigger_condition(text)
                or matches_sr2(text)
                or matches_sr3(text)
                or matches_fr4_result_role(text)
                or matches_fr4_mask_role(text)
            )
            if not is_real:
                spurious += 1
        false_positive_rate = spurious / float(len(high_conf_candidates))
    else:
        false_positive_rate = 0.0

    localization_count = sum(1 for f in (sr1_ok, sr2_ok, sr3_ok) if f)
    if localization_count == 3:
        trigger_payload_localization = 1.0
    elif localization_count == 2:
        trigger_payload_localization = 0.66
    elif localization_count == 1:
        trigger_payload_localization = 0.33
    else:
        trigger_payload_localization = 0.0

    confidence_calibration = 1.0 if sr4_ok else 0.0

    metrics = {
        "detection_rate": round(detection_rate, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "trigger_payload_localization": round(trigger_payload_localization, 4),
        "confidence_calibration": round(confidence_calibration, 4),
    }
    print("[METRICS] {}".format(json.dumps(metrics)))


compute_metrics()


# ---------------------------------------------------------------------------
# Optional informational corroboration: simulate lockstep_alu.v via iverilog
# to confirm the ground-truth trigger is present in the shipped RTL. This is
# purely evidence printed to stdout; it never affects PASS/FAIL verdicts
# because this domain grades the submitted answer file, not the RTL itself.
# A missing design file here is not fatal to grading (the FR/SR checks above
# already fully determine pass/fail), so we only warn.
# ---------------------------------------------------------------------------

def run_optional_simulation():
    if not os.path.isfile(LOCKSTEP_ALU_PATH):
        print("[INFO] optional corroboration skipped: inputs/lockstep_alu.v not found")
        return
    if not os.path.isfile(TB_PATH):
        print("[INFO] optional corroboration skipped: evaluation/tb_trigger_check.v not found")
        return

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sim_bin = os.path.join(tmpdir, "sim.vvp")
            compile_cmd = [
                "iverilog",
                "-g2012",
                "-o",
                sim_bin,
                LOCKSTEP_ALU_PATH,
                TB_PATH,
            ]
            comp = subprocess.run(
                compile_cmd, capture_output=True, text=True, timeout=30
            )
            if comp.returncode != 0:
                print(
                    "[INFO] optional corroboration: iverilog compile failed (non-fatal): {}".format(
                        comp.stderr.strip()[:500]
                    )
                )
                return

            run = subprocess.run(
                ["vvp", sim_bin], capture_output=True, text=True, timeout=30
            )
            print("[INFO] optional corroboration simulation output:")
            for line in run.stdout.strip().splitlines():
                print("[INFO]   {}".format(line))
    except FileNotFoundError:
        print("[INFO] optional corroboration skipped: iverilog/vvp not available on this system")
    except subprocess.TimeoutExpired:
        print("[INFO] optional corroboration skipped: simulation timed out")
    except Exception as e:
        print("[INFO] optional corroboration skipped: {}".format(e))


run_optional_simulation()


# ---------------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------------

all_pass = all(ok for (_, ok, _) in results)

if all_pass:
    print("[RESULT] ALL REQUIREMENTS PASSED")
    sys.exit(0)
else:
    failed_ids = [rid for (rid, ok, _) in results if not ok]
    print("[RESULT] FAILED REQUIREMENTS: {}".format(", ".join(failed_ids)))
    sys.exit(1)