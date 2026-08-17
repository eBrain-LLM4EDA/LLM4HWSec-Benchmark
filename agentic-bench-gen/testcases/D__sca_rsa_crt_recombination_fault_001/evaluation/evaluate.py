#!/usr/bin/env python3
"""
evaluate.py -- Grader for sca_rsa_crt_recombination_fault_001

Grades submission/vulnerability_report.json against the hidden ground
truth for the Bellcore-style CRT recombination fault task. Reads the
reference RTL artifacts under inputs/ purely for cross-checking (an
actual iverilog/vvp fault-injection simulation), never for grading the
submission's prose style.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

INPUT_FILES = [
    "inputs/crt_recombine.v",
    "inputs/crt_reference.v",
    "inputs/tb_crt_recombine.v",
    "inputs/fault_model.md",
    "inputs/design_brief.md",
]

SUBMISSION_PATH = "submission/vulnerability_report.json"
HARNESS_TEMPLATE_PATH = "evaluation/fault_sim_harness.v"
GOLDEN_FIXTURE_PATH = "evaluation/private/golden_fixture.json"

REQUIRED_FIELDS = [
    "vulnerable_register",
    "fault_model",
    "trigger_scenario",
    "missing_verification_step",
    "recommended_fix",
]

VALID_REGISTERS = ["sig_p_reg", "sig_q_reg"]

results = {}  # requirement_id -> (passed: bool, reason: str)


def record(req_id, passed, reason=""):
    if req_id not in results:
        results[req_id] = (passed, reason)


def emit_all():
    order = ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]
    all_pass = True
    for rid in order:
        if rid not in results:
            results[rid] = (False, "requirement not evaluated")
        passed, reason = results[rid]
        if passed:
            print("[TEST] PASS: %s" % rid)
        else:
            all_pass = False
            print("[TEST] FAIL: %s: %s" % (rid, reason))
    return all_pass


def setup_fail(path):
    print("[TEST] FAIL: SETUP: %s not found" % path)
    for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
        results.setdefault(rid, (False, "setup failure: %s not found" % path))
    emit_all()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Primary-register determination
#
# A correct report may legitimately discuss BOTH sig_p_reg and sig_q_reg in
# its vulnerable_register (or trigger_scenario) text -- e.g. explaining that
# the recombination stage is symmetric and the other branch register is, in
# principle, equally exposed -- while still clearly designating ONE register
# as the primary/asserted answer. We must not reject such reports merely
# because both identifiers appear as whole-word tokens somewhere in the
# field. Instead we determine which register (if any) is asserted as THE
# answer in an unqualified, primary statement, and treat later mentions of
# the other register as non-disqualifying "color" when introduced by a
# contrastive/explanatory marker or otherwise not asserted with equal
# certainty.
# ---------------------------------------------------------------------------

CONTRASTIVE_MARKERS = [
    "note that", "note,", "note:", "note ",
    "also", "similarly", "symmetrically", "in contrast",
    "unlike", "whereas", "by contrast",
]

# Patterns signaling a genuine, unresolved ambiguity between the two
# registers (both asserted as candidates with no primary distinguished).
AMBIGUOUS_PATTERNS = [
    r'\beither\s+sig_[pq]_reg\s+or\s+sig_[pq]_reg\b',
    r'\bcould\s+be\s+either\b',
    r'\bcould\s+be\s+(?:sig_p_reg|sig_q_reg)\s+or\s+(?:sig_p_reg|sig_q_reg)\b',
    r'\b(?:sig_p_reg|sig_q_reg)\s+or\s+(?:sig_p_reg|sig_q_reg)\s+(?:is|are|could\s+be)\s+(?:the\s+)?(?:vulnerable|unverified)\b',
    r'\bnot\s+sure\s+(?:which|whether)\b',
    r'\b(?:unclear|ambiguous)\s+whether\b',
]

# Patterns asserting a specific register as THE unqualified/primary answer.
# The register name may appear before or after the assertion verb.
PRIMARY_ASSERTION_PATTERNS = [
    # "<REG> is the (unverified|vulnerable|faulted|unchecked) ... register"
    r'\b(sig_p_reg|sig_q_reg)\b(?:[^.]{0,80})\bis\s+the\b(?:[^.]{0,60})\b(?:vulnerable|unverified|unchecked|faulted|at-risk|exposed)\b(?:[^.]{0,40})\bregister\b',
    # "the (unverified|vulnerable|...) register is <REG>"
    r'\bthe\b(?:[^.]{0,40})\b(?:vulnerable|unverified|unchecked|faulted|at-risk|exposed)\b(?:[^.]{0,40})\bregister\b(?:[^.]{0,40})\bis\s+(sig_p_reg|sig_q_reg)\b',
    # "<REG> is the register that ..." / "<REG> ... is not re-verified"
    r'\b(sig_p_reg|sig_q_reg)\b(?:[^.]{0,80})\bis\s+not\s+(?:re-?verified|re-?checked|verified|checked)\b',
    r'\b(sig_p_reg|sig_q_reg)\b(?:[^.]{0,120})\bunverified\b',
    r'\b(sig_p_reg|sig_q_reg)\b(?:[^.]{0,120})\bvulnerable\s+register\b',
]


def split_sentences(text):
    if not isinstance(text, str):
        return []
    # Simple sentence splitter on '.', '!', '?', or newline boundaries.
    parts = re.split(r'(?<=[.!?])\s+|\n+', text.strip())
    return [p.strip() for p in parts if p.strip()]


def sentence_has_marker(sentence, markers):
    low = sentence.lower()
    return any(m in low for m in markers)


def determine_primary_register(text):
    """
    Returns (primary_register_or_None, is_ambiguous_bool).

    primary_register_or_None: 'sig_p_reg' / 'sig_q_reg' / None if no
    register could be determined.
    is_ambiguous_bool: True only if the text asserts both registers as
    equally-certain candidates with no primary distinguished.
    """
    if not isinstance(text, str) or not text.strip():
        return None, False

    low_full = text.lower()

    # Step 0: explicit "either X or Q" style ambiguity anywhere in text.
    for pat in AMBIGUOUS_PATTERNS:
        if re.search(pat, low_full):
            return None, True

    sentences = split_sentences(text)

    primary = None
    primary_sentence_idx = None

    # Step 1: scan sentences in order for the first unqualified primary
    # assertion naming one specific register.
    for idx, sent in enumerate(sentences):
        low_sent = sent.lower()
        for pat in PRIMARY_ASSERTION_PATTERNS:
            m = re.search(pat, low_sent, flags=re.IGNORECASE)
            if m:
                reg = m.group(1).lower()
                if reg in VALID_REGISTERS:
                    primary = reg
                    primary_sentence_idx = idx
                    break
        if primary is not None:
            break

    if primary is None:
        # Fallback: if exactly one register name appears anywhere in the
        # text at all (no assertion pattern matched but only one token is
        # mentioned), treat that as the primary by default.
        found = set()
        for reg in VALID_REGISTERS:
            if re.search(r'\b' + re.escape(reg) + r'\b', text):
                found.add(reg)
        if len(found) == 1:
            return next(iter(found)), False
        elif len(found) == 0:
            return None, False
        else:
            # Both mentioned, no assertion structure found at all to
            # distinguish a primary -> ambiguous.
            return None, True

    # Step 2: check whether the OTHER register is later asserted with equal
    #/unqualified certainty (which would make this genuinely ambiguous),
    # or only mentioned in a contrastive/explanatory manner (which is fine).
    other = "sig_q_reg" if primary == "sig_p_reg" else "sig_p_reg"

    for idx, sent in enumerate(sentences):
        if idx <= primary_sentence_idx:
            continue
        low_sent = sent.lower()
        if other not in low_sent:
            continue
        # Other register is mentioned in this later sentence. Determine if
        # it is asserted as THE answer with equal certainty, or just
        # explanatory/contrastive color.
        is_contrastive = sentence_has_marker(sent, CONTRASTIVE_MARKERS)

        asserts_other_as_primary = False
        for pat in PRIMARY_ASSERTION_PATTERNS:
            m = re.search(pat, low_sent, flags=re.IGNORECASE)
            if m and m.group(1).lower() == other:
                asserts_other_as_primary = True
                break

        if asserts_other_as_primary and not is_contrastive:
            # Genuinely asserts the other register as an equally-certain
            # candidate answer, with no contrastive framing -> ambiguous.
            return None, True
        # Otherwise (contrastive marker present, or mention without an
        # unqualified primary-assertion pattern) -> non-disqualifying;
        # keep scanning remaining sentences but do not override primary.

    return primary, False


def extract_msg_in_candidates(text):
    """Extract candidate integer values in [0,142] from text, in order."""
    if not isinstance(text, str):
        return []
    candidates = []
    for m in re.finditer(r'-?\d+', text):
        try:
            v = int(m.group(0))
        except ValueError:
            continue
        if 0 <= v <= 142:
            candidates.append(v)
    return candidates


def run_subprocess(cmd, cwd=None, timeout=30):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    except FileNotFoundError as e:
        return None, "", "TOOL_NOT_FOUND: %s" % str(e)


def build_and_run_fault_sim(msg_in, fault_reg, tmpdir):
    """
    Substitute placeholders in the harness template and run iverilog/vvp.
    Returns (status, info) where status is one of:
      'ok'          -> info is dict with dut_result, dut_done, ref_result, ref_done
      'compile_fail'-> info is stderr text
      'run_fail'    -> info is stderr/stdout text
    """
    try:
        with open(HARNESS_TEMPLATE_PATH, "r") as f:
            template = f.read()
    except FileNotFoundError:
        return "compile_fail", "harness template evaluation/fault_sim_harness.v not found"

    filled = template.replace("<MSG_IN>", str(msg_in)).replace("<FAULT_REG>", fault_reg)

    tb_path = os.path.join(tmpdir, "fault_sim_harness_%s_%d.v" % (fault_reg, msg_in))
    with open(tb_path, "w") as f:
        f.write(filled)

    sim_bin = os.path.join(tmpdir, "sim_%s_%d.vvp" % (fault_reg, msg_in))

    compile_cmd = [
        "iverilog", "-g2005", "-o", sim_bin,
        "inputs/crt_recombine.v",
        "inputs/crt_reference.v",
        tb_path,
    ]
    rc, out, err = run_subprocess(compile_cmd, timeout=30)
    if rc is None:
        return "compile_fail", "iverilog invocation failed: %s" % err
    if rc != 0:
        return "compile_fail", (err or out)[:800]

    run_cmd = ["vvp", sim_bin]
    rc, out, err = run_subprocess(run_cmd, timeout=30)
    if rc is None:
        return "run_fail", "vvp run failed/timed out: %s" % err

    m = re.search(
        r'RESULT\s+dut_result=(\d+)\s+dut_done=(\d+)\s+ref_result=(\d+)\s+ref_done=(\d+)',
        out
    )
    if not m:
        return "run_fail", "could not parse RESULT line; stdout=%r stderr=%r" % (out[:400], err[:400])

    info = {
        "dut_result": int(m.group(1)),
        "dut_done": int(m.group(2)),
        "ref_result": int(m.group(3)),
        "ref_done": int(m.group(4)),
    }
    return "ok", info


def sim_diverges(info):
    return (
        info["dut_done"] == 1
        and info["ref_done"] == 1
        and info["dut_result"] != info["ref_result"]
    )


def run_golden_fixture_regression_check():
    """
    Internal CI regression self-check (per repair notes): confirms
    determine_primary_register() still resolves a representative
    golden-style vulnerable_register value (primary assertion + a later
    contrastive 'Note that ... also symmetrically ...' mention of the
    other register) to the expected primary register, guarding against a
    regression of the golden_rejected false-rejection bug. This does not
    affect the FR3/SR1 scoring markers emitted for the actual submission;
    it is a best-effort internal sanity check printed for diagnostic
    purposes only.
    """
    try:
        with open(GOLDEN_FIXTURE_PATH, "r") as f:
            fixture = json.load(f)
    except Exception as e:
        print("[INFO] golden_fixture regression check skipped: %s" % str(e))
        return

    text = fixture.get("vulnerable_register", "")
    expected = fixture.get("expected_primary_register", "")
    primary, ambiguous = determine_primary_register(text)

    if primary == expected and not ambiguous:
        print("[INFO] golden_fixture regression check: OK (primary=%s)" % primary)
    else:
        print(
            "[INFO] golden_fixture regression check: MISMATCH "
            "(expected=%s, got primary=%s, ambiguous=%s)" % (expected, primary, ambiguous)
        )


def main():
    # --- Step 1: verify input artifacts exist ---
    for path in INPUT_FILES:
        if not os.path.isfile(path):
            setup_fail(path)

    if not os.path.isfile(HARNESS_TEMPLATE_PATH):
        setup_fail(HARNESS_TEMPLATE_PATH)

    # --- Internal regression self-check (diagnostic only, non-scoring) ---
    run_golden_fixture_regression_check()

    # --- Step 2: load submission ---
    if not os.path.isfile(SUBMISSION_PATH):
        print("[TEST] FAIL: SETUP: %s not found" % SUBMISSION_PATH)
        for rid in ["FR1", "FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            results.setdefault(rid, (False, "setup failure: submission not found"))
        ok = emit_all()
        sys.exit(0 if ok else 1)

    raw = None
    try:
        with open(SUBMISSION_PATH, "r") as f:
            raw = f.read()
    except Exception as e:
        record("FR1", False, "could not read submission file: %s" % str(e))

    report = None
    if raw is not None:
        try:
            report = json.loads(raw)
        except Exception as e:
            record("FR1", False, "submission is not valid JSON: %s" % str(e))

    fr1_ok = True
    fr1_reasons = []
    if report is not None:
        if not isinstance(report, dict):
            fr1_ok = False
            fr1_reasons.append("top-level JSON value is not an object")
        else:
            for field in REQUIRED_FIELDS:
                if field not in report:
                    fr1_ok = False
                    fr1_reasons.append("missing field '%s'" % field)
                elif not isinstance(report[field], str):
                    fr1_ok = False
                    fr1_reasons.append("field '%s' is not a string" % field)
                elif len(report[field].strip()) == 0:
                    fr1_ok = False
                    fr1_reasons.append("field '%s' is empty" % field)
    elif "FR1" not in results:
        fr1_ok = False
        fr1_reasons.append("submission JSON failed to parse")

    if "FR1" not in results:
        record("FR1", fr1_ok, "; ".join(fr1_reasons) if fr1_reasons else "")

    # If report is unusable, fail everything downstream cleanly.
    if not isinstance(report, dict):
        for rid in ["FR2", "FR3", "FR4", "SR1", "SR2", "SR3", "SR4"]:
            record(rid, False, "cannot evaluate: submission JSON missing/invalid (see FR1)")
        ok = emit_all()
        sys.exit(0 if ok else 1)

    def get_field(name):
        v = report.get(name, "")
        return v if isinstance(v, str) else ""

    vulnerable_register = get_field("vulnerable_register")
    fault_model = get_field("fault_model")
    trigger_scenario = get_field("trigger_scenario")
    missing_verification_step = get_field("missing_verification_step")
    recommended_fix = get_field("recommended_fix")

    fields_present_and_nonempty = fr1_ok

    # --- Step 3: FR3 / SR1 -- primary register determination & consistency ---
    vr_primary, vr_ambiguous = (None, False)
    trig_primary, trig_ambiguous = (None, False)

    if fields_present_and_nonempty:
        vr_primary, vr_ambiguous = determine_primary_register(vulnerable_register)
        trig_primary, trig_ambiguous = determine_primary_register(trigger_scenario)

    if not fields_present_and_nonempty:
        record("FR3", False, "cannot evaluate: required fields missing/empty (see FR1)")
    else:
        if vr_ambiguous:
            record("FR3", False,
                   "vulnerable_register asserts both sig_p_reg and sig_q_reg as equally-certain "
                   "candidates with no primary register distinguished: %r" % vulnerable_register)
        elif vr_primary is not None:
            record("FR3", True)
        else:
            record("FR3", False,
                   "vulnerable_register does not name sig_p_reg or sig_q_reg as the primary "
                   "unverified branch register: %r" % vulnerable_register)

    if not fields_present_and_nonempty:
        record("SR1", False, "cannot evaluate: required fields missing/empty (see FR1)")
    else:
        if vr_ambiguous or vr_primary is None:
            record("SR1", False,
                   "vulnerable_register does not unambiguously designate a primary register "
                   "(sig_p_reg or sig_q_reg): %r" % vulnerable_register)
        else:
            # Determine the register referenced in trigger_scenario, falling
            # back to a single-token match if primary-assertion patterns
            # don't match there (trigger_scenario prose often just names the
            # register once without an "X is the vulnerable register" style
            # sentence).
            effective_trig_reg = trig_primary
            if effective_trig_reg is None and not trig_ambiguous:
                found = set()
                for reg in VALID_REGISTERS:
                    if re.search(r'\b' + re.escape(reg) + r'\b', trigger_scenario):
                        found.add(reg)
                if len(found) == 1:
                    effective_trig_reg = next(iter(found))

            if trig_ambiguous:
                record("SR1", False,
                       "trigger_scenario names both branch registers with no primary target "
                       "distinguished, inconsistent with vulnerable_register=%s" % vr_primary)
            elif effective_trig_reg is None:
                record("SR1", False,
                       "trigger_scenario does not name any branch register consistent with "
                       "vulnerable_register=%s" % vr_primary)
            elif effective_trig_reg == vr_primary:
                record("SR1", True)
            else:
                record("SR1", False,
                       "trigger_scenario's primary fault target (%s) is inconsistent with "
                       "vulnerable_register's primary register (%s)" % (effective_trig_reg, vr_primary))

    # --- Step 4: FR2 / SR4 -- reproducible trigger scenario via simulation ---
    if not fields_present_and_nonempty:
        record("FR2", False, "cannot evaluate: required fields missing/empty (see FR1)")
        record("SR4", False, "cannot evaluate: required fields missing/empty (see FR1)")
    else:
        # Determine which register(s) to try forcing: prefer the SR1-
        # consistent primary register, else whichever single register
        # trigger_scenario names, else whichever vulnerable_register names.
        candidate_regs = []
        if vr_primary is not None and not vr_ambiguous:
            candidate_regs.append(vr_primary)
        if trig_primary is not None and trig_primary not in candidate_regs:
            candidate_regs.append(trig_primary)
        if not trig_ambiguous:
            found = set()
            for reg in VALID_REGISTERS:
                if re.search(r'\b' + re.escape(reg) + r'\b', trigger_scenario):
                    found.add(reg)
            for r in sorted(found):
                if r not in candidate_regs:
                    candidate_regs.append(r)

        if not candidate_regs:
            candidate_regs = list(VALID_REGISTERS)  # last resort try both

        msg_candidates = extract_msg_in_candidates(trigger_scenario)
        fallback_vectors = [5, 77, 142, 0, 100]
        vectors_to_try = msg_candidates if msg_candidates else []

        tried = []
        sim_ok_result = None
        compile_errors = []
        run_errors = []

        with tempfile.TemporaryDirectory() as tmpdir:
            attempts = []
            for reg in candidate_regs:
                for mv in vectors_to_try:
                    attempts.append((mv, reg))
            if not attempts:
                for reg in candidate_regs:
                    for mv in fallback_vectors:
                        attempts.append((mv, reg))

            for (mv, reg) in attempts:
                tried.append((mv, reg))
                status, info = build_and_run_fault_sim(mv, reg, tmpdir)
                if status == "compile_fail":
                    compile_errors.append((mv, reg, info))
                    continue
                if status == "run_fail":
                    run_errors.append((mv, reg, info))
                    continue
                if sim_diverges(info):
                    sim_ok_result = (mv, reg, info)
                    break

            if sim_ok_result is None and vectors_to_try:
                for reg in candidate_regs:
                    for mv in fallback_vectors:
                        if (mv, reg) in tried:
                            continue
                        tried.append((mv, reg))
                        status, info = build_and_run_fault_sim(mv, reg, tmpdir)
                        if status == "compile_fail":
                            compile_errors.append((mv, reg, info))
                            continue
                        if status == "run_fail":
                            run_errors.append((mv, reg, info))
                            continue
                        if sim_diverges(info):
                            sim_ok_result = (mv, reg, info)
                            break
                    if sim_ok_result is not None:
                        break

        no_msg = not msg_candidates
        no_reg_hint = (vr_primary is None and trig_primary is None
                       and not any(re.search(r'\b' + re.escape(r) + r'\b', trigger_scenario) for r in VALID_REGISTERS))

        if no_msg and no_reg_hint:
            reason = ("trigger_scenario does not contain a parsable msg_in value "
                       "(0-142) or a named register (sig_p_reg/sig_q_reg)")
            record("FR2", False, reason)
            record("SR4", False, reason)
        elif sim_ok_result is not None:
            record("FR2", True)
            record("SR4", True)
        else:
            if compile_errors:
                mv, reg, err = compile_errors[0]
                reason = "compile failed for msg_in=%s reg=%s: %s" % (mv, reg, err[:400])
            elif run_errors:
                mv, reg, err = run_errors[0]
                reason = "simulation run failed for msg_in=%s reg=%s: %s" % (mv, reg, err[:400])
            else:
                reason = ("no attempted (msg_in, register) combination from trigger_scenario "
                          "reproduced a divergence with done asserted in both dut and reference; "
                          "tried: %s" % tried[:10])
            record("FR2", False, reason)
            record("SR4", False, reason)

    # --- Step 5: FR4 / SR3 -- recompute-and-compare fix semantics ---
    RECOMPUTE_PATTERNS = [
        r'\brecompute\b',
        r'\brecomput\w*',
        r'\bredundan\w*',
        r'\bcross[- ]?check\w*',
        r'\bcross[- ]?verif\w*',
        r'\bindependent(?:ly)?\s+(?:comput|recomput|verif|check)\w*',
        r'\bcompare\w*\s+(?:the\s+)?(?:two\s+)?(?:branch|result|sig_p_reg|sig_q_reg|partial)',
        r'\bconsisten\w*\s+check\w*',
        r'\bdual[- ]?comput\w*',
        r'\bsecond\s+(?:independent\s+)?comput\w*\s+path',
        r'\bre-?verif\w*\s+(?:the\s+)?(?:branch|result|register)',
        r'\bverify\s+(?:the\s+)?(?:branch|result)s?\s+(?:against|before)',
        r'\bmatch\w*\s+(?:the\s+)?(?:two\s+)?branch\w*\s+result',
    ]

    GENERIC_ONLY_PATTERNS = [
        r'\bparity\b',
        r'\bchecksum\b',
        r'\bcrc\b',
        r'\bwatchdog\b',
        r'\btimeout\b',
        r'\becc\b',
        r'\berror[- ]correcting\s+code\b',
    ]

    def has_recompute_semantics(text):
        if not isinstance(text, str):
            return False
        low = text.lower()
        for pat in RECOMPUTE_PATTERNS:
            if re.search(pat, low):
                return True
        return False

    def only_generic_no_recompute(text):
        if not isinstance(text, str) or len(text.strip()) == 0:
            return False
        low = text.lower()
        has_generic = any(re.search(pat, low) for pat in GENERIC_ONLY_PATTERNS)
        has_recompute = has_recompute_semantics(text)
        return has_generic and not has_recompute

    if not fields_present_and_nonempty:
        record("FR4", False, "cannot evaluate: required fields missing/empty (see FR1)")
        record("SR3", False, "cannot evaluate: required fields missing/empty (see FR1)")
    else:
        fix_has_recompute = has_recompute_semantics(recommended_fix)
        step_has_recompute = has_recompute_semantics(missing_verification_step)
        combined_has_recompute = fix_has_recompute or step_has_recompute

        fix_only_generic = only_generic_no_recompute(recommended_fix)

        if fix_has_recompute and not fix_only_generic:
            record("FR4", True)
        elif fix_only_generic:
            record("FR4", False,
                   "recommended_fix proposes only generic/unrelated mitigation "
                   "(e.g. parity/CRC/watchdog) without recompute-and-compare semantics: %r" % recommended_fix)
        else:
            record("FR4", False,
                   "recommended_fix does not describe a concrete recompute/redundant/cross-check "
                   "countermeasure: %r" % recommended_fix)

        if combined_has_recompute:
            record("SR3", True)
        else:
            record("SR3", False,
                   "neither missing_verification_step nor recommended_fix expresses "
                   "recompute-and-compare / independent cross-check semantics")

    # --- Step 6: SR2 -- fault model semantics ---
    SINGLE_TRANSIENT_PATTERNS = [
        r'\bbit[- ]?flip\w*',
        r'\btransient\w*',
        r'\bsingle[- ]event[- ]upset\b',
        r'\bseu\b',
        r'\bglitch\w*',
        r'\bstuck[- ]at\b',
        r'\bstuck\s+value\b',
        r'\bforced?\s+value\b',
        r'\bforc\w*\s+(?:the\s+)?(?:register|sig_p_reg|sig_q_reg)',
        r'\bsingle\s+register\b',
        r'\bone\s+register\b',
        r'\bcorrupt\w*\s+(?:one|a|the)\s+register\b',
        r'\bvoltage\s+glitch\b',
        r'\bclock\s+glitch\b',
        r'\blaser\b',
        r'\bem\s+pulse\b',
        r'\bfault\s+injection\b',
    ]

    MULTI_BRANCH_REQUIRED_PATTERNS = [
        r'\bboth\s+(?:branch\w*|register\w*|sig_p_reg\s+and\s+sig_q_reg)\s+(?:must|need|are)\s+(?:be\s+)?(?:fault\w*|corrupt\w*|flip\w*)',
        r'\brequires?\s+(?:two|multiple|both)\s+(?:simultaneous\s+)?faults',
        r'\bsimultaneous(?:ly)?\s+fault\w*\s+(?:both|two)\b',
    ]

    def has_single_transient_semantics(text):
        if not isinstance(text, str):
            return False
        low = text.lower()
        for pat in SINGLE_TRANSIENT_PATTERNS:
            if re.search(pat, low):
                return True
        return False

    def requires_multi_branch_fault(text):
        if not isinstance(text, str):
            return False
        low = text.lower()
        for pat in MULTI_BRANCH_REQUIRED_PATTERNS:
            if re.search(pat, low):
                return True
        return False

    if not fields_present_and_nonempty:
        record("SR2", False, "cannot evaluate: required fields missing/empty (see FR1)")
    else:
        if requires_multi_branch_fault(fault_model):
            record("SR2", False,
                   "fault_model describes a requirement for simultaneous multi-branch faults, "
                   "inconsistent with the single-transient-register Bellcore fault model: %r" % fault_model)
        elif has_single_transient_semantics(fault_model):
            record("SR2", True)
        else:
            record("SR2", False,
                   "fault_model does not describe single-register transient/bit-flip/glitch-style "
                   "corruption consistent with a Bellcore-style fault: %r" % fault_model)

    ok = emit_all()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()