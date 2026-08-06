"""
evaluation/private/analysis.py

Private grading logic for the power side-channel leakage localization task.
This module is imported by evaluation/evaluate.py and is NOT participant
facing. It re-simulates the fixed RTL/testbench pair shipped under inputs/
to recompute ground-truth Hamming-distance variance per register (per the
formula in inputs/power_model.md), and grades a submitted
vulnerability_report.json against both structural (FR) and substantive (SR)
requirements.
"""

import os
import re
import subprocess
import tempfile

# ---------------------------------------------------------------------------
# Constants derived from the fixed input RTL (inputs/round_datapath.v) and
# the design brief (inputs/design_brief.md). These identify the roles of the
# four pipeline registers for grading purposes; participants are not shown
# this role mapping directly (they must discover it via their own analysis).
# ---------------------------------------------------------------------------

PLAINTEXT_SIG = "plaintext_reg"   # registered raw plaintext, pre key-mix (non-leaky reference)
KEYMIX_SIG = "key_mix_reg"        # registers plaintext_reg XOR round_key (leaky)
SBOX_SIG = "sbox_out_reg"         # registers sbox_lut(key_mix_reg) (leaky)
ROUNDOUT_SIG = "round_out_reg"    # registers balanced diffusion of sbox_out_reg (non-leaky reference)

ALLOWED_TECHNIQUE_KEYWORDS = [
    "mask",
    "dual-rail",
    "dual rail",
    "precharge",
    "isolat",
    "hid",
    "blind",
]

# Ground-truth cross-check is intentionally an order-of-magnitude sanity
# band rather than a tight percentage tolerance. power_model.md permits a
# compliant analyst to make documented methodological choices about how
# consecutive-cycle transitions in the printed trace are aggregated (e.g.
# whether inter-vector boundary transitions are windowed identically to
# intra-vector settle transitions), so a correct submission's absolute
# hd_variance numbers may legitimately diverge substantially from this
# evaluator's own single recomputation while still correctly ranking and
# flagging every signal. GT_RATIO_FACTOR bounds how wildly off a submitted
# number may be from this evaluator's recomputation before it is treated as
# fabricated/incorrect rather than merely following a different (but valid)
# aggregation convention.
GT_RATIO_FACTOR = 5.0

SR1_RATIO_MIN = 1.3       # key_mix_reg hd_variance must be >= this multiple of plaintext_reg's

# Module-level cache: {abspath(input_dir): {signal_name: hd_variance}}
_GT_CACHE = {}


# ---------------------------------------------------------------------------
# RTL parsing helpers
# ---------------------------------------------------------------------------

def parse_register_names(path):
    """
    Parse inputs/round_datapath.v and return the list of internal register
    names (declaration order) of the form `reg [W:0] NAME;`, excluding any
    line that also mentions 'input' or 'output' (i.e. excluding module port
    declarations, even if a port happens to be declared with a 'reg' type).
    Raises ValueError if fewer than 4 such registers are found.
    """
    with open(path, "r") as f:
        text = f.read()

    names = []
    reg_decl_re = re.compile(r'^\s*reg\s*\[\s*\d+\s*:\s*\d+\s*\]\s*(\w+)\s*;')
    for line in text.splitlines():
        stripped = line.strip()
        if "input" in stripped or "output" in stripped:
            continue
        m = reg_decl_re.match(stripped)
        if m:
            names.append(m.group(1))

    if len(names) < 4:
        raise ValueError(
            "fewer than 4 internal register declarations found in %s (found: %s)"
            % (path, names)
        )
    return names


# ---------------------------------------------------------------------------
# Power model math (mirrors inputs/power_model.md exactly)
# ---------------------------------------------------------------------------

def popcount(x):
    return bin(x).count("1")


def sample_variance(values):
    """
    Bessel-corrected sample variance of a list of HD samples.
    Returns 0.0 if fewer than 2 samples, matching power_model.md.
    """
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / float(n)
    ss = sum((v - mean) ** 2 for v in values)
    return ss / float(n - 1)


def _within_order_of_magnitude(submitted, truth, factor=GT_RATIO_FACTOR):
    """
    Permissive band check: PASS iff submitted is within `factor`-x of truth
    (as a ratio, in either direction), or, when truth is effectively zero,
    submitted is itself small in absolute terms (<= factor). This tolerates
    any spec-compliant aggregation methodology while still rejecting
    fabricated or wildly-wrong numbers.
    """
    try:
        submitted = float(submitted)
        truth = float(truth)
    except (TypeError, ValueError):
        return False

    if truth <= 1e-9:
        return abs(submitted) <= factor

    lower = truth / factor
    upper = truth * factor
    return lower <= submitted <= upper


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

