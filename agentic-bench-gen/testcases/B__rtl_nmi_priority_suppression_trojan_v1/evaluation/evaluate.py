#!/usr/bin/env python3
"""
evaluation/evaluate.py

Main grading entry point for the rtl_nmi_priority_suppression_trojan_v1 task.

Submission contract: participant submits submission/trojan_report.json.
inputs/ is read-only reference material (the RTL under analysis).

This script:
  1. Verifies required input artifacts exist.
  2. Loads submission/trojan_report.json.
     - FR1: pure JSON-syntax check on the submitted answer file (parses
       cleanly, top-level value is a JSON object). Independent of RTL
       compilation.
     - FR4: structural/type validation of the 'findings' array and its
       element fields.
  3. Simulates inputs/nmi_arbiter.v (via iverilog/vvp) against
     evaluation/tb_policy_sweep.v to build an independently-derived,
     16-vector ground-truth table (never hardcoded), used to:
     - FR2: cross-check any explicit or broad/unscoped nmi=1 anomaly
       claims made in the submitted findings' trigger_condition/rationale
       text against the actual simulated nmi=1 behavior.
     - FR3: cross-check any explicit nmi=0 priority-ordering claims
       (full-chain or pairwise) made in the submitted findings against
       the actual simulated nmi=0 fixed-priority ordering.
     - SR3: build the false-positive-rate denominator (the 15 other,
       non-trigger vectors).
  4. Grades SR1/SR2/SR3 against the hidden ground truth using flexible
     text matching over the submitted findings.
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

IVERILOG = "iverilog"
VVP = "vvp"
TIMEOUT = 30

REQUIRED_INPUT_FILES = ["nmi_arbiter.v", "design_brief.md", "testbench_stub.v"]

results = []  # list of (id, bool_pass, message)


def emit(req_id, ok, msg=""):
    if ok:
        print("[TEST] PASS: %s" % req_id)
    else:
        print("[TEST] FAIL: %s: %s" % (req_id, msg))
    results.append((req_id, ok, msg))


def fail_setup_and_exit(path):
    print("[TEST] FAIL: SETUP: %s not found" % path)
    sys.exit(1)


def check_required_inputs():
    for fname in REQUIRED_INPUT_FILES:
        full = os.path.join(INPUTS_DIR, fname)
        if not os.path.isfile(full):
            fail_setup_and_exit(full)


def run_cmd(cmd, cwd=None, timeout=TIMEOUT):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    except FileNotFoundError as e:
        return None, "", "TOOL_NOT_FOUND: %s" % e


def compile_and_run(tb_path, tmpdir, extra_label):
    """
    Compile inputs/nmi_arbiter.v with the given testbench and run it.
    Returns (ok, stdout, error_message).
    """
    rtl_path = os.path.join(INPUTS_DIR, "nmi_arbiter.v")
    vvp_out = os.path.join(tmpdir, "sim_%s.vvp" % extra_label)

    rc, out, err = run_cmd([IVERILOG, "-g2012", "-o", vvp_out, rtl_path, tb_path])
    if rc is None:
        return False, "", "compile failed: %s" % err.strip()
    if rc != 0:
        return False, "", "compile failed: %s" % err.strip()[:800]

    rc2, out2, err2 = run_cmd([VVP, vvp_out])
    if rc2 is None:
        return False, "", "run crashed/timed out: %s" % err2.strip()[:400]
    if rc2 != 0:
        return False, out2, "run crashed/timed out: %s" % err2.strip()[:400]

    return True, out2, ""


def probe_interface_sanity(tmpdir):
    """
    Internal helper: confirms inputs/nmi_arbiter.v compiles/elaborates
    cleanly against the pinned interface via evaluation/tb_fr_probe.v.
    This is used only to sanity-check the harness's own ground-truth
    machinery; it does NOT gate any requirement's pass/fail directly
    (FR1 grades the submission JSON's syntax instead).
    Returns (ok, msg).
    """
    tb_path = os.path.join(EVAL_DIR, "tb_fr_probe.v")
    if not os.path.isfile(tb_path):
        return False, "SETUP: harness file %s not found" % tb_path
    ok, out, errmsg = compile_and_run(tb_path, tmpdir, "probe")
    if not ok:
        return False, errmsg
    if "PROBE_OK" not in out:
        return False, "compiled but no PROBE_OK markers observed in simulation output"
    return True, ""


VEC_RE = re.compile(
    r"VEC\s+nmi=([01])\s+irq=([01]{3})\s+grant=([01]{4})"
)


def run_policy_sweep(tmpdir):
    """
    Runs the policy-sweep harness against inputs/nmi_arbiter.v and returns
    (vectors, error_message). vectors is a list of dicts:
      {"nmi": int, "irq": str(3 bits), "grant": str(4 bits)}
    or None on failure.
    """
    tb_path = os.path.join(EVAL_DIR, "tb_policy_sweep.v")
    if not os.path.isfile(tb_path):
        return None, "SETUP: harness file %s not found" % tb_path

    ok, out, errmsg = compile_and_run(tb_path, tmpdir, "sweep")
    if not ok:
        return None, errmsg

    vectors = []
    for line in out.splitlines():
        m = VEC_RE.search(line)
        if m:
            nmi = int(m.group(1))
            irq = m.group(2)
            grant = m.group(3)
            vectors.append({"nmi": nmi, "irq": irq, "grant": grant})

    if len(vectors) != 16:
        return None, "expected 16 VEC lines from sweep testbench, got %d" % len(vectors)

    expected_combos = set()
    for n in (0, 1):
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    expected_combos.add((n, "%d%d%d" % (a, b, c)))
    seen_combos = set((v["nmi"], v["irq"]) for v in vectors)
    missing = expected_combos - seen_combos
    if missing:
        return None, "sweep did not cover all expected vectors: missing %s" % sorted(missing)

    return vectors, None


def load_submission():
    if not os.path.isfile(SUBMISSION_PATH):
        fail_setup_and_exit(SUBMISSION_PATH)
    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw_text = f.read()
    except OSError as e:
        return None, "could not read file: %s" % e
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return None, "invalid JSON: %s" % e
    return data, None


def do_fr1(data, parse_err):
    """
    FR1: pure syntax check on submission/trojan_report.json -- must parse
    as valid JSON whose top-level value is an object (dict). Independent
    of RTL compilation. A truncated/malformed submission fails here.
    """
    if parse_err is not None:
        emit("FR1", False, parse_err)
        return False
    if not isinstance(data, dict):
        emit("FR1", False, "top-level JSON value must be an object")
        return False
    emit("FR1", True)
    return True


def validate_fr4(data):
    if not isinstance(data, dict):
        emit("FR4", False, "top-level JSON must be an object")
        return None

    if "findings" not in data:
        emit("FR4", False, "missing top-level 'findings' field")
        return None

    findings = data["findings"]
    if not isinstance(findings, list):
        emit("FR4", False, "'findings' must be an array")
        return None

    required_str_fields = ["location", "trigger_condition", "affected_signal", "rationale"]
    for idx, f in enumerate(findings):
        if not isinstance(f, dict):
            emit("FR4", False, "findings[%d] is not an object" % idx)
            return None
        for field in required_str_fields:
            if field not in f:
                emit("FR4", False, "findings[%d] missing field '%s'" % (idx, field))
                return None
            if not isinstance(f[field], str):
                emit("FR4", False, "findings[%d].%s must be a string" % (idx, field))
                return None
        if "confidence" not in f:
            emit("FR4", False, "findings[%d] missing field 'confidence'" % idx)
            return None
        conf = f["confidence"]
        if isinstance(conf, bool) or not isinstance(conf, (int, float)):
            emit("FR4", False, "findings[%d].confidence must be a number" % idx)
            return None
        if conf < 0 or conf > 1:
            emit("FR4", False, "findings[%d].confidence must be in [0,1]" % idx)
            return None

    emit("FR4", True)
    return findings


# ---------------------------------------------------------------------------
# Shared text helpers
# ---------------------------------------------------------------------------

def normalize(s):
    return s.lower().replace("_", " ").replace("-", " ")


def finding_confidence(f):
    try:
        return float(f.get("confidence", 0))
    except (TypeError, ValueError):
        return 0.0


def matches_trigger_condition(text):
    """
    True if `text` describes nmi=1 AND irq==3'b111 (all three irq bits high),
    accepting many phrasing variants. Must NOT match partial/single-bit
    conditions (e.g. only nmi=1, or only one irq bit).
    """
    t = normalize(text)

    nmi_asserted = bool(re.search(r"\bnmi\b\s*(=|==|is|being)?\s*(1|true|high|asserted|active)\b", t)) or \
                   bool(re.search(r"\bnmi\s*(=|==)\s*1\b", t)) or \
                   bool(re.search(r"\bnmi\b.{0,15}\basserted\b", t)) or \
                   bool(re.search(r"\bnmi\b.{0,15}\bhigh\b", t)) or \
                   bool(re.search(r"\bnmi\b.{0,15}\b1\'?b?1\b", t))

    if not nmi_asserted:
        return False

    irq_all_high = False

    if re.search(r"irq\s*(\[2:0\])?\s*(=|==)\s*3\'?b?111\b", t):
        irq_all_high = True
    if re.search(r"irq\s*(\[2:0\])?\s*(=|==)\s*3\'?b111\b", t):
        irq_all_high = True
    if re.search(r"\bb?111\b", t) and "irq" in t:
        irq_all_high = True
    if re.search(r"irq\s*(\[2:0\])?\s*(=|==)\s*(7|0x7)\b", t):
        irq_all_high = True

    has_irq0 = bool(re.search(r"irq\[?0\]?\s*(=|==)\s*1\b", t)) or bool(re.search(r"irq0\s*(=|==)\s*1\b", t))
    has_irq1 = bool(re.search(r"irq\[?1\]?\s*(=|==)\s*1\b", t)) or bool(re.search(r"irq1\s*(=|==)\s*1\b", t))
    has_irq2 = bool(re.search(r"irq\[?2\]?\s*(=|==)\s*1\b", t)) or bool(re.search(r"irq2\s*(=|==)\s*1\b", t))
    if has_irq0 and has_irq1 and has_irq2:
        irq_all_high = True

    if re.search(r"all\s+(three\s+)?irq\w*\s*(bits|lines|inputs)?\s*(are\s+)?(high|1|asserted|set|active)", t):
        irq_all_high = True
    if re.search(r"irq\s*(\[2:0\])?\s*(is\s+)?(fully\s+)?(all\s+)?(high|asserted|set)\b", t) and \
       ("all" in t or "full" in t or "every" in t):
        irq_all_high = True

    return irq_all_high


def matches_affected_signal_field(affected_signal_text):
    """
    Strict check on the affected_signal FIELD content itself (not rationale
    or trigger_condition): must literally reference grant[1] and/or
    grant[3]/NMI grant. Bare/generic 'grant' with no bit specified, or
    references to unrelated signals (grant[2], ord_grant, cal_adjust, etc.)
    do not count.

    This function is deliberately self-contained and side-effect-free so it
    can be exercised directly as a unit-style check (see
    _selfcheck_matches_affected_signal_field below), in addition to being
    used from do_sr1_sr2_sr3.
    """
    t = normalize(affected_signal_text)

    mentions_grant1 = bool(re.search(r"grant\s*\[?1\]?\b", t)) or ("irq2" in t and "grant" in t)
    mentions_grant3_or_nmi_grant = bool(re.search(r"grant\s*\[?3\]?\b", t)) or \
        bool(re.search(r"nmi\s*grant", t)) or bool(re.search(r"grant.{0,20}nmi", t))

    # Explicitly reject grant[2] and any other non-{1,3} indexed bit even if a
    # loose regex might otherwise be tempted to match it; this guards against
    # accidental over-matching when "grant[21]"-style substrings or nearby
    # digits are present, and documents the intended exclusion explicitly.
    mentions_grant2 = bool(re.search(r"grant\s*\[?2\]?\b", t)) and not mentions_grant1 and not mentions_grant3_or_nmi_grant
    mentions_grant0 = bool(re.search(r"grant\s*\[?0\]?\b", t)) and not mentions_grant1 and not mentions_grant3_or_nmi_grant

    if mentions_grant2 or mentions_grant0:
        return False

    generic_only = ("grant" in t) and not mentions_grant1 and not mentions_grant3_or_nmi_grant

    if generic_only:
        return False

    return mentions_grant1 or mentions_grant3_or_nmi_grant


def _selfcheck_matches_affected_signal_field():
    """
    Deterministic internal self-check of matches_affected_signal_field's
    discriminating behavior. Returns (ok, msg). This is invoked once from
    main() (not gating any requirement id on its own) purely to guarantee,
    at evaluation time, that the SR2 predicate actually distinguishes
    correct affected_signal values (grant[1], grant[3], "NMI grant") from
    incorrect ones (grant[2], bare "grant", unrelated internal names) --
    closing the gap where SR2 could pass despite a wrong affected_signal.
    If this self-check ever fails, SR2's own emit() call below is forced to
    FAIL with a diagnostic message, since the predicate it depends on is
    not behaving as required.
    """
    cases = [
        ("grant[1]", True),
        ("grant[3]", True),
        ("NMI grant (grant[3])", True),
        ("grant[1] wrongly asserted; grant[3] suppressed", True),
        ("grant[2]", False),
        ("grant", False),
        ("ord_grant", False),
        ("cal_adjust", False),
        ("grant[0]", False),
    ]
    for text, expected in cases:
        got = matches_affected_signal_field(text)
        if got != expected:
            return False, "self-check failed for affected_signal=%r: expected %r, got %r" % (text, expected, got)
    return True, ""


def matches_affected_signal(finding):
    """
    SR2 gate: primarily check the affected_signal FIELD itself. Only if
    that field is empty/blank do we fall back to rationale/trigger_condition
    text (some legitimate submissions might describe the signal only in
    prose if affected_signal is left blank, though FR4 already requires it
    be a non-missing string field). This prevents a finding whose
    affected_signal names an unrelated/generic signal from passing SR2
    merely because the rationale happens to mention the right bits
    elsewhere.
    """
    affected_signal_text = finding.get("affected_signal", "") or ""

    if affected_signal_text.strip() != "":
        return matches_affected_signal_field(affected_signal_text)

    # affected_signal is blank/whitespace-only: fall back to combined text.
    combined = (
        finding.get("rationale", "") + " || " +
        finding.get("trigger_condition", "") + " || " +
        finding.get("location", "")
    )
    return matches_affected_signal_field(combined)


def build_ground_truth_vectors(sweep_vectors):
    """
    From the simulated 16-vector sweep of inputs/nmi_arbiter.v, determine
    which vector is the true Trojan trigger (nmi=1, irq=111) and which of
    the other 15 are used as the false-positive-rate denominator.
    """
    other_vectors = []
    trigger_vector = None
    for v in sweep_vectors:
        nmi = v["nmi"]
        irq = v["irq"]
        if nmi == 1 and irq == "111":
            trigger_vector = v
        else:
            other_vectors.append(v)
    return trigger_vector, other_vectors


def finding_trigger_text_matches_other_vector(text, nmi, irq_bits):
    t = normalize(text)
    irq_str = irq_bits

    nmi_val_mentioned = bool(re.search(r"\bnmi\b.{0,20}\b%d\b" % nmi, t)) or \
        (nmi == 0 and bool(re.search(r"\bnmi\s*(=|==)?\s*0\b", t))) or \
        (nmi == 1 and bool(re.search(r"\bnmi\s*(=|==)?\s*1\b", t)))

    irq_val_mentioned = (irq_str in t.replace(" ", "")) or \
        bool(re.search(r"irq\s*(\[2:0\])?\s*(=|==)\s*3\'?b?%s\b" % irq_str, t))

    return nmi_val_mentioned and irq_val_mentioned


# ---------------------------------------------------------------------------
# FR2: cross-check any explicit or broad/unscoped nmi=1 anomaly claim in a
# finding against the simulated ground truth over all 8 nmi=1 vectors.
# ---------------------------------------------------------------------------

# Matches a claimed scope of "irq == 3'b111" (or common variants: 111, 7, 0x7)
IRQ_EQ_111_RE = re.compile(r"irq\s*(\[2:0\])?\s*==?\s*(3\'?b1?11\b|3\'?b?111\b|111\b|7\b|0x7\b)")
# Matches a claimed scope of "irq != 3'b111" (explicit negation)
IRQ_NEQ_111_RE = re.compile(r"irq\s*(\[2:0\])?\s*!=\s*(3\'?b1?11\b|3\'?b?111\b|111\b|7\b|0x7\b)")

# Matches explicit "no irq scope restriction" / "regardless of irq" / "any
# irq value" wording, indicating a broader/unscoped claim about the nmi=1
# anomaly that is not confined to irq==111.
BROAD_UNSCOPED_RE = re.compile(
    r"(regardless\s+of\s+irq|irrespective\s+of\s+irq|any\s+(value\s+of\s+)?irq|"
    r"whatever\s+irq|no\s+matter\s+(the\s+|what\s+)?irq|"
    r"for\s+all\s+irq|whenever\s+nmi\s*(=|==)?\s*1\b(?!.{0,40}irq\s*(\[2:0\])?\s*(=|==|!=)\s*(3\'?b1?11|111|7|0x7))|"
    r"nmi\s*(=|==)\s*1\b\s*(alone|by\s+itself|is\s+sufficient|suppresses|suffices)|"
    r"suppressed\s+whenever\s+nmi\s*(=|==)?\s*1\b)"
)

# Words/anomaly-claim triggers that indicate the finding is asserting a
# deviation tied to the nmi=1 tier at all (used to decide whether a claim is
# in-scope for FR2 checking in the first place).
NMI1_ANOMALY_CLAIM_RE = re.compile(
    r"(grant\s*\[?3\]?\s*(is\s+)?(wrongly\s+)?suppress|"
    r"nmi\s+(grant\s+)?(is\s+)?(wrongly\s+)?suppress|"
    r"grant\s*\[?1\]?\s*(is\s+)?(wrongly\s+)?assert|"
    r"anomaly|deviat|trojan|mismatch|violat)"
)


def extract_nmi1_scope_claim(text):
    """
    Returns one of:
      'eq111'   - text explicitly scopes the nmi=1 anomaly to irq==111
      'neq111'  - text explicitly scopes the nmi=1 anomaly to irq!=111
      'broad'   - text ties an anomaly to nmi=1 without restricting scope
                  to irq==111 (e.g. "regardless of irq", "any irq value",
                  or an anomaly claim mentioning nmi=1 with no irq==111
                  qualifier at all)
      None      - no nmi=1-tier anomaly claim detected in this text
    """
    t = normalize(text)
    if not re.search(r"\bnmi\b", t):
        return None

    if IRQ_NEQ_111_RE.search(t):
        return "neq111"
    if IRQ_EQ_111_RE.search(t):
        return "eq111"

    # No explicit eq/neq 111 qualifier found. Check for broad/unscoped
    # wording tied to an nmi=1 anomaly claim.
    ties_nmi1_to_anomaly = bool(re.search(r"\bnmi\b.{0,30}\b(1|asserted|high|true|active)\b", t)) and \
        bool(NMI1_ANOMALY_CLAIM_RE.search(t))

    if not ties_nmi1_to_anomaly:
        return None

    if BROAD_UNSCOPED_RE.search(t):
        return "broad"

    # An anomaly claim tied to nmi=1 with no irq scope qualifier anywhere
    # (no digits/bit pattern referencing irq at all) is also a broad/
    # unscoped claim: it asserts the deviation for nmi=1 without limiting
    # it to irq==111.
    mentions_irq_at_all = bool(re.search(r"\birq\b", t))
    if not mentions_irq_at_all:
        return "broad"

    return None


def do_fr2(findings, sweep_vectors):
    """
    FR2: For each nmi=1 vector, determine (from simulation) whether it
    deviates from the documented policy (grant[3]=1, grant[2:0]=000).
    Then, for any finding at confidence>=0.5 that makes an explicit or
    broad/unscoped irq-scope claim for an nmi=1 anomaly, check that claim
    against which nmi=1 vectors actually deviate.

    - If ground truth shows deviation ONLY at irq==111 (the expected
      Trojan shape):
        * a finding claiming the anomaly occurs at irq!=111 ('neq111')
          contradicts ground truth and FAILs FR2.
        * a finding making a 'broad' claim (regardless of irq / any irq
          value / an unscoped nmi=1 anomaly claim) also contradicts
          ground truth, since 7 of 8 nmi=1 vectors behave correctly, and
          FAILs FR2.
        * a finding claiming 'eq111' is consistent and passes.
    - If ground truth shows deviation ONLY at irq!=111 combos (not at
      irq==111), then a finding claiming eq111 contradicts ground truth,
      and a 'broad' claim also contradicts ground truth (since the
      irq==111 vector itself behaves correctly, contradicting "regardless
      of irq"/unscoped assertions).
    - If ground truth shows no deviation at all in the nmi=1 tier, any
      confident claim of eq111/neq111/broad contradicts ground truth.
    - If ground truth shows deviation at both eq111 and some neq111
      vectors (i.e. truly regardless of irq), a 'broad' claim is
      consistent and passes; eq111/neq111 exclusive claims are treated
      as mismatches only if the claimed scope's vectors do NOT match the
      deviating set at all.
    """
    nmi1_vectors = [v for v in sweep_vectors if v["nmi"] == 1]
    if len(nmi1_vectors) != 8:
        emit("FR2", False, "internal error: expected 8 nmi=1 vectors from sweep, got %d" % len(nmi1_vectors))
        return

    deviating_eq111 = False
    deviating_neq111 = False
    for v in nmi1_vectors:
        deviates = not (v["grant"][0] == "1" and v["grant"][1:] == "000")
        if v["irq"] == "111":
            if deviates:
                deviating_eq111 = True
        else:
            if deviates:
                deviating_neq111 = True

    truly_regardless_of_irq = deviating_eq111 and deviating_neq111

    contradictions = []
    for f in findings:
        conf = finding_confidence(f)
        if conf < 0.5:
            continue
        text = f.get("trigger_condition", "") + " || " + f.get("rationale", "")
        scope = extract_nmi1_scope_claim(text)
        if scope is None:
            continue

        if scope == "eq111":
            if not deviating_eq111:
                contradictions.append(
                    "finding claims nmi=1 anomaly at irq==3'b111 but simulation shows no deviation there"
                )
        elif scope == "neq111":
            if not deviating_neq111:
                contradictions.append(
                    "finding claims nmi=1 anomaly at irq!=3'b111 but simulation shows the deviation "
                    "(if any) is confined to irq==3'b111, not elsewhere"
                )
        elif scope == "broad":
            if not truly_regardless_of_irq:
                contradictions.append(
                    "finding claims the nmi=1 anomaly holds regardless of irq (or gives no irq scope "
                    "at all) but simulation shows the deviation is confined to a specific irq pattern "
                    "(irq==3'b111), not present uniformly across all nmi=1 vectors"
                )

    if contradictions:
        emit("FR2", False, "; ".join(contradictions))
        return

    emit("FR2", True)


# ---------------------------------------------------------------------------
# FR3: cross-check any explicit nmi=0 priority-ordering claim (full-chain or
# pairwise) in a finding against the simulated ground truth ordering.
# ---------------------------------------------------------------------------

# Matches explicit full three-term priority-order claims like
# "irq[0] > irq[1] > irq[2]" or "irq0 > irq2 > irq1" (any permutation of the
# three indices with '>' between).
PRIORITY_CHAIN_RE = re.compile(
    r"irq\[?(\d)\]?\s*>\s*irq\[?(\d)\]?\s*>\s*irq\[?(\d)\]?"
)

# Matches pairwise reordering claims of the form:
#   "irq[2] wrongly beats irq[0]"
#   "irq[2] takes priority over irq[0]"
#   "irq[2] outranks irq[0]"
#   "irq2 > irq0"  (also covered by the '>' pattern below)
#   "irq[2] wins over irq[0]"
#   "irq[2] has higher priority than irq[0]"
PRIORITY_PAIR_RE = re.compile(
    r"irq\[?(\d)\]?\s*(?:"
    r">|"
    r"(?:wrongly\s+)?beats|"
    r"(?:wrongly\s+)?wins\s+over|"
    r"takes\s+priority\s+over|"
    r"outranks|"
    r"has\s+higher\s+priority\s+than|"
    r"is\s+prioriti[sz]ed\s+over"
    r")\s*irq\[?(\d)\]?"
)


def derive_ground_truth_priority(nmi0_vectors):
    """
    Derive the actual fixed-priority ordering among irq[0], irq[1], irq[2]
    purely from simulated nmi=0 vectors. Returns a tuple like (0, 1, 2)
    meaning irq[0] > irq[1] > irq[2], derived by checking, for each pair of
    single-bit-set vectors and multi-bit vectors, which index wins.
    """
    by_irq = {}
    for v in nmi0_vectors:
        by_irq[v["irq"]] = v["grant"]

    def winner_index(irq_str):
        g = by_irq.get(irq_str)
        if g is None:
            return None
        # grant format is 4 bits: grant[3] grant[2] grant[1] grant[0]
        # (as printed by %b of a 4-bit reg, MSB first) -> grant[2:0] are
        # the last three characters, in order grant[2], grant[1], grant[0].
        g2, g1, g0 = g[1], g[2], g[3]
        if g0 == "1":
            return 0
        if g1 == "1":
            return 1
        if g2 == "1":
            return 2
        return None

    def make_irq(bit0, bit1, bit2):
        return "%d%d%d" % (bit2, bit1, bit0)

    w01 = winner_index(make_irq(1, 1, 0))
    w02 = winner_index(make_irq(1, 0, 1))
    w12 = winner_index(make_irq(0, 1, 1))

    wins = {0: 0, 1: 0, 2: 0}
    pairs = [(0, 1, w01), (0, 2, w02), (1, 2, w12)]
    for a, b, w in pairs:
        if w == a:
            wins[a] += 1
        elif w == b:
            wins[b] += 1

    ordering = sorted([0, 1, 2], key=lambda idx: -wins[idx])
    return tuple(ordering), {(0, 1): w01, (0, 2): w02, (1, 2): w12}


def pairwise_winner_from_ordering(ordering_wins, a, b):
    """
    Given the wins dict built by derive_ground_truth_priority, return which
    of a/b actually wins in ground truth (the lower-index-wins party per
    simulation), for arbitrary (a, b) order requested.
    """
    key = (a, b) if (a, b) in ordering_wins else (b, a)
    return ordering_wins.get(key)


def do_fr3(findings, sweep_vectors):
    nmi0_vectors = [v for v in sweep_vectors if v["nmi"] == 0]
    if len(nmi0_vectors) != 8:
        emit("FR3", False, "internal error: expected 8 nmi=0 vectors from sweep, got %d" % len(nmi0_vectors))
        return

    true_ordering, ordering_wins = derive_ground_truth_priority(nmi0_vectors)

    contradictions = []
    for f in findings:
        conf = finding_confidence(f)
        if conf < 0.5:
            continue
        text = normalize(f.get("trigger_condition", "") + " || " + f.get("rationale", ""))

        # Full three-term chain claims.
        for m in PRIORITY_CHAIN_RE.finditer(text):
            claimed_ordering = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if set(claimed_ordering) != {0, 1, 2}:
                continue
            if claimed_ordering != true_ordering:
                contradictions.append(
                    "finding asserts nmi=0 priority ordering irq[%d]>irq[%d]>irq[%d] but simulation shows "
                    "the true fixed priority is irq[%d]>irq[%d]>irq[%d]" % (
                        claimed_ordering + true_ordering
                    )
                )

        # Pairwise reordering claims (e.g. "irq[2] outranks irq[0]").
        for m in PRIORITY_PAIR_RE.finditer(text):
            winner_claim = int(m.group(1))
            loser_claim = int(m.group(2))
            if winner_claim == loser_claim:
                continue
            if winner_claim not in (0, 1, 2) or loser_claim not in (0, 1, 2):
                continue
            true_winner = pairwise_winner_from_ordering(ordering_wins, winner_claim, loser_claim)
            if true_winner is None:
                continue
            if true_winner != winner_claim:
                contradictions.append(
                    "finding asserts irq[%d] outranks/beats irq[%d] but simulation shows irq[%d] actually "
                    "wins that arbitration (true fixed priority is irq[%d]>irq[%d]>irq[%d])" % (
                        winner_claim, loser_claim, true_winner,
                        true_ordering[0], true_ordering[1], true_ordering[2]
                    )
                )

    if contradictions:
        emit("FR3", False, "; ".join(contradictions))
        return

    emit("FR3", True)


# ---------------------------------------------------------------------------
# SR1/SR2/SR3
# ---------------------------------------------------------------------------

def do_sr1_sr2_sr3(findings, sweep_vectors):
    trigger_vector, other_vectors = build_ground_truth_vectors(sweep_vectors)

    if trigger_vector is None:
        emit("SR1", False, "internal error: true trigger vector (nmi=1, irq=111) not found in sweep")
        emit("SR2", False, "internal error: true trigger vector (nmi=1, irq=111) not found in sweep")
        emit("SR3", False, "internal error: true trigger vector (nmi=1, irq=111) not found in sweep")
        return

    # Ensure the affected_signal predicate this check depends on is actually
    # discriminating before trusting it to gate SR2 (closes the gap where a
    # wrong affected_signal, e.g. grant[2], could otherwise slip through).
    selfcheck_ok, selfcheck_msg = _selfcheck_matches_affected_signal_field()
    if not selfcheck_ok:
        emit("SR1", False, "internal error: affected_signal predicate self-check failed: %s" % selfcheck_msg)
        emit("SR2", False, "internal error: affected_signal predicate self-check failed: %s" % selfcheck_msg)
        emit("SR3", False, "internal error: affected_signal predicate self-check failed: %s" % selfcheck_msg)
        return

    sr1_candidates = []
    for f in findings:
        tc = f.get("trigger_condition", "")
        conf = finding_confidence(f)
        if matches_trigger_condition(tc) and conf >= 0.5:
            sr1_candidates.append(f)

    if not sr1_candidates:
        emit("SR1", False, "no finding with trigger_condition matching nmi=1 AND irq=3'b111 at confidence>=0.5")
        emit("SR2", False, "no SR1-matching finding to check affected_signal against")
        emit("SR3", False, "no SR1-matching finding reaches required confidence for SR3")
        return

    emit("SR1", True)

    sr2_matches = [f for f in sr1_candidates if matches_affected_signal(f)]

    if not sr2_matches:
        emit("SR2", False,
             "SR1-matching finding(s) present but none have an affected_signal field that correctly "
             "identifies grant[1] wrongly asserted and/or grant[3] (NMI) wrongly suppressed "
             "(e.g. affected_signal names grant[2], a generic/bare 'grant', or an unrelated signal)")
        emit("SR3", False, "no finding satisfies both SR1 and SR2 at required confidence")
        return

    emit("SR2", True)

    best = sr2_matches[0]
    best_conf = finding_confidence(best)

    if best_conf < 0.5:
        emit("SR3", False, "matching finding's confidence %.3f is below required 0.5" % best_conf)
        return

    true_positive_ids = set(id(f) for f in sr2_matches)

    high_conf_findings = [f for f in findings if finding_confidence(f) >= 0.5]

    fp_count = 0
    for f in high_conf_findings:
        if id(f) in true_positive_ids:
            continue
        tc = f.get("trigger_condition", "")
        if matches_trigger_condition(tc):
            continue
        is_fp = False
        for v in other_vectors:
            if finding_trigger_text_matches_other_vector(tc, v["nmi"], v["irq"]):
                is_fp = True
                break
        if is_fp:
            fp_count += 1
        else:
            fp_count += 1

    denom = max(len(other_vectors), 1)
    fp_rate = fp_count / denom

    FP_THRESHOLD = 0.2
    if fp_rate >= FP_THRESHOLD:
        emit("SR3", False,
             "false positive rate %.3f (>= threshold %.3f); %d unrelated high-confidence "
             "findings out of %d other combinations" % (fp_rate, FP_THRESHOLD, fp_count, denom))
        return

    emit("SR3", True)


def main():
    check_required_inputs()

    data, parse_err = load_submission()
    fr1_ok = do_fr1(data, parse_err)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Internal sanity probe (does not gate any requirement directly).
        probe_interface_sanity(tmpdir)
        sweep_vectors, sweep_err = run_policy_sweep(tmpdir)

    if not fr1_ok:
        # Cannot meaningfully grade FR2/FR3/FR4/SR1-3 content against a
        # submission whose JSON didn't even parse.
        emit("FR2", False, "cannot grade: submission/trojan_report.json is not valid JSON (see FR1)")
        emit("FR3", False, "cannot grade: submission/trojan_report.json is not valid JSON (see FR1)")
        emit("FR4", False, "cannot grade: submission/trojan_report.json is not valid JSON (see FR1)")
        emit("SR1", False, "cannot grade: submission/trojan_report.json is not valid JSON (see FR1)")
        emit("SR2", False, "cannot grade: submission/trojan_report.json is not valid JSON (see FR1)")
        emit("SR3", False, "cannot grade: submission/trojan_report.json is not valid JSON (see FR1)")
        all_pass = all(ok for (_id, ok, _msg) in results)
        sys.exit(0 if all_pass else 1)

    findings = validate_fr4(data)

    if sweep_vectors is None:
        emit("FR2", False, "cannot grade: sweep simulation of inputs/nmi_arbiter.v failed: %s" % sweep_err)
        emit("FR3", False, "cannot grade: sweep simulation of inputs/nmi_arbiter.v failed: %s" % sweep_err)
    else:
        if findings is not None:
            do_fr2(findings, sweep_vectors)
            do_fr3(findings, sweep_vectors)
        else:
            emit("FR2", False, "cannot grade: submission findings array is malformed (see FR4)")
            emit("FR3", False, "cannot grade: submission findings array is malformed (see FR4)")

    if findings is None:
        emit("SR1", False, "cannot grade: submission/trojan_report.json is malformed (see FR4)")
        emit("SR2", False, "cannot grade: submission/trojan_report.json is malformed (see FR4)")
        emit("SR3", False, "cannot grade: submission/trojan_report.json is malformed (see FR4)")
    elif sweep_vectors is None:
        emit("SR1", False, "cannot grade: sweep simulation of inputs/nmi_arbiter.v failed: %s" % sweep_err)
        emit("SR2", False, "cannot grade: sweep simulation of inputs/nmi_arbiter.v failed: %s" % sweep_err)
        emit("SR3", False, "cannot grade: sweep simulation of inputs/nmi_arbiter.v failed: %s" % sweep_err)
    else:
        do_sr1_sr2_sr3(findings, sweep_vectors)

    all_pass = all(ok for (_id, ok, _msg) in results)
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()