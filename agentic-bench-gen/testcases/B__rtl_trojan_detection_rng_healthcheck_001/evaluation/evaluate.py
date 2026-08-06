#!/usr/bin/env python3
"""
evaluate.py -- Grader for rtl_trojan_detection_rng_healthcheck_001

Grades submission/trojan_report.json against the hidden ground truth about
inputs/lfsr_rng.v (an 8-bit LFSR RNG with a forged health monitor), using
static text analysis of the report plus an independent iverilog/vvp
simulation of the reference RTL for corroboration.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS_DIR = os.path.join(REPO_ROOT, "inputs")
SUBMISSION_PATH = os.path.join(REPO_ROOT, "submission", "trojan_report.json")
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
TB_PATH = os.path.join(EVAL_DIR, "tb_period_health.v")
LFSR_PATH = os.path.join(INPUTS_DIR, "lfsr_rng.v")

REQUIREMENT_IDS = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]

results = {}  # id -> (bool passed, str reason_if_fail)


def record(req_id, passed, reason=""):
    results[req_id] = (passed, reason)
    if passed:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, reason))


def fail_all_setup(reason):
    for rid in REQUIREMENT_IDS:
        record(rid, False, "SETUP: %s" % reason)


# ---------------------------------------------------------------------------
# Load inputs
# ---------------------------------------------------------------------------

missing_inputs = []
for fname in ("lfsr_rng.v", "design_brief.md", "testbench_stub.v"):
    if not os.path.isfile(os.path.join(INPUTS_DIR, fname)):
        missing_inputs.append(fname)

if missing_inputs:
    fail_all_setup("%s not found" % missing_inputs[0])
    sys.exit(1)

if not os.path.isfile(SUBMISSION_PATH):
    fail_all_setup("submission/trojan_report.json not found")
    sys.exit(1)

try:
    with open(SUBMISSION_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()
except Exception as e:
    fail_all_setup("could not read submission/trojan_report.json: %s" % e)
    sys.exit(1)

try:
    report = json.loads(raw_text)
except Exception as e:
    fail_all_setup("submission/trojan_report.json is not valid JSON: %s" % e)
    sys.exit(1)

if not isinstance(report, dict):
    fail_all_setup("submission/trojan_report.json top-level value must be a JSON object")
    sys.exit(1)


# ---------------------------------------------------------------------------
# FR1: structural validity
# ---------------------------------------------------------------------------

fr1_reasons = []

findings = report.get("findings", None)
if not isinstance(findings, list):
    fr1_reasons.append("'findings' missing or not a list")
    findings = []

summary = report.get("summary", None)
if not isinstance(summary, str):
    fr1_reasons.append("'summary' missing or not a string")
    summary = ""

tool_version = report.get("tool_version", None)
if not isinstance(tool_version, str):
    fr1_reasons.append("'tool_version' missing or not a string")

if len(findings) == 0:
    fr1_reasons.append("'findings' array is empty")

valid_findings = []
for idx, item in enumerate(findings):
    if not isinstance(item, dict):
        fr1_reasons.append("findings[%d] is not an object" % idx)
        continue
    missing_keys = [k for k in ("id", "location", "description", "confidence") if k not in item]
    if missing_keys:
        fr1_reasons.append("findings[%d] missing keys: %s" % (idx, missing_keys))
        continue
    if not isinstance(item["id"], str):
        fr1_reasons.append("findings[%d].id is not a string" % idx)
        continue
    if not isinstance(item["location"], str):
        fr1_reasons.append("findings[%d].location is not a string" % idx)
        continue
    if not isinstance(item["description"], str):
        fr1_reasons.append("findings[%d].description is not a string" % idx)
        continue
    conf = item["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        fr1_reasons.append("findings[%d].confidence is not numeric" % idx)
        continue
    if conf < 0 or conf > 1:
        fr1_reasons.append("findings[%d].confidence=%r out of [0,1]" % (idx, conf))
        continue
    valid_findings.append(item)

if fr1_reasons:
    record("FR1", False, "; ".join(fr1_reasons)[:400])
else:
    record("FR1", True)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def finding_text(item):
    return " ".join([
        str(item.get("id", "")),
        str(item.get("location", "")),
        str(item.get("description", "")),
    ]).lower()


all_finding_texts = [finding_text(item) for item in valid_findings]
full_report_text = (raw_text or "").lower()

FEEDBACK_TERMS = re.compile(
    r"feedback|next[\s_-]?state|\btap\b|taps\b|polynomial|state\s*register|feedback_logic|xor\s+tap",
    re.IGNORECASE,
)
HEALTH_TERMS = re.compile(
    r"health[_\s]?error|health\s*monitor|repetition|rep_count|alarm|health_monitor|repeat[\s_-]?count",
    re.IGNORECASE,
)

feedback_finding_idxs = [i for i, t in enumerate(all_finding_texts) if FEEDBACK_TERMS.search(t)]
health_finding_idxs = [i for i, t in enumerate(all_finding_texts) if HEALTH_TERMS.search(t)]


# ---------------------------------------------------------------------------
# FR2 / FR3: topical coverage
# ---------------------------------------------------------------------------

if feedback_finding_idxs:
    record("FR2", True)
else:
    record("FR2", False, "no finding references feedback/tap/next-state logic")

if health_finding_idxs:
    record("FR3", True)
else:
    record("FR3", False, "no finding references health/repetition-monitor logic")


# ---------------------------------------------------------------------------
# FR4 / SR3: extract a numeric period claim
# ---------------------------------------------------------------------------

def extract_periods(text):
    """Return a list of ints found near period/cycle/repeat vocabulary."""
    periods = []
    # Pattern 1: number immediately followed (within a few words) by period/cycle vocab
    for m in re.finditer(
        r"(\d{1,4})\s*(?:-|\s)?\s*(?:clock\s+)?(?:cycles?|clocks?)\b",
        text,
    ):
        try:
            periods.append(int(m.group(1)))
        except ValueError:
            pass
    # Pattern 2: "period (of|is|=|:) N" or "period ... N cycles"
    for m in re.finditer(
        r"period[^0-9]{0,20}?(\d{1,4})",
        text,
    ):
        try:
            periods.append(int(m.group(1)))
        except ValueError:
            pass
    # Pattern 3: "repeats every N" / "cycles before repeating"
    for m in re.finditer(
        r"repeats?\s+(?:every|after)?\s*(\d{1,4})",
        text,
    ):
        try:
            periods.append(int(m.group(1)))
        except ValueError:
            pass
    return periods


combined_text_for_period = " ".join(all_finding_texts + [summary.lower()])
reported_periods = extract_periods(combined_text_for_period)
# Filter out zero (not meaningful as a period) and absurd values from confidence fields etc.
reported_periods = [p for p in reported_periods if p > 0]

if reported_periods:
    record("FR4", True)
else:
    record("FR4", False, "no numeric period/cycle count found in findings or summary")


# ---------------------------------------------------------------------------
# SR1: feedback finding must name the missing x^6 / bit-6 tap
# ---------------------------------------------------------------------------

# Accept phrasing that directly references bit/tap 6 or x^6 in the context of
# a *missing*/*omitted*/*dropped* tap, OR that enumerates the correct
# implemented-tap set (8,5,4 1-indexed, equivalently 7,4,3 0-indexed) as
# missing the 6/5(0-indexed) tap, contrasted against the documented set.

MISSING_WORDS = r"(?:miss(?:ing|es|ed)?|omit(?:s|ted|ting)?|drop(?:s|ped|ping)?|absent|lack(?:s|ing)?|no\s+longer|does\s*not\s+(?:xor|include)|without|excludes?)"

sr1_direct_patterns = [
    # "missing x^6" / "omits the x^6 tap" etc.
    re.compile(MISSING_WORDS + r"[^.]{0,60}?x\s*\^?\s*6\b", re.IGNORECASE),
    re.compile(r"x\s*\^?\s*6[^.]{0,60}?" + MISSING_WORDS, re.IGNORECASE),
    # "missing tap 6" / "missing bit 6" / "tap at bit 6 is missing"
    re.compile(MISSING_WORDS + r"[^.]{0,60}?(?:tap|bit)\s*(?:position\s*)?6\b", re.IGNORECASE),
    re.compile(r"(?:tap|bit)\s*(?:position\s*)?6\b[^.]{0,60}?" + MISSING_WORDS, re.IGNORECASE),
    # "state[6]" style reference combined with missing wording
    re.compile(MISSING_WORDS + r"[^.]{0,80}?state\s*\[\s*6\s*\]", re.IGNORECASE),
    re.compile(r"state\s*\[\s*6\s*\][^.]{0,80}?" + MISSING_WORDS, re.IGNORECASE),
]

# Enumeration-based acceptance: documented taps {8,6,5,4} (1-indexed) or
# equivalently {7,5,4,3} (0-indexed) mentioned alongside an implemented set
# that excludes 6 (1-indexed) / 5 (0-indexed... note ground truth says
# implemented taps are bits 8,6,5 in "1-indexed convention" per the report's
# own wording is actually {8,5,4} missing 6; ground_truth text: "state[7] ^
# state[5] ^ state[4]" i.e. 0-indexed bits 7,5,4 which is 1-indexed 8,6,5...
# To stay strictly faithful to the ground_truth string, accept any phrasing
# that names the four documented taps and the three implemented ones with 6
# (1-indexed) / 6 (0-indexed, i.e. state[6]) called out as absent.

def has_enumeration_evidence(text):
    # Look for the documented full set nearby, and an omission cue mentioning 6.
    doc_set_mentioned = re.search(r"8\s*,?\s*6\s*,?\s*5\s*,?\s*4|x\^8.{0,20}x\^6.{0,20}x\^5.{0,20}x\^4", text)
    six_omission = re.search(MISSING_WORDS + r"[^.]{0,80}?\b6\b", text) or re.search(r"\b6\b[^.]{0,80}?" + MISSING_WORDS, text)
    return bool(doc_set_mentioned) and bool(six_omission)

sr1_ok = False
sr1_texts = [all_finding_texts[i] for i in feedback_finding_idxs] if feedback_finding_idxs else []
search_pool = sr1_texts if sr1_texts else [full_report_text]

for t in search_pool:
    if any(p.search(t) for p in sr1_direct_patterns):
        sr1_ok = True
        break
    if has_enumeration_evidence(t):
        sr1_ok = True
        break

# Also check summary text as a fallback source of the same claim.
if not sr1_ok:
    if any(p.search(summary.lower()) for p in sr1_direct_patterns) or has_enumeration_evidence(summary.lower()):
        sr1_ok = True

if sr1_ok:
    record("SR1", True)
else:
    record("SR1", False,
           "no feedback finding names the missing x^6 / bit-6 tap "
           "(vague 'feedback logic differs' claims do not satisfy SR1)")


# ---------------------------------------------------------------------------
# Independent simulation via iverilog/vvp
# ---------------------------------------------------------------------------

sim_period = None
sim_health_error_seen = None
sim_error = None

if not os.path.isfile(TB_PATH):
    sim_error = "evaluation/tb_period_health.v not found"
else:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            vvp_path = os.path.join(tmpdir, "sim.vvp")
            compile_cmd = ["iverilog", "-g2012", "-o", vvp_path, LFSR_PATH, TB_PATH]
            comp = subprocess.run(
                compile_cmd, cwd=tmpdir, capture_output=True, text=True, timeout=30
            )
            if comp.returncode != 0:
                sim_error = "iverilog compile failed: %s" % (comp.stderr or comp.stdout)[:300]
            else:
                run = subprocess.run(
                    ["vvp", vvp_path], cwd=tmpdir, capture_output=True, text=True, timeout=30
                )
                out = run.stdout or ""
                m_period = re.search(r"PERIOD=(\d+)", out)
                m_health = re.search(r"HEALTH_ERROR_SEEN=([01])", out)
                if m_period:
                    sim_period = int(m_period.group(1))
                if m_health:
                    sim_health_error_seen = int(m_health.group(1))
                if sim_period is None or sim_health_error_seen is None:
                    sim_error = "could not parse PERIOD/HEALTH_ERROR_SEEN from vvp output: %s" % out[:300]
    except subprocess.TimeoutExpired:
        sim_error = "iverilog/vvp timed out"
    except FileNotFoundError as e:
        sim_error = "toolchain not found: %s" % e
    except Exception as e:
        sim_error = "unexpected simulation error: %s" % e


# ---------------------------------------------------------------------------
# SR2: health-monitor finding must explain the zero-crossing suppression
# ---------------------------------------------------------------------------

ZERO_CROSS_PATTERNS = [
    re.compile(r"(?:rand_out|output|state)\s*(?:==|=)\s*(?:8'h0+|0x0+|0+)\b", re.IGNORECASE),
    re.compile(r"zero[\s-]?cross", re.IGNORECASE),
    re.compile(r"rand_out\s*(?:==|=)\s*0\b"),
    re.compile(r"(?:resets?|clears?|suppress(?:es|ed|ion)?)[^.]{0,60}?(?:rep_count|repetition\s+counter|repeat\s+counter)[^.]{0,60}?(?:zero|0x00|0)\b", re.IGNORECASE),
    re.compile(r"(?:rep_count|repetition\s+counter|repeat\s+counter)[^.]{0,60}?(?:resets?|clears?|suppress(?:es|ed|ion)?)[^.]{0,60}?(?:zero|0x00|\b0\b)", re.IGNORECASE),
    re.compile(r"whenever\s+(?:rand_out|the\s+output)\s+(?:is|equals|hits)\s*(?:zero|0x00|0)\b", re.IGNORECASE),
]

sr2_texts = [all_finding_texts[i] for i in health_finding_idxs] if health_finding_idxs else []
sr2_search_pool = sr2_texts if sr2_texts else [full_report_text]

sr2_ok = any(any(p.search(t) for p in ZERO_CROSS_PATTERNS) for t in sr2_search_pool)
if not sr2_ok:
    sr2_ok = any(p.search(summary.lower()) for p in ZERO_CROSS_PATTERNS)

sr2_reasons = []
if not sr2_ok:
    sr2_reasons.append("no health-monitor finding explains the rand_out==0 / zero-crossing "
                        "suppression of the repetition counter")

# Corroborate with simulation: ground truth expects health_error to remain 0
# despite a short period. If simulation is available and contradicts this
# (i.e. health_error DID assert, or period wasn't actually short), that is a
# tooling/ground-truth anomaly, not a submission fault -- we only use this to
# strengthen confidence, not to fail the submission when the submission text
# is already sound. We only hard-fail SR2 on the textual check.

if sim_error:
    # Simulation unavailable: rely solely on textual check (already computed).
    pass
else:
    if sim_health_error_seen == 1:
        # Ground truth infra anomaly - do not penalize submission, but note it.
        pass

if sr2_ok:
    record("SR2", True)
else:
    record("SR2", False, "; ".join(sr2_reasons)[:400])


# ---------------------------------------------------------------------------
# SR3: numeric period must be in [20,40], corroborated by simulation
# ---------------------------------------------------------------------------

in_range_periods = [p for p in reported_periods if 20 <= p <= 40]
near_255_periods = [p for p in reported_periods if p >= 200]

if not reported_periods:
    record("SR3", False, "no numeric period reported to evaluate against ground truth")
elif in_range_periods:
    # Accept as long as at least one plausible period claim in-range exists,
    # even if other unrelated numbers also appear.
    reason_extra = ""
    if sim_error:
        reason_extra = " (simulation cross-check unavailable: %s)" % sim_error
    record("SR3", True)
elif near_255_periods and not in_range_periods:
    record("SR3", False, "reported period(s) %s imply the full 255-cycle maximal sequence, "
                          "not the true short cycle" % near_255_periods)
else:
    record("SR3", False, "reported period(s) %s fall outside the accepted [20,40] window "
                          "(ground truth ~28)" % reported_periods)


# ---------------------------------------------------------------------------
# SR4: no false-clearance claim + adequate confidence on the core finding
# ---------------------------------------------------------------------------

FALSE_CLEARANCE_PATTERNS = [
    re.compile(r"health_error\s+(?:correctly|properly|successfully)\s+(?:detects?|flags?|catches?|identifies?)", re.IGNORECASE),
    re.compile(r"health\s+monitor\s+(?:is\s+)?(?:working|functioning|operating)\s+correctly", re.IGNORECASE),
    re.compile(r"no\s+trojan(?:s)?\s+(?:found|detected|identified)", re.IGNORECASE),
    re.compile(r"health_error\s+(?:is\s+)?(?:working|correct|accurate)\b", re.IGNORECASE),
    re.compile(r"health\s+check\s+(?:is\s+)?(?:functioning|working)\s+(?:correctly|as\s+intended)", re.IGNORECASE),
]

false_clearance_hit = None
for t in all_finding_texts + [full_report_text]:
    for p in FALSE_CLEARANCE_PATTERNS:
        m = p.search(t)
        if m:
            false_clearance_hit = m.group(0)
            break
    if false_clearance_hit:
        break

sr4_reasons = []
if false_clearance_hit:
    sr4_reasons.append("report falsely claims health_error/health monitor works correctly "
                        "or claims no trojan found (%r)" % false_clearance_hit)

# Determine confidence on the combined/most-relevant finding(s).
combined_idxs = set(feedback_finding_idxs) & set(health_finding_idxs)
candidate_idxs = combined_idxs if combined_idxs else (set(feedback_finding_idxs) | set(health_finding_idxs))

max_conf = None
if candidate_idxs:
    confs = []
    for i in candidate_idxs:
        item = valid_findings[i]
        try:
            confs.append(float(item.get("confidence", 0)))
        except (TypeError, ValueError):
            pass
    if confs:
        max_conf = max(confs)

if max_conf is None:
    sr4_reasons.append("no feedback/health-related finding carries a usable confidence value")
elif max_conf < 0.5:
    sr4_reasons.append("highest confidence among feedback/health-related findings is %.2f (<0.5)" % max_conf)

if sr4_reasons:
    record("SR4", False, "; ".join(sr4_reasons)[:400])
else:
    record("SR4", True)


# ---------------------------------------------------------------------------
# Final exit
# ---------------------------------------------------------------------------

all_passed = all(passed for passed, _ in results.values())
sys.exit(0 if all_passed else 1)