_TRACE_COLUMNS = ["plaintext_reg", "key_mix_reg", "sbox_out_reg", "round_out_reg"]
_HEADER_LEN = 7  # cycle,plaintext,round_key,plaintext_reg,key_mix_reg,sbox_out_reg,round_out_reg


def run_simulation(input_dir, timeout=30):
    """
    Compile and run the fixed RTL + testbench from input_dir via
    iverilog/vvp, and parse the printed CSV trace into a dict mapping each
    of the 4 pipeline register names to an ordered list of ints (cycle
    order). Raises RuntimeError on any build/run failure.
    """
    tmpdir = tempfile.mkdtemp(prefix="sca_eval_")
    sim_path = os.path.join(tmpdir, "sim.vvp")

    rtl_files = [
        os.path.join(input_dir, "round_datapath.v"),
        os.path.join(input_dir, "sbox_table.v"),
        os.path.join(input_dir, "testbench_hd_trace.v"),
    ]

    compile_cmd = ["iverilog", "-o", sim_path] + rtl_files
    try:
        compile_proc = subprocess.run(
            compile_cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("iverilog compile timed out: %s" % exc)
    except OSError as exc:
        raise RuntimeError("could not invoke iverilog: %s" % exc)

    if compile_proc.returncode != 0:
        raise RuntimeError(
            "iverilog compile failed (rc=%d): stdout=%r stderr=%r"
            % (compile_proc.returncode, compile_proc.stdout, compile_proc.stderr)
        )

    try:
        run_proc = subprocess.run(
            ["vvp", sim_path], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("vvp simulation timed out: %s" % exc)
    except OSError as exc:
        raise RuntimeError("could not invoke vvp: %s" % exc)

    if run_proc.returncode != 0:
        raise RuntimeError(
            "vvp simulation failed (rc=%d): stdout=%r stderr=%r"
            % (run_proc.returncode, run_proc.stdout, run_proc.stderr)
        )

    columns = {name: [] for name in _TRACE_COLUMNS}

    for line in run_proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != _HEADER_LEN:
            continue
        try:
            ints = [int(p.strip()) for p in parts]
        except ValueError:
            # Header line or other non-numeric noise; skip.
            continue
        # ints layout: cycle, plaintext, round_key, plaintext_reg, key_mix_reg,
        # sbox_out_reg, round_out_reg
        for idx, name in enumerate(_TRACE_COLUMNS, start=3):
            columns[name].append(ints[idx])

    for name in _TRACE_COLUMNS:
        if len(columns[name]) < 2:
            raise RuntimeError(
                "insufficient simulation samples for %s (got %d)"
                % (name, len(columns[name]))
            )

    return columns


def compute_ground_truth(input_dir):
    """
    Re-simulate the fixed RTL/testbench and compute hd_variance for each of
    the 4 pipeline registers, per the exact formula in power_model.md.
    Result is cached per input_dir to avoid repeated iverilog/vvp
    invocations within a single evaluate.py run.
    """
    key = os.path.abspath(input_dir)
    if key in _GT_CACHE:
        return _GT_CACHE[key]

    columns = run_simulation(input_dir)

    result = {}
    for name, values in columns.items():
        hd_samples = [
            popcount(values[i] ^ values[i + 1]) for i in range(len(values) - 1)
        ]
        result[name] = sample_variance(hd_samples)

    _GT_CACHE[key] = result
    return result


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def check_schema(submission):
    """
    Validate the top-level structure of a submitted vulnerability_report.
    Returns (ok, reason, signals_by_name, recommendations).
    On failure, signals_by_name and recommendations are None.
    """
    if not isinstance(submission, dict):
        return False, "submission is not a JSON object", None, None

    if "signals" not in submission:
        return False, "missing top-level 'signals' key", None, None
    if "recommendations" not in submission:
        return False, "missing top-level 'recommendations' key", None, None

    signals = submission["signals"]
    recommendations = submission["recommendations"]

    if not isinstance(signals, list):
        return False, "'signals' is not an array", None, None
    if not isinstance(recommendations, list):
        return False, "'recommendations' is not an array", None, None

    signals_by_name = {}
    for i, entry in enumerate(signals):
        if not isinstance(entry, dict):
            return False, "signals[%d] is not an object" % i, None, None

        if "signal_name" not in entry:
            return False, "signals[%d] missing signal_name" % i, None, None
        sig_name = entry["signal_name"]
        if not isinstance(sig_name, str):
            return False, "signals[%d].signal_name is not a string" % i, None, None

        if "hd_variance" not in entry:
            return False, "signals[%d] (%s) missing hd_variance" % (i, sig_name), None, None
        hd_val = entry["hd_variance"]
        if isinstance(hd_val, bool) or not isinstance(hd_val, (int, float)):
            return False, "hd_variance for %s is not numeric" % sig_name, None, None

        if "flagged" not in entry:
            return False, "signals[%d] (%s) missing flagged" % (i, sig_name), None, None
        if not isinstance(entry["flagged"], bool):
            return False, "flagged for %s is not boolean" % sig_name, None, None

        signals_by_name[sig_name] = entry

    for i, rec in enumerate(recommendations):
        if not isinstance(rec, dict):
            return False, "recommendations[%d] is not an object" % i, None, None
        for field in ("target_signal", "technique", "rationale"):
            if field not in rec:
                return False, "recommendations[%d] missing %s" % (i, field), None, None
            if not isinstance(rec[field], str):
                return (
                    False,
                    "recommendations[%d].%s is not a string" % (i, field),
                    None,
                    None,
                )

    return True, "", signals_by_name, recommendations


# ---------------------------------------------------------------------------
# Requirement checks
# ---------------------------------------------------------------------------

def check_fr1(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, _ = check_schema(submission)
        if not ok:
            return False, reason

        rtl_path = os.path.join(input_dir, "round_datapath.v")
        try:
            reg_names = parse_register_names(rtl_path)
        except Exception as exc:
            return False, "could not parse register names from %s: %s" % (rtl_path, exc)

        missing = [n for n in reg_names if n not in signals_by_name]
        if missing:
            return False, "signals array missing entries for: %s" % ", ".join(missing)

        return True, ""
    except (KeyError, TypeError) as exc:
        return False, "%s missing or malformed" % exc


def check_fr2(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, _ = check_schema(submission)
        if not ok:
            return False, reason

        if gt is None:
            return False, "simulation failed: ground truth unavailable"

        if PLAINTEXT_SIG not in signals_by_name:
            return False, "%s missing or malformed" % PLAINTEXT_SIG

        entry = signals_by_name[PLAINTEXT_SIG]
        submitted = float(entry["hd_variance"])
        truth = float(gt[PLAINTEXT_SIG])

        if not _within_order_of_magnitude(submitted, truth):
            return False, (
                "hd_variance for %s = %s not within order-of-magnitude band (factor %.1f) of ground truth %s"
                % (PLAINTEXT_SIG, submitted, GT_RATIO_FACTOR, truth)
            )
        return True, ""
    except (KeyError, TypeError, ValueError) as exc:
        return False, "%s field missing or malformed" % exc


def check_fr3(submission, gt, input_dir="inputs"):
    try:
        ok, reason, _, _ = check_schema(submission)
        return ok, reason
    except (KeyError, TypeError) as exc:
        return False, "%s missing or malformed" % exc


def check_fr4(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, recommendations = check_schema(submission)
        if not ok:
            return False, reason

        for i, rec in enumerate(recommendations):
            target = rec.get("target_signal")
            if target not in signals_by_name:
                return False, (
                    "recommendations[%d] references unknown signal '%s'" % (i, target)
                )
        return True, ""
    except (KeyError, TypeError) as exc:
        return False, "%s missing or malformed" % exc


def check_sr1(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, _ = check_schema(submission)
        if not ok:
            return False, reason

        if gt is None:
            return False, "simulation failed: ground truth unavailable"

        if KEYMIX_SIG not in signals_by_name:
            return False, "%s missing or malformed" % KEYMIX_SIG
        if PLAINTEXT_SIG not in signals_by_name:
            return False, "%s missing or malformed" % PLAINTEXT_SIG

        keymix_entry = signals_by_name[KEYMIX_SIG]
        plaintext_entry = signals_by_name[PLAINTEXT_SIG]

        flagged = keymix_entry["flagged"]
        submitted_hd = float(keymix_entry["hd_variance"])
        plaintext_hd = float(plaintext_entry["hd_variance"])

        if not flagged:
            return False, "%s not flagged as leaking (flagged=false)" % KEYMIX_SIG

        truth = gt.get(KEYMIX_SIG)
        if truth is None:
            return False, "simulation failed: no ground truth for %s" % KEYMIX_SIG

        if not _within_order_of_magnitude(submitted_hd, truth):
            return False, (
                "%s hd_variance %s not within order-of-magnitude band (factor %.1f) of ground truth %s"
                % (KEYMIX_SIG, submitted_hd, GT_RATIO_FACTOR, truth)
            )

        if plaintext_hd <= 0:
            if submitted_hd <= 0:
                return False, (
                    "%s hd_variance not substantially higher than %s"
                    % (KEYMIX_SIG, PLAINTEXT_SIG)
                )
        else:
            if submitted_hd < SR1_RATIO_MIN * plaintext_hd:
                return False, (
                    "%s hd_variance (%s) not >= %.1fx %s hd_variance (%s)"
                    % (KEYMIX_SIG, submitted_hd, SR1_RATIO_MIN, PLAINTEXT_SIG, plaintext_hd)
                )

        return True, ""
    except (KeyError, TypeError, ValueError) as exc:
        return False, "%s field missing or malformed" % exc


def check_sr2(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, _ = check_schema(submission)
        if not ok:
            return False, reason

        if gt is None:
            return False, "simulation failed: ground truth unavailable"

        if SBOX_SIG not in signals_by_name:
            return False, "%s missing or malformed" % SBOX_SIG

        entry = signals_by_name[SBOX_SIG]
        flagged = entry["flagged"]
        submitted_hd = float(entry["hd_variance"])

        if not flagged:
            return False, "%s not flagged as leaking (flagged=false)" % SBOX_SIG

        truth = gt.get(SBOX_SIG)
        if truth is None:
            return False, "simulation failed: no ground truth for %s" % SBOX_SIG

        if not _within_order_of_magnitude(submitted_hd, truth):
            return False, (
                "%s hd_variance %s not within order-of-magnitude band (factor %.1f) of ground truth %s"
                % (SBOX_SIG, submitted_hd, GT_RATIO_FACTOR, truth)
            )

        return True, ""
    except (KeyError, TypeError, ValueError) as exc:
        return False, "%s field missing or malformed" % exc


def check_sr3(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, recommendations = check_schema(submission)
        if not ok:
            return False, reason

        for sig in (KEYMIX_SIG, SBOX_SIG, ROUNDOUT_SIG, PLAINTEXT_SIG):
            if sig not in signals_by_name:
                return False, "%s missing or malformed" % sig

        keymix_hd = float(signals_by_name[KEYMIX_SIG]["hd_variance"])
        sbox_hd = float(signals_by_name[SBOX_SIG]["hd_variance"])
        roundout_hd = float(signals_by_name[ROUNDOUT_SIG]["hd_variance"])
        plaintext_hd = float(signals_by_name[PLAINTEXT_SIG]["hd_variance"])

        leaky_max = max(keymix_hd, sbox_hd)
        nonleaky_max = max(roundout_hd, plaintext_hd)

        if not (leaky_max > nonleaky_max):
            return False, (
                "leaky signals max hd_variance (%s) does not exceed non-leaky signals max (%s)"
                % (leaky_max, nonleaky_max)
            )

        targets = set()
        for rec in recommendations:
            targets.add(rec.get("target_signal"))

        if KEYMIX_SIG not in targets and SBOX_SIG not in targets:
            return False, (
                "no recommendation targets %s or %s" % (KEYMIX_SIG, SBOX_SIG)
            )

        return True, ""
    except (KeyError, TypeError, ValueError) as exc:
        return False, "%s field missing or malformed" % exc


def check_sr4(submission, gt, input_dir="inputs"):
    try:
        ok, reason, signals_by_name, recommendations = check_schema(submission)
        if not ok:
            return False, reason

        def has_valid_recommendation(target):
            for rec in recommendations:
                if rec.get("target_signal") != target:
                    continue
                technique = (rec.get("technique") or "").strip()
                text = technique if technique else (rec.get("rationale") or "")
                text_lower = text.lower()
                for kw in ALLOWED_TECHNIQUE_KEYWORDS:
                    if kw in text_lower:
                        return True
            return False

        missing = []
        for sig in (KEYMIX_SIG, SBOX_SIG):
            if not has_valid_recommendation(sig):
                missing.append(sig)

        if missing:
            return False, (
                "no recognized countermeasure recommendation for: %s"
                % ", ".join(missing)
            )

        return True, ""
    except (KeyError, TypeError) as exc:
        return False, "%s missing or malformed" % exc