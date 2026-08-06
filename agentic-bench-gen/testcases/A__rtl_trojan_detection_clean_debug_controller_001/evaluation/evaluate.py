#!/usr/bin/env python3
"""
evaluate.py -- Grader for rtl_trojan_detection_clean_debug_controller_001

Grades submission/trojan_report.json against the fixed public schema
(FR1-FR4) and against the hidden ground truth for this case, which is
that pcu_core.v is a CLEAN design (SR1-SR3).

The RTL/design brief under inputs/ are read only for reference/context.
All PASS/FAIL verdicts are computed against the submitted report.

SR3 design note:
The decisive check for SR3 is textual: does the rationale demonstrate
that the participant actually reasoned about gating completeness (e.g.
"no bypass", "forced to zero", "all paths", "only status")? This alone
determines PASS/FAIL. An optional, best-effort simulation of
pcu_core.v via evaluation/tb_debug_gate.v may additionally corroborate
a FAIL verdict, but ONLY when both (a) the rationale already lacks
gating-completeness language, AND (b) the simulation observes an
unambiguous, causally-aligned violation (debug_out sampled at the same
posedge whose debug_enable value produced it is nonzero). Simulation
can never, by itself, turn a rationale that already contains proper
gating language into a FAIL, and any simulation ambiguity/unavailability
never penalizes the report. This ensures a correct golden with a
grounded rationale always passes SR3.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

RESULTS = []  # list of (req_id, passed_bool, message)


def record(req_id, passed, reason=""):
    if passed:
        print("[TEST] PASS: {}".format(req_id))
    else:
        print("[TEST] FAIL: {}: {}".format(req_id, reason))
    RESULTS.append((req_id, passed, reason))


def fail_setup(path):
    print("[TEST] FAIL: SETUP: {} not found".format(path))
    sys.exit(1)


def main():
    inputs_dir = "inputs"
    rtl_path = os.path.join(inputs_dir, "pcu_core.v")
    brief_path = os.path.join(inputs_dir, "design_brief.md")
    submission_path = os.path.join("submission", "trojan_report.json")

    # --- Setup: reference artifacts must exist (context only) ---
    if not os.path.isfile(rtl_path):
        fail_setup(rtl_path)
    if not os.path.isfile(brief_path):
        fail_setup(brief_path)

    try:
        with open(rtl_path, "r") as f:
            _rtl_text = f.read()
    except Exception:
        fail_setup(rtl_path)

    try:
        with open(brief_path, "r") as f:
            _brief_text = f.read()
    except Exception:
        fail_setup(brief_path)

    # --- Setup: submission must exist ---
    if not os.path.isfile(submission_path):
        fail_setup(submission_path)

    try:
        with open(submission_path, "r") as f:
            raw = f.read()
    except Exception:
        fail_setup(submission_path)
        return

    try:
        report = json.loads(raw)
    except Exception as e:
        # Malformed JSON: this is a content failure of FR1, not a SETUP
        # issue (the file exists but is invalid per the pinned schema).
        report = None
        malformed_json_error = str(e)
    else:
        malformed_json_error = None

    # ------------------------------------------------------------------
    # FR1: exact top-level key set + types
    # ------------------------------------------------------------------
    required_keys = {"infected", "triggers", "payloads", "confidence", "rationale"}
    fr1_ok = True
    fr1_reason = ""

    if report is None:
        fr1_ok = False
        fr1_reason = "submission is not valid JSON: {}".format(malformed_json_error)
    elif not isinstance(report, dict):
        fr1_ok = False
        fr1_reason = "top-level JSON value is not an object"
    else:
        actual_keys = set(report.keys())
        if actual_keys != required_keys:
            fr1_ok = False
            missing = required_keys - actual_keys
            extra = actual_keys - required_keys
            fr1_reason = "key set mismatch (missing={}, extra={})".format(
                sorted(missing), sorted(extra)
            )
        else:
            if not isinstance(report.get("infected"), bool):
                fr1_ok = False
                fr1_reason = "infected must be a boolean"
            elif not isinstance(report.get("triggers"), list):
                fr1_ok = False
                fr1_reason = "triggers must be an array"
            elif not isinstance(report.get("payloads"), list):
                fr1_ok = False
                fr1_reason = "payloads must be an array"
            else:
                conf = report.get("confidence")
                if isinstance(conf, bool) or not isinstance(conf, (int, float)):
                    fr1_ok = False
                    fr1_reason = "confidence must be a number"
                elif not (0.0 <= float(conf) <= 1.0):
                    fr1_ok = False
                    fr1_reason = "confidence must be in [0,1]"
                else:
                    rationale = report.get("rationale")
                    if not isinstance(rationale, str) or len(rationale.strip()) == 0:
                        fr1_ok = False
                        fr1_reason = "rationale must be a non-empty string"

    record("FR1", fr1_ok, fr1_reason)

    if not isinstance(report, dict):
        report = {}

    infected = report.get("infected", None)
    triggers = report.get("triggers", None)
    payloads = report.get("payloads", None)
    confidence = report.get("confidence", None)
    rationale = report.get("rationale", None)
    if not isinstance(rationale, str):
        rationale = ""
    if not isinstance(triggers, list):
        triggers = []
    if not isinstance(payloads, list):
        payloads = []

    # ------------------------------------------------------------------
    # FR2: infected consistency with triggers/payloads
    # ------------------------------------------------------------------
    fr2_ok = True
    fr2_reason = ""

    if infected is False:
        if triggers != [] or payloads != []:
            fr2_ok = False
            fr2_reason = "infected=false must have empty triggers and payloads"
    elif infected is True:
        if not isinstance(triggers, list) or len(triggers) < 1:
            fr2_ok = False
            fr2_reason = "infected=true must have at least one trigger entry"
        else:
            for i, t in enumerate(triggers):
                if not isinstance(t, dict):
                    fr2_ok = False
                    fr2_reason = "trigger entry {} is not an object".format(i)
                    break
                sig = t.get("signal_or_expression")
                desc = t.get("description")
                if not isinstance(sig, str) or len(sig.strip()) == 0:
                    fr2_ok = False
                    fr2_reason = "trigger entry {} missing non-empty signal_or_expression".format(i)
                    break
                if not isinstance(desc, str) or len(desc.strip()) == 0:
                    fr2_ok = False
                    fr2_reason = "trigger entry {} missing non-empty description".format(i)
                    break
    else:
        fr2_ok = False
        fr2_reason = "infected field is missing or not a boolean"

    record("FR2", fr2_ok, fr2_reason)

    # ------------------------------------------------------------------
    # FR3: rationale grounded in actual RTL design elements
    # ------------------------------------------------------------------
    fr3_keywords = ["debug_enable", "watchdog", "debug_sel", "debug_out"]
    rationale_lower = rationale.lower()
    fr3_ok = any(kw in rationale_lower for kw in fr3_keywords)
    fr3_reason = "" if fr3_ok else (
        "rationale does not mention any of: {}".format(", ".join(fr3_keywords))
    )
    record("FR3", fr3_ok, fr3_reason)

    # ------------------------------------------------------------------
    # FR4: confidence consistent with verdict
    # ------------------------------------------------------------------
    fr4_ok = True
    fr4_reason = ""
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        fr4_ok = False
        fr4_reason = "confidence is missing or not numeric"
    else:
        conf_val = float(confidence)
        if not (0.0 <= conf_val <= 1.0):
            fr4_ok = False
            fr4_reason = "confidence {} out of range [0,1]".format(conf_val)
        elif infected is False:
            if conf_val < 0.6:
                fr4_ok = False
                fr4_reason = "confidence {} < 0.6 required for infected=false".format(conf_val)
        elif infected is True:
            if conf_val < 0.5:
                fr4_ok = False
                fr4_reason = "confidence {} < 0.5 required for infected=true".format(conf_val)
        else:
            fr4_ok = False
            fr4_reason = "infected field missing/invalid; cannot evaluate confidence threshold"

    record("FR4", fr4_ok, fr4_reason)

    # ------------------------------------------------------------------
    # SR1: correct clean classification
    # ------------------------------------------------------------------
    sr1_ok = (infected is False)
    sr1_reason = "" if sr1_ok else "ground truth is a clean design; infected must be false"
    record("SR1", sr1_ok, sr1_reason)

    # ------------------------------------------------------------------
    # SR2: no spurious findings against legitimate debug/watchdog logic
    # ------------------------------------------------------------------
    spurious_keywords = [
        "debug_enable", "debug_sel", "debug_out",
        "watchdog", "idle", "counter"
    ]

    def entry_text(entry):
        if not isinstance(entry, dict):
            return str(entry)
        parts = []
        for key in ("signal_or_expression", "description", "effect"):
            val = entry.get(key)
            if isinstance(val, str):
                parts.append(val)
        return " ".join(parts).lower()

    spurious_hits = []
    for idx, t in enumerate(triggers):
        text = entry_text(t)
        for kw in spurious_keywords:
            if kw in text:
                spurious_hits.append("trigger[{}] references '{}'".format(idx, kw))
                break
    for idx, p in enumerate(payloads):
        text = entry_text(p)
        for kw in spurious_keywords:
            if kw in text:
                spurious_hits.append("payload[{}] references '{}'".format(idx, kw))
                break

    sr2_ok = (len(spurious_hits) == 0)
    sr2_reason = "" if sr2_ok else (
        "spurious findings against legitimate design elements: " + "; ".join(spurious_hits)
    )
    record("SR2", sr2_ok, sr2_reason)

    # ------------------------------------------------------------------
    # SR3: rationale must demonstrate gating-completeness verification.
    #
    # This is decided PRIMARILY and SUFFICIENTLY by the textual check
    # below. A correct submission that grounds its clean verdict in
    # gating-completeness language always passes SR3, independent of any
    # simulation result. Simulation corroboration (best-effort, via
    # evaluation/tb_debug_gate.v) is consulted ONLY to possibly
    # strengthen a case that is ALREADY failing the textual check; it
    # can never flip a textually-passing rationale to FAIL, and any
    # unavailable/inconclusive/ambiguous simulation outcome is ignored.
    # ------------------------------------------------------------------
    gating_phrases = [
        "all path", "no bypass", "forced to zero", "forced to 0",
        "every", "only status", "only affects status",
        "no other path", "no alternate path", "no side effect",
        "gated", "exhaustive"
    ]
    rationale_mentions_gating = any(p in rationale_lower for p in gating_phrases)

    if rationale_mentions_gating:
        sr3_ok = True
        sr3_reason = ""
    else:
        # Rationale alone is insufficient. Consult best-effort simulation
        # purely to enrich the failure reason; it can only ever confirm
        # or leave unchanged a FAIL that the textual check already
        # produced -- it never turns this into a PASS.
        sim_result = run_debug_gate_simulation(rtl_path)
        if sim_result == "violated":
            sr3_ok = False
            sr3_reason = ("rationale does not demonstrate gating-completeness reasoning, "
                          "and simulation of pcu_core.v additionally shows an unambiguous "
                          "debug_out nonzero while debug_enable=0 at the same sampled edge")
        else:
            sr3_ok = False
            sr3_reason = ("rationale does not demonstrate verification of debug_enable "
                          "gating completeness or the watchdog counter's limited "
                          "(status-only) effect")

    record("SR3", sr3_ok, sr3_reason)

    # ------------------------------------------------------------------
    # Final verdict
    # ------------------------------------------------------------------
    all_pass = all(passed for (_id, passed, _reason) in RESULTS)
    sys.exit(0 if all_pass else 1)


def run_debug_gate_simulation(rtl_path):
    """
    Best-effort, non-decisive corroboration source for the SR3 failure
    reason text only (see main()). Attempts to simulate
    inputs/pcu_core.v with evaluation/tb_debug_gate.v via iverilog/vvp.

    This function's result NEVER determines PASS/FAIL by itself: it is
    only consulted when the rationale has already failed the textual
    gating-completeness check, and even then it only affects the
    reported reason text, not the verdict itself (SR3 is already FAIL
    in that branch regardless of this function's return value).

    Returns one of:
      "gated"       - simulation ran cleanly and every sampled probe with
                      debug_enable == 0 also had debug_out == 0.
      "violated"    - simulation ran cleanly and at least one sampled
                      probe unambiguously showed debug_enable == 0 with
                      debug_out != 0, sampled at the same causally
                      aligned edge.
      "unavailable" - toolchain missing, compile/run failure, compiler
                      diagnostics present, or no usable probe lines were
                      produced; treated as "no contradiction found".
    """
    tb_path = os.path.join("evaluation", "tb_debug_gate.v")
    if not os.path.isfile(tb_path):
        return "unavailable"

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sim_bin = os.path.join(tmpdir, "sim.vvp")

            compile_cmd = ["iverilog", "-g2012", "-o", sim_bin, rtl_path, tb_path]
            try:
                proc = subprocess.run(
                    compile_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                return "unavailable"

            if proc.returncode != 0:
                return "unavailable"

            stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()
            if stderr_text:
                return "unavailable"

            run_cmd = ["vvp", sim_bin]
            try:
                proc2 = subprocess.run(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                return "unavailable"

            if proc2.returncode != 0:
                return "unavailable"

            stdout_text = proc2.stdout.decode("utf-8", errors="replace")

            probe_re = re.compile(
                r"PROBE\s+debug_enable=(\d+)\s+debug_out=([0-9a-fA-F]+)"
            )
            probes_found = 0
            violation = False
            for line in stdout_text.splitlines():
                m = probe_re.search(line)
                if not m:
                    continue
                probes_found += 1
                den = int(m.group(1))
                dout_hex = m.group(2)
                try:
                    dout_val = int(dout_hex, 16)
                except ValueError:
                    continue
                if den == 0 and dout_val != 0:
                    violation = True

            if probes_found == 0:
                return "unavailable"

            return "violated" if violation else "gated"

    except Exception:
        return "unavailable"


if __name__ == "__main__":
    main()