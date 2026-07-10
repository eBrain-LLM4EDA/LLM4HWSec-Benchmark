import json
import os
import re

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_GROUND_TRUTH_PATH = os.path.join(_THIS_DIR, "ground_truth.json")

with open(_GROUND_TRUTH_PATH, "r") as _f:
    GROUND_TRUTH = json.load(_f)

VALID_OUTPUT_PORTS = [p.lower() for p in GROUND_TRUTH.get("valid_output_ports", [])]
FUNCTIONAL_KEYWORDS = GROUND_TRUTH.get("functional_keywords", [])
INTEGRITY_KEYWORDS = GROUND_TRUTH.get("integrity_keywords", [])

_REQUIRED_STRING_FIELDS = [
    "id",
    "signal_name",
    "location_hint",
    "leak_source_reg",
    "leak_sink_output",
    "rationale",
]

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse_report(path):
    """Load and parse a trojan report JSON file, returning a dict.

    Raises on I/O error or malformed JSON (caller is expected to handle).
    """
    with open(path, "r") as f:
        return json.load(f)


def normalize(s):
    """Lowercase and strip underscores/spaces/hyphens for fuzzy substring matching."""
    if s is None:
        return ""
    s = str(s).lower()
    for ch in ("_", " ", "-"):
        s = s.replace(ch, "")
    return s


def _extract_identifier_tokens(s):
    """Extract identifier-like whole-word tokens (preserving internal underscores)."""
    if s is None:
        return []
    return [tok.lower() for tok in _IDENTIFIER_RE.findall(str(s))]


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _numeric_confidence(candidate):
    """Best-effort extraction of a numeric confidence from a candidate dict.

    Returns float('-inf') if unavailable/invalid so it never wins a max().
    """
    if not isinstance(candidate, dict):
        return float("-inf")
    conf = candidate.get("confidence", None)
    if _is_number(conf):
        return float(conf)
    return float("-inf")


def check_fr1(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"

    candidates = report.get("candidates", None)
    if not isinstance(candidates, list):
        return False, "'candidates' field missing or not a list"

    summary = report.get("summary", None)
    if not isinstance(summary, str) or len(summary.strip()) == 0:
        return False, "'summary' field missing, not a string, or empty"

    for idx, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            return False, "candidate at index {} is not an object".format(idx)

        for field in _REQUIRED_STRING_FIELDS:
            value = cand.get(field, None)
            if not isinstance(value, str):
                return False, "candidate at index {} missing/invalid string field '{}'".format(idx, field)
            if field == "rationale" and len(value.strip()) == 0:
                return False, "candidate at index {} has empty 'rationale'".format(idx)

        conf = cand.get("confidence", None)
        if not _is_number(conf):
            return False, "candidate at index {} has missing/non-numeric 'confidence'".format(idx)
        if conf < 0.0 or conf > 1.0:
            return False, "candidate at index {} has confidence {} outside [0.0, 1.0]".format(idx, conf)

    return True, ""


def check_fr2(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"

    candidates = report.get("candidates", None)
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "candidates list is empty or missing"

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        tokens = []
        tokens.extend(_extract_identifier_tokens(cand.get("signal_name", "")))
        tokens.extend(_extract_identifier_tokens(cand.get("leak_sink_output", "")))
        for tok in tokens:
            if tok in VALID_OUTPUT_PORTS:
                return True, ""

    return False, "no candidate's signal_name/leak_sink_output references a real output port ({})".format(
        ", ".join(VALID_OUTPUT_PORTS)
    )


def check_fr3(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"

    candidates = report.get("candidates", None)
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "candidates list is empty or missing"

    confidences = []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        conf = cand.get("confidence", None)
        if _is_number(conf):
            confidences.append(float(conf))

    if len(confidences) == 0:
        return False, "no candidate has a numeric confidence value"

    max_conf = max(confidences)
    if max_conf < 0.5:
        return False, "highest confidence {} is below required 0.5".format(max_conf)

    tie_count = sum(1 for c in confidences if abs(c - max_conf) < 1e-9)
    if tie_count > 1:
        return False, "no unique top-ranked candidate: {} candidates tie at max confidence {}".format(
            tie_count, max_conf
        )

    return True, ""


def check_fr4(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"

    summary = report.get("summary", None)
    if not isinstance(summary, str) or len(summary.strip()) == 0:
        return False, "'summary' field missing, not a string, or empty"

    norm_summary = normalize(summary)

    has_functional = any(normalize(kw) in norm_summary for kw in FUNCTIONAL_KEYWORDS)
    has_integrity = any(normalize(kw) in norm_summary for kw in INTEGRITY_KEYWORDS)

    if not has_functional and not has_integrity:
        return False, "summary lacks both a functional-framing reference and an integrity/intact qualifier"
    if not has_functional:
        return False, "summary lacks a functional-framing reference (e.g. 8N1/tx_busy/tx_done/stop bit)"
    if not has_integrity:
        return False, "summary lacks an integrity/intact-style qualifier confirming normal behavior is preserved"

    return True, ""


def get_top_candidate(report):
    """Return the unique max-confidence candidate dict, or None if unavailable/tied."""
    if not isinstance(report, dict):
        return None

    candidates = report.get("candidates", None)
    if not isinstance(candidates, list) or len(candidates) == 0:
        return None

    scored = []
    for cand in candidates:
        if isinstance(cand, dict):
            scored.append((_numeric_confidence(cand), cand))

    if not scored:
        return None

    max_conf = max(score for score, _ in scored)
    if max_conf == float("-inf"):
        return None

    top = [cand for score, cand in scored if abs(score - max_conf) < 1e-9]
    if len(top) != 1:
        return None

    return top[0]