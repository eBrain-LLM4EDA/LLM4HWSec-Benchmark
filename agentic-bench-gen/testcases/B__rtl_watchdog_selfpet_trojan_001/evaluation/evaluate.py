#!/usr/bin/env python3
"""evaluate.py — RTL Trojan Detection grader for rtl_watchdog_selfpet_trojan_001.

Grades submission/trojan_report.json against the public functional
requirements (FR1-FR4) and the hidden security requirements (SR1-SR3),
using inputs/wdt_top.v, inputs/design_brief.md, inputs/register_map.md as
read-only reference material. Optional iverilog/vvp cross-check is used as
corroborating evidence for SR1 only; grading verdicts are decided on the
submitted report content.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUT_FILES = ["wdt_top.v", "design_brief.md", "register_map.md"]
SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

results = []  # list of (req_id, passed_bool, reason_or_None)


def record(req_id, passed, reason=None):
    results.append((req_id, passed, reason))
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))


def fail_setup(msg):
    print("[TEST] FAIL: SETUP: %s" % msg)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Load input artifacts (reference only)
# ---------------------------------------------------------------------------

for fname in INPUT_FILES:
    path = os.path.join("inputs", fname)
    if not os.path.isfile(path):
        fail_setup("%s not found" % path)

WDT_TOP_PATH = os.path.join("inputs", "wdt_top.v")

with open(WDT_TOP_PATH, "r", encoding="utf-8") as f:
    WDT_TOP_SRC = f.read()


def derive_true_magic_constant(rtl_src):
    """Structurally derive the true magic data constant that, combined with
    addr==8'h0C, triggers the internal reload path, by scanning the RTL
    text for a wire/expression that ANDs a we-qualified addr==0x0C compare
    with a wdata==32'h... compare. Falls back to a looser scan if the
    tightly-coupled pattern is not found verbatim."""
    # Find all 32'h.... hex literals that appear textually near an "0C"
    # (case-insensitive) address literal within the same statement/wire
    # declaration. This ties the derived constant to the actual RTL rather
    # than hardcoding it independently of the input artifact.
    candidates = []
    for m in re.finditer(r'wire\s+\S+\s*=\s*([^;]+);', rtl_src):
        expr = m.group(1)
        if re.search(r"8'h0c\b", expr, re.IGNORECASE) or re.search(r"addr\s*==\s*ADDR_CFG", expr, re.IGNORECASE):
            for hm in re.finditer(r"32'h([0-9a-fA-F]{8})", expr):
                candidates.append(int(hm.group(1), 16))
    if candidates:
        # Prefer a candidate that is not the documented pet magic value.
        pet_like = 0xA5A5A5A5
        non_pet = [c for c in candidates if c != pet_like]
        return non_pet[0] if non_pet else candidates[0]

    # Fallback: broader window-based scan for "0C" and 32'h... within
    # ~200 chars of each other anywhere in the source.
    for am in re.finditer(r"(?:8'h0c|addr\s*==\s*8'h0c)", rtl_src, re.IGNORECASE):
        start = max(0, am.start() - 200)
        end = min(len(rtl_src), am.end() + 200)
        window = rtl_src[start:end]
        for hm in re.finditer(r"32'h([0-9a-fA-F]{8})", window):
            val = int(hm.group(1), 16)
            if val != 0xA5A5A5A5:
                return val

    return None


TRUE_MAGIC_CONST = derive_true_magic_constant(WDT_TOP_SRC)

# ---------------------------------------------------------------------------
# Load submission (FR1 owns parse-failure reporting; no SETUP for bad JSON)
# ---------------------------------------------------------------------------

if not os.path.isfile(SUBMISSION_PATH):
    fail_setup("%s not found" % SUBMISSION_PATH)

report = None
fr1_parse_error = None

try:
    with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()
    report = json.loads(raw_text)
    if not isinstance(report, dict):
        fr1_parse_error = "%s does not contain a top-level JSON object" % SUBMISSION_PATH
        report = None
except Exception as e:  # noqa: BLE001 - deliberately broad: any parse failure is an FR1 fact
    fr1_parse_error = "%s could not be parsed as JSON: %s" % (SUBMISSION_PATH, e)
    report = None

# Safe fallback so every requirement below can run without crashing/cascading.
safe_report = report if isinstance(report, dict) else {}


# ---------------------------------------------------------------------------
# Helper extraction functions
# ---------------------------------------------------------------------------

def _all_text_fields(finding):
    """Concatenate the textual fields of a finding for pattern scanning."""
    parts = []
    if not isinstance(finding, dict):
        return ""
    for key in ("signal_or_path", "location", "trigger_condition"):
        v = finding.get(key, "")
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


def extract_address_tokens(text):
    """Return a set of canonical address values (ints) mentioned in text.

    Recognizes forms like 0x0C, 0x0c, 8'h0C, WDT_CFG_ALIAS,
    WDT_CTRL, WDT_TIMEOUT, WDT_PET, and 'address 0x0C' style phrasing.
    """
    addrs = set()
    if not isinstance(text, str):
        return addrs

    # Named register aliases -> canonical addresses
    name_map = {
        r"WDT_CFG_ALIAS": 0x0C,
        r"WDT_CTRL": 0x00,
        r"WDT_TIMEOUT": 0x04,
        r"WDT_PET": 0x08,
    }
    for pattern, addr in name_map.items():
        if re.search(pattern, text, re.IGNORECASE):
            addrs.add(addr)

    # Hex tokens: 0x0C, 8'h0C, 'h0C, etc. (1-2 hex digits, address-scale)
    for m in re.finditer(r"(?:0x|8'h|'h)([0-9a-fA-F]{1,2})\b", text, re.IGNORECASE):
        try:
            addrs.add(int(m.group(1), 16))
        except ValueError:
            pass

    # bare "address 0x0C" / "address 12" style phrasing
    for m in re.finditer(r"address(?:es)?\s*(?:=|:|is|of)?\s*0?x?([0-9a-fA-F]{1,2})\b", text, re.IGNORECASE):
        token = m.group(1)
        try:
            addrs.add(int(token, 16))
        except ValueError:
            pass

    return addrs


def extract_data_tokens(text):
    """Return a set of canonical 32-bit data values (ints) mentioned in text."""
    data_vals = set()
    if not isinstance(text, str):
        return data_vals

    # 32'hDEADC0DE, 0xDEADC0DE, DEADC0DE (8 hex digit standalone), 32'hA5A5A5A5, 0xA5A5A5A5
    for m in re.finditer(r"(?:0x|32'h|'h)?([0-9a-fA-F]{8})\b", text):
        try:
            data_vals.add(int(m.group(1), 16))
        except ValueError:
            pass

    return data_vals


DEADC0DE = 0xDEADC0DE  # documented ground-truth expected value (also cross-checked structurally)
A5A5A5A5 = 0xA5A5A5A5
ADDR_CFG = 0x0C
ADDR_PET = 0x08
ADDR_CTRL = 0x00
ADDR_TIMEOUT = 0x04


def finding_has_trigger_pair(finding, expected_data_val=DEADC0DE):
    """True if this finding names addr 0x0C together with the given data value."""
    text = _all_text_fields(finding)
    addrs = extract_address_tokens(text)
    data = extract_data_tokens(text)
    return (ADDR_CFG in addrs) and (expected_data_val in data)


def finding_names_addr_cfg_with_any_data(finding):
    """True if finding names addr 0x0C together with SOME 32-bit-ish data
    token (regardless of whether it's the correct one). Used for FR2, which
    only checks presence/shape, not correctness (that's SR1's job)."""
    text = _all_text_fields(finding)
    addrs = extract_address_tokens(text)
    data = extract_data_tokens(text)
    return (ADDR_CFG in addrs) and (len(data) > 0)


def finding_describes_reload_effect(finding):
    """True if finding text describes a reload/pet-equivalent effect."""
    text = _all_text_fields(finding).lower()
    keywords = [
        "reload", "reset the counter", "resets the counter", "counter to 0",
        "counter to zero", "clears reset_req", "clear reset_req",
        "equivalent to pet", "pet-equivalent", "acts as a pet",
        "acts like a pet", "silently pet", "silent pet", "same as pet",
        "reload the counter", "reloads the counter", "reload path",
        "shadow", "bypass", "second pet", "hidden pet", "secret pet",
        "alternate pet", "int_pet", "petting", "pets the watchdog",
        "services the watchdog",
    ]
    return any(k in text for k in keywords)


def finding_claims_hidden_logic(finding, addr):
    """True if finding claims hidden/undocumented/trigger logic tied to addr,
    but the finding is NOT actually about the 0x0C/DEADC0DE trigger."""
    text = _all_text_fields(finding)
    addrs = extract_address_tokens(text)
    if addr not in addrs:
        return False
    # If this finding is really about the true trigger pair (it also
    # mentions 0x0C / DEADC0DE), it's substantiated -- don't count it
    # against the unrelated-register cap.
    data = extract_data_tokens(text)
    if (ADDR_CFG in addrs) or (DEADC0DE in data):
        return False
    lower = text.lower()
    claim_keywords = [
        "hidden", "undocumented", "trigger", "trojan", "malicious",
        "backdoor", "anomal", "suspicious", "covert", "unauthorized",
        "secret",
    ]
    return any(k in lower for k in claim_keywords)


def finding_flags_documented_pet_as_vuln(finding):
    """True if this finding singles out 0x08/A5A5A5A5 as itself the vuln,
    without also referencing the 0x0C/DEADC0DE anomalous path."""
    text = _all_text_fields(finding)
    addrs = extract_address_tokens(text)
    data = extract_data_tokens(text)
    mentions_pet_pair = (ADDR_PET in addrs) or (A5A5A5A5 in data)
    mentions_trigger = (ADDR_CFG in addrs) or (DEADC0DE in data)
    if not mentions_pet_pair or mentions_trigger:
        return False
    lower = text.lower()
    claim_keywords = [
        "hidden", "undocumented", "trigger", "trojan", "malicious",
        "backdoor", "anomal", "suspicious", "covert", "unauthorized",
        "vulnerab", "flaw", "bug", "defect",
    ]
    return any(k in lower for k in claim_keywords)


# ---------------------------------------------------------------------------
# FR1: structural schema check (also owns JSON parse-failure reporting)
# ---------------------------------------------------------------------------

def check_fr1():
    if fr1_parse_error is not None:
        return False, fr1_parse_error

    if "findings" not in report or "summary" not in report or "reset_req_reliable" not in report:
        return False, "missing one of top-level keys findings/summary/reset_req_reliable"

    findings = report["findings"]
    summary = report["summary"]
    reliable = report["reset_req_reliable"]

    if not isinstance(findings, list):
        return False, "'findings' is not a list"
    if not isinstance(summary, str):
        return False, "'summary' is not a string"
    if not isinstance(reliable, bool):
        return False, "'reset_req_reliable' is not a boolean"

    if len(findings) == 0:
        return False, "'findings' is empty"

    for i, finding in enumerate(findings):
        if not isinstance(finding, dict):
            return False, "findings[%d] is not an object" % i
        for key in ("signal_or_path", "location", "trigger_condition"):
            if key not in finding or not isinstance(finding[key], str):
                return False, "findings[%d] missing/mistyped string field '%s'" % (i, key)
        if "confidence" not in finding:
            return False, "findings[%d] missing 'confidence'" % i
        conf = finding["confidence"]
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            return False, "findings[%d].confidence is not a number" % i
        if not (0.0 <= float(conf) <= 1.0):
            return False, "findings[%d].confidence=%r is not within [0,1]" % (i, conf)

    return True, None


FR1_OK, FR1_REASON = check_fr1()
record("FR1", FR1_OK, FR1_REASON)


# ---------------------------------------------------------------------------
# FR4: severity field per finding
# ---------------------------------------------------------------------------

def check_fr4():
    if not FR1_OK:
        return False, "cannot validate severity fields: FR1 structural check failed (%s)" % FR1_REASON
    valid_severities = {"low", "medium", "high", "critical"}
    findings = safe_report.get("findings", [])
    for i, finding in enumerate(findings):
        sev = finding.get("severity", None) if isinstance(finding, dict) else None
        if not isinstance(sev, str) or sev.lower() not in valid_severities:
            return False, "findings[%d].severity=%r is missing or not one of low/medium/high/critical" % (i, sev)
    return True, None


FR4_OK, FR4_REASON = check_fr4()
record("FR4", FR4_OK, FR4_REASON)


# ---------------------------------------------------------------------------
# FR2: explicit trigger address+data pair (presence/shape only; correctness
#      of the exact data value is SR1's job), distinct from 0x08/A5A5A5A5
# ---------------------------------------------------------------------------

def check_fr2():
    if not FR1_OK:
        return False, "cannot validate trigger pair: FR1 structural check failed (%s)" % FR1_REASON
    findings = safe_report.get("findings", [])
    for finding in findings:
        if finding_names_addr_cfg_with_any_data(finding):
            return True, None
    return False, "no finding explicitly states address 0x0C together with an explicit 32-bit data value"


FR2_OK, FR2_REASON = check_fr2()
record("FR2", FR2_OK, FR2_REASON)


# ---------------------------------------------------------------------------
# FR3: reset_req_reliable == false, summary distinguishes documented pet
# ---------------------------------------------------------------------------

def check_fr3():
    if not FR1_OK:
        return False, "cannot validate reliability conclusion: FR1 structural check failed (%s)" % FR1_REASON

    reliable = safe_report.get("reset_req_reliable", None)
    if reliable is not False:
        return False, "'reset_req_reliable' is %r, expected false" % (reliable,)

    summary = safe_report.get("summary", "")
    if not isinstance(summary, str):
        return False, "'summary' is not a string"

    lower = summary.lower()

    mentions_doc_pet = (
        "a5a5a5a5" in lower or "0x08" in lower or "wdt_pet" in lower
    )
    if not mentions_doc_pet:
        return False, "summary does not mention the documented WDT_PET (0x08/A5A5A5A5) path"

    contrastive_keywords = [
        "unaffected", "unimpact", "not affected", "normal", "intact",
        "documented", "legitimate", "intended", "correctly", "as expected",
        "unrelated", "distinct", "separate", "unlike", "whereas", "however",
        "in contrast", "still works", "still functions", "continues to work",
        "continues to function", "remains reliable", "operates as documented",
    ]
    if not any(k in lower for k in contrastive_keywords):
        return False, "summary does not distinguish the documented pet path from the anomalous path"

    return True, None


FR3_OK, FR3_REASON = check_fr3()
record("FR3", FR3_OK, FR3_REASON)


# ---------------------------------------------------------------------------
# SR1: correct + specific trigger localization, checked against the true
#      magic constant derived structurally from inputs/wdt_top.v, with
#      optional simulation corroboration.
# ---------------------------------------------------------------------------

def run_simulation_corroboration(magic_val):
    """Best-effort iverilog/vvp cross-check with a given magic data value
    substituted for the injected write. Returns True if the simulation
    corroborates that this value defeats the watchdog (reset_req fails to
    assert at the expected timeout), False if reset_req still asserts
    normally (meaning this value is NOT the true trigger), or None if the
    toolchain is unavailable / simulation could not be run."""
    tb_path = os.path.join("evaluation", "tb_wdt_trojan_check.v")
    if not os.path.isfile(tb_path):
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        sim_bin = os.path.join(tmpdir, "sim.vvp")
        try:
            compile_proc = subprocess.run(
                ["iverilog", "-g2012", "-o", sim_bin, WDT_TOP_PATH, tb_path],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        if compile_proc.returncode != 0:
            return None

        try:
            run_proc = subprocess.run(
                ["vvp", sim_bin, "+MAGIC_VAL=%08X" % (magic_val & 0xFFFFFFFF)],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        output = run_proc.stdout or ""

    m1 = re.search(r"PROBE\s+reset_req_at_expected_timeout=(\d)", output)
    if not m1:
        return None

    expected_val = int(m1.group(1))
    # If the injected value truly defeats the watchdog, reset_req should NOT
    # be asserted at the originally expected timeout cycle.
    return expected_val == 0


def check_sr1():
    if not FR1_OK:
        return False, "cannot validate trigger localization: FR1 structural check failed (%s)" % FR1_REASON

    if TRUE_MAGIC_CONST is None:
        return False, "internal error: could not structurally derive the true magic constant from inputs/wdt_top.v"

    findings = safe_report.get("findings", [])

    # Findings that at least name addr 0x0C plus some 32-bit-ish data token.
    cfg_findings = [f for f in findings if finding_names_addr_cfg_with_any_data(f)]
    if not cfg_findings:
        return False, "no finding identifies address 0x0C together with an explicit data value as the trigger"

    # Among those, findings whose reported data value(s) include the TRUE
    # magic constant derived from the RTL.
    correct_value_findings = [f for f in cfg_findings if finding_has_trigger_pair(f, TRUE_MAGIC_CONST)]
    if not correct_value_findings:
        reported_vals = set()
        for f in cfg_findings:
            reported_vals |= extract_data_tokens(_all_text_fields(f))
        return False, (
            "finding(s) name address 0x0C but the reported data value(s) %s do not match the true "
            "magic constant 0x%08X present in inputs/wdt_top.v"
            % (", ".join("0x%08X" % v for v in sorted(reported_vals)) or "<none>", TRUE_MAGIC_CONST)
        )

    described = [f for f in correct_value_findings if finding_describes_reload_effect(f)]
    if not described:
        return False, (
            "finding(s) correctly identify address 0x0C + the true magic data value but do not describe "
            "the counter-reload / pet-equivalent effect (only a generic address mention)"
        )

    # Optional corroboration via simulation using the reported (correct)
    # value; does not override report-based judgment but reinforces it.
    sim_result = run_simulation_corroboration(TRUE_MAGIC_CONST)
    if sim_result is False:
        return False, (
            "simulation cross-check of inputs/wdt_top.v did not corroborate the reported trigger: "
            "reset_req still asserted at the expected timeout after injecting the reported value"
        )

    return True, None


SR1_OK, SR1_REASON = check_sr1()
record("SR1", SR1_OK, SR1_REASON)


# ---------------------------------------------------------------------------
# SR2: reset_req_reliable==false AND no finding mischaracterizes the
#      documented WDT_PET path itself as the vulnerability.
# ---------------------------------------------------------------------------

def check_sr2():
    if not FR1_OK:
        return False, "cannot validate SR2: FR1 structural check failed (%s)" % FR1_REASON

    reliable = safe_report.get("reset_req_reliable", None)
    if reliable is not False:
        return False, "'reset_req_reliable' is %r, expected false" % (reliable,)

    findings = safe_report.get("findings", [])
    for i, finding in enumerate(findings):
        if finding_flags_documented_pet_as_vuln(finding):
            return False, ("findings[%d] flags the documented WDT_PET (0x08/A5A5A5A5) path itself as "
                            "anomalous/trojan without referencing the separate 0x0C/DEADC0DE trigger" % i)

    return True, None


SR2_OK, SR2_REASON = check_sr2()
record("SR2", SR2_OK, SR2_REASON)


# ---------------------------------------------------------------------------
# SR3: scan ALL findings for any that claim hidden/undocumented/trigger
#      logic on WDT_CTRL(0x00) or WDT_TIMEOUT(0x04), describing documented
#      behavior (two-step disable-toggle, normal timeout compare) as
#      anomalous. Any single such mischaracterizing finding, or more than
#      one unsubstantiated finding overall, fails SR3.
# ---------------------------------------------------------------------------

DOCUMENTED_BEHAVIOR_PHRASES = [
    "disable-toggle", "disable toggle", "two-step disable", "two step disable",
    "bit 1", "bit1", "toggle sequence", "timeout compare", "compare against",
    "counter == timeout", "counter==timeout", "reaches the programmed timeout",
    "reaches timeout", "compares the counter", "prescaled ticks", "programmed timeout",
]

CLAIM_KEYWORDS = [
    "hidden", "undocumented", "trigger", "trojan", "malicious",
    "backdoor", "anomal", "suspicious", "covert", "unauthorized",
    "secret",
]


def finding_mischaracterizes_documented_behavior(finding, addr):
    """True if finding ties `addr` to a hidden/trigger-type claim while
    describing behavior that matches the documented, normal operation of
    that register (disable-toggle sequence or timeout compare), and the
    finding is not actually about the true 0x0C/magic-value trigger."""
    text = _all_text_fields(finding)
    addrs = extract_address_tokens(text)
    if addr not in addrs:
        return False

    # Don't count findings that are really about the true trigger pair.
    data = extract_data_tokens(text)
    if (ADDR_CFG in addrs) or (TRUE_MAGIC_CONST is not None and TRUE_MAGIC_CONST in data):
        return False

    lower = text.lower()
    has_claim = any(k in lower for k in CLAIM_KEYWORDS)
    describes_documented = any(p in lower for p in DOCUMENTED_BEHAVIOR_PHRASES)

    if has_claim and describes_documented:
        return True

    # Even without an explicit documented-behavior phrase, a bare claim
    # keyword tied to WDT_CTRL/WDT_TIMEOUT (with no 0x0C/magic reference)
    # is itself an unsubstantiated finding on a documented register.
    return has_claim


def check_sr3():
    if not FR1_OK:
        return False, "cannot validate SR3: FR1 structural check failed (%s)" % FR1_REASON

    findings = safe_report.get("findings", [])
    unsubstantiated_count = 0
    mischaracterizing_indices = []
    offending_indices = []

    for i, finding in enumerate(findings):
        mischar_ctrl = finding_mischaracterizes_documented_behavior(finding, ADDR_CTRL)
        mischar_timeout = finding_mischaracterizes_documented_behavior(finding, ADDR_TIMEOUT)
        flagged_ctrl = finding_claims_hidden_logic(finding, ADDR_CTRL)
        flagged_timeout = finding_claims_hidden_logic(finding, ADDR_TIMEOUT)

        if mischar_ctrl or mischar_timeout:
            mischaracterizing_indices.append(i)

        if flagged_ctrl or flagged_timeout or mischar_ctrl or mischar_timeout:
            unsubstantiated_count += 1
            offending_indices.append(i)

    if mischaracterizing_indices:
        return False, (
            "findings %r mischaracterize documented WDT_CTRL/WDT_TIMEOUT behavior (e.g. the two-step "
            "disable-toggle sequence or normal timeout compare) as a hidden/undocumented trigger"
            % mischaracterizing_indices
        )

    if unsubstantiated_count > 1:
        return False, (
            "%d findings claim hidden/undocumented trigger logic in WDT_CTRL(0x00) or WDT_TIMEOUT(0x04) "
            "(indices %r); at most one such unsubstantiated finding is tolerated"
            % (unsubstantiated_count, offending_indices)
        )

    return True, None


SR3_OK, SR3_REASON = check_sr3()
record("SR3", SR3_OK, SR3_REASON)


# ---------------------------------------------------------------------------
# Final verdict
# ---------------------------------------------------------------------------

all_passed = all(passed for (_, passed, _) in results)
sys.exit(0 if all_passed else 1)