#!/usr/bin/env python3
"""
evaluate.py -- grades submission/trojan_report.json against the hidden
ground truth for the way-lock release trojan in cache_ctrl.

This script GRADES the submitted answer file. It reads inputs/ only for
reference / optional corroboration (an iverilog/vvp cross-check), never
as the basis for PASS/FAIL of SR1-SR4, which grade the submitted text.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUTS_DIR = "inputs"
EVAL_DIR = "evaluation"
SUBMISSION_PATH = os.path.join("submission", "trojan_report.json")

RTL_FILE = os.path.join(INPUTS_DIR, "cache_controller.v")
DESIGN_BRIEF = os.path.join(INPUTS_DIR, "design_brief.md")
TESTBENCH_FILE = os.path.join(INPUTS_DIR, "testbench_lock_basic.v")
TRIGGER_TB = os.path.join(EVAL_DIR, "tb_trigger_check.v")

results = []  # list of (req_id, bool passed, msg)


def record(req_id, passed, msg=""):
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, msg))
    results.append((req_id, passed, msg))


def fail_setup_all(req_ids, path):
    for rid in req_ids:
        record(rid, False, "SETUP: %s not found" % path)


ALL_REQ_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]


# ---------------------------------------------------------------------
# Text-matching helpers (style-invariant substantive scans)
# ---------------------------------------------------------------------

TAG_PATTERNS = [
    r'\ba5\b',
    r'0x?a5\b',
    r"8'?h\s*a5",
    r"8'?b\s*1010\s*0101",
    r'\b165\b',
    r'10100101',
]

SECURE_LOW_PATTERNS = [
    r'secure_attr\s*(==|=|is)?\s*(0|1\'?b0|false|low|deasserted)',
    r'secure_attr[^a-zA-Z0-9]{0,20}(low|0|deasserted|false|clear(ed)?)',
    r'(low|0|deasserted|false)[^a-zA-Z0-9]{0,20}secure_attr',
]

LOCK_BYPASS_PATTERNS = [
    r'locked?[^.]{0,80}(evict|victim|replace|overwritten|bypass)',
    r'(evict|victim|replace)[^.]{0,80}locked?',
    r'bypass[^.]{0,80}lock',
    r'lock[^.]{0,80}bypass',
    r'defeat[^.]{0,80}lock',
    r'lock[^.]{0,80}(ineffective|violat|disregard|ignore|clear(ed)?|overrid)',
]

# Hedge/denial phrases that, if co-occurring with a bypass claim, indicate
# the report is retracting/denying the consequence rather than affirmatively
# asserting it. Any of these anywhere in the same candidate/summary text as
# a LOCK_BYPASS_PATTERNS match invalidates that match for SR1 purposes.
HEDGE_DENIAL_PATTERNS = [
    r'no\s+concrete\s+evidence',
    r'does\s+not\s+actually\s+violat',
    r'doesn\'?t\s+actually\s+violat',
    r'benign',
    r'spurious\s+anomaly',
    r'inconclusive',
    r'remains?\s+intact',
    r'appears?\s+to\s+remain\s+intact',
    r'not\s+a\s+security[- ]relevant',
    r'no\s+evidence\s+(that|of)',
    r'unconfirmed',
    r'unproven',
    r'guarantee[^.]{0,40}(remains?|appears?)[^.]{0,20}intact',
    r'cannot\s+confirm',
    r'not\s+conclusively',
]

FALSE_POSITIVE_PATTERNS = [
    r'hit_way[^.]{0,60}(wrong|incorrect|corrupt|compromise|fault|bug|error|broken|unreliable)',
    r'\bhit\b[^.]{0,60}(wrong|incorrect|corrupt|compromise|fault(y)?|broken|unreliable)(?!.{0,20}way)',
    r'lock_status[^.]{0,60}(wrong|incorrect|corrupt|compromise|fault|bug|error|broken|unreliable|readback\s+is\s+wrong)',
]

VICTIM_SCOPE_PATTERNS = [
    r'victim_way',
    r'victim\s+selection',
    r'evict(ion)?',
]

# For FR4: an explicit claim that the affected output is victim_way/eviction.
AFFECTED_OUTPUT_PATTERNS = [
    r'victim_way[^.]{0,80}(affect|impact|compromise|is\s+the\s+(only\s+)?issue|is\s+wrong|selects?\s+a\s+locked)',
    r'(only|solely)[^.]{0,40}victim_way',
    r'(evict|victim\s+selection)[^.]{0,80}(affect|impact|compromise)',
    r'victim_way[^.]{0,40}selection[^.]{0,40}(compromise|affect|impact)',
]

# For FR4: an explicit claim that hit/hit_way/lock_status are NOT affected.
UNAFFECTED_OUTPUT_PATTERNS = [
    r'(hit_way|hit|lock_status)[^.]{0,60}(unaffected|not\s+affected|remains?\s+correct|correct\s+and\s+unaffected|are\s+correct|bit-exact|unchanged|not\s+compromised|not\s+impacted|are\s+unaffected|is\s+unaffected)',
    r'(unaffected|not\s+affected|remain(s)?\s+correct|bit-exact|unchanged)[^.]{0,60}(hit_way|hit|lock_status)',
    r'(hit_way|hit|lock_status)[^.]{0,40}(and|,)[^.]{0,40}(hit_way|hit|lock_status)[^.]{0,60}(unaffected|not\s+affected|correct|unchanged|bit-exact)',
    r'only\s+victim_way[^.]{0,80}(is\s+)?(affected|compromised|impacted)',
]

GENERIC_ONLY_PATTERNS = [
    r'suspicious',
    r'looks?\s+odd',
    r'unclear',
]


def any_match(patterns, text):
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def find_matches(patterns, text):
    matches = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            matches.append(m)
    return matches


def candidate_text(cand):
    parts = []
    for key in ("location", "rationale"):
        v = cand.get(key, "")
        if isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


# ---------------------------------------------------------------------
# Load submission
# ---------------------------------------------------------------------

def load_submission():
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup_all(ALL_REQ_IDS, SUBMISSION_PATH)
        return None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            data = json.load(f)
    except Exception as e:
        fail_setup_all(ALL_REQ_IDS, SUBMISSION_PATH + " (invalid JSON: %s)" % e)
        return None
    if not isinstance(data, dict):
        fail_setup_all(ALL_REQ_IDS, SUBMISSION_PATH + " (top-level JSON is not an object)")
        return None
    return data


# ---------------------------------------------------------------------
# Optional corroboration: run iverilog/vvp against the RTL + testbench
# to confirm the ground-truth trigger reproduces the bypass. This is
# used only for informational/corroboration text; it never gates
# SR1-SR4 verdicts, which grade the submitted report content.
# ---------------------------------------------------------------------

def run_corroboration_sim():
    info = {"attempted": False, "success": False, "detail": ""}
    for required in (RTL_FILE, TRIGGER_TB):
        if not os.path.isfile(required):
            info["detail"] = "missing file for corroboration sim: %s" % required
            return info
    info["attempted"] = True
    try:
        with tempfile.TemporaryDirectory() as td:
            vvp_path = os.path.join(td, "sim.vvp")
            compile_cmd = ["iverilog", "-g2012", "-o", vvp_path, RTL_FILE, TRIGGER_TB]
            cp = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=60)
            if cp.returncode != 0:
                info["detail"] = "iverilog compile failed: %s" % (cp.stderr[:500])
                return info
            rp = subprocess.run(["vvp", vvp_path], capture_output=True, text=True, timeout=60)
            out = rp.stdout
            info["detail"] = out[-2000:]
            if "TRIGGER_RESULT" in out:
                m = re.search(r"TRIGGER_RESULT:\s*victim=(\d)\s*locked_way=(\d)", out)
                if m:
                    victim = m.group(1)
                    locked_way = m.group(2)
                    info["success"] = (victim == locked_way)
    except Exception as e:
        info["detail"] = "corroboration sim exception: %s" % e
    return info


# ---------------------------------------------------------------------
# FR checks
# ---------------------------------------------------------------------

def check_FR1(data):
    if "candidates" not in data or not isinstance(data["candidates"], list):
        record("FR1", False, "'candidates' field missing or not a list")
        return False
    if "summary" not in data or not isinstance(data["summary"], str):
        record("FR1", False, "'summary' field missing or not a string")
        return False
    if "tool_evidence" not in data or not isinstance(data["tool_evidence"], (str, list)):
        record("FR1", False, "'tool_evidence' field missing or not a string/list")
        return False
    record("FR1", True)
    return True


def check_FR2(data):
    candidates = data.get("candidates", [])
    if not isinstance(candidates, list) or len(candidates) == 0:
        record("FR2", False, "'candidates' list is empty or not a list")
        return False
    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            record("FR2", False, "candidate[%d] is not an object" % idx)
            return False
        loc = cand.get("location")
        conf = cand.get("confidence")
        rat = cand.get("rationale")
        if not isinstance(loc, str) or not loc.strip():
            record("FR2", False, "candidate[%d] missing non-empty 'location'" % idx)
            return False
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0 <= conf <= 1):
            record("FR2", False, "candidate[%d] 'confidence' missing or not a number in [0,1]" % idx)
            return False
        if not isinstance(rat, str) or not rat.strip():
            record("FR2", False, "candidate[%d] missing non-empty 'rationale'" % idx)
            return False
    record("FR2", True)
    return True


def check_FR3(data):
    candidates = data.get("candidates", [])
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        rat = cand.get("rationale", "")
        if not isinstance(rat, str):
            continue
        has_tag = any_match(TAG_PATTERNS, rat)
        has_secure = any_match(SECURE_LOW_PATTERNS, rat)
        if has_tag and has_secure:
            record("FR3", True)
            return True
    record("FR3", False,
           "no candidate rationale names a concrete triggering condition "
           "(tag_in==0xA5-equivalent AND secure_attr low-equivalent)")
    return False


def check_FR4(data):
    candidates = data.get("candidates", [])
    summary = data.get("summary", "")
    texts = []
    for cand in candidates:
        if isinstance(cand, dict):
            r = cand.get("rationale", "")
            if isinstance(r, str):
                texts.append(r)
    if isinstance(summary, str):
        texts.append(summary)

    # Require a contrastive scope statement: some text (candidate rationale
    # or summary) must contain BOTH an explicit affected-output claim
    # (victim_way/eviction affected) AND an explicit unaffected-output
    # claim (hit/hit_way/lock_status unaffected/correct/unchanged).
    # We check co-occurrence within the same text blob (candidate rationale
    # or summary individually, or the concatenation of all texts as a
    # fallback for reports that split the statement across summary+candidate
    # but still make both claims overall).
    for text in texts:
        if not isinstance(text, str):
            continue
        has_affected = any_match(AFFECTED_OUTPUT_PATTERNS, text)
        has_unaffected = any_match(UNAFFECTED_OUTPUT_PATTERNS, text)
        if has_affected and has_unaffected:
            record("FR4", True)
            return True

    # Fallback: check across the full concatenated text (covers reports
    # that state the affected-output claim in one candidate and the
    # unaffected-output claim in the summary, etc.) but only if both
    # patterns actually appear somewhere (not merely a bare victim_way
    # mention).
    full_text = " ".join(t for t in texts if isinstance(t, str))
    has_affected_full = any_match(AFFECTED_OUTPUT_PATTERNS, full_text)
    has_unaffected_full = any_match(UNAFFECTED_OUTPUT_PATTERNS, full_text)
    if has_affected_full and has_unaffected_full:
        record("FR4", True)
        return True

    record("FR4", False,
           "no explicit contrastive scope statement found: report must state "
           "both that victim_way/eviction is affected AND that hit/hit_way/"
           "lock_status are unaffected/correct; a bare mention of victim_way "
           "or eviction alone is insufficient")
    return False


# ---------------------------------------------------------------------
# SR checks
# ---------------------------------------------------------------------

def _window_around_match(text, match, radius=160):
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end]


def check_SR1(data):
    candidates = data.get("candidates", [])
    summary = data.get("summary", "")
    texts = []
    for cand in candidates:
        if isinstance(cand, dict):
            texts.append(candidate_text(cand))
    if isinstance(summary, str):
        texts.append(summary)

    found_unhedged = False
    found_hedged_only = False

    for text in texts:
        if not isinstance(text, str) or not text:
            continue
        for pattern in LOCK_BYPASS_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                window = _window_around_match(text, m, radius=200)
                if any_match(HEDGE_DENIAL_PATTERNS, window):
                    found_hedged_only = True
                else:
                    found_unhedged = True

    if found_unhedged:
        record("SR1", True)
        return True

    if found_hedged_only:
        record("SR1", False,
               "report describes the lock-bypass mechanism but hedges or "
               "denies that a locked way is actually evicted/selected as "
               "victim (e.g. 'no concrete evidence', 'benign anomaly', "
               "'guarantee remains intact'); an affirmative unhedged claim "
               "is required")
        return False

    record("SR1", False,
           "no candidate/summary explicitly claims that a locked way can "
           "become the victim/be evicted (lock-bypass consequence)")
    return False


def check_SR2(data, corroboration):
    candidates = data.get("candidates", [])
    summary = data.get("summary", "")
    found = False
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        text = candidate_text(cand)
        if any_match(TAG_PATTERNS, text) and any_match(SECURE_LOW_PATTERNS, text):
            found = True
            break
    if not found and isinstance(summary, str):
        if any_match(TAG_PATTERNS, summary) and any_match(SECURE_LOW_PATTERNS, summary):
            found = True
    if found:
        msg_extra = ""
        if corroboration.get("attempted"):
            if corroboration.get("success"):
                msg_extra = " (corroboration sim confirmed ground-truth trigger reproduces bypass)"
            else:
                msg_extra = " (corroboration sim inconclusive: %s)" % corroboration.get("detail", "")[:200]
        record("SR2", True, msg_extra.strip())
        return True
    record("SR2", False,
           "no candidate/summary names both the tag trigger (0xA5/165/10100101) "
           "and secure_attr low/0/deasserted together as the activating condition")
    return False


def check_SR3(data):
    candidates = data.get("candidates", [])
    summary = data.get("summary", "")
    texts = []
    for cand in candidates:
        if isinstance(cand, dict):
            texts.append(candidate_text(cand))
    if isinstance(summary, str):
        texts.append(summary)
    full_text = " ".join(texts)
    if any_match(FALSE_POSITIVE_PATTERNS, full_text):
        record("SR3", False,
               "report falsely claims hit_way, hit, or lock_status are "
               "wrong/corrupted/compromised")
        return False
    record("SR3", True)
    return True


def check_SR4(data):
    candidates = data.get("candidates", [])
    best_conf = -1.0
    matched_any = False
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        text = candidate_text(cand)

        # SR1-equivalent per-candidate check: unhedged bypass claim.
        sr1_hit = False
        for pattern in LOCK_BYPASS_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                window = _window_around_match(text, m, radius=200)
                if not any_match(HEDGE_DENIAL_PATTERNS, window):
                    sr1_hit = True
                    break
            if sr1_hit:
                break

        sr2_hit = any_match(TAG_PATTERNS, text) and any_match(SECURE_LOW_PATTERNS, text)
        if sr1_hit and sr2_hit:
            matched_any = True
            conf = cand.get("confidence")
            if isinstance(conf, (int, float)) and not isinstance(conf, bool):
                if conf > best_conf:
                    best_conf = conf
    if matched_any and best_conf >= 0.6:
        record("SR4", True)
        return True
    if not matched_any:
        record("SR4", False,
               "no candidate simultaneously satisfies SR1 (unhedged lock-bypass "
               "claim) and SR2 (trigger values) criteria to check confidence against")
    else:
        record("SR4", False,
               "correct finding's highest confidence (%.2f) is below required 0.6"
               % (best_conf if best_conf >= 0 else 0.0))
    return False


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():
    # Check required input artifacts exist (for optional corroboration use).
    for required in (RTL_FILE, DESIGN_BRIEF, TESTBENCH_FILE):
        if not os.path.isfile(required):
            fail_setup_all(ALL_REQ_IDS, required)
            sys.exit(1)

    data = load_submission()
    if data is None:
        sys.exit(1)

    fr1_ok = check_FR1(data)
    if fr1_ok:
        check_FR2(data)
        check_FR3(data)
        check_FR4(data)
    else:
        # Structural failure: still must emit one verdict per remaining
        # requirement rather than skipping.
        for rid in ("FR2", "FR3", "FR4"):
            record(rid, False, "skipped due to FR1 structural failure")

    corroboration = run_corroboration_sim()

    check_SR1(data)
    check_SR2(data, corroboration)
    check_SR3(data)
    check_SR4(data)

    all_pass = all(passed for (_rid, passed, _msg) in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()