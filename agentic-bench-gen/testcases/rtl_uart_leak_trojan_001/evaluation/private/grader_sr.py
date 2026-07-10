import grader


def _dual_contains(text, keyword):
    """Check for keyword presence in text using both raw lowercase substring
    matching and normalized (underscore/space/hyphen-stripped) substring
    matching, since bracket characters like '[' and ']' are preserved by
    normalize() and keyword spacing/formatting may vary across submissions."""
    if text is None:
        return False
    raw_text = str(text).lower()
    raw_keyword = str(keyword).lower()
    if raw_keyword in raw_text:
        return True

    norm_text = grader.normalize(text)
    norm_keyword = grader.normalize(keyword)
    if norm_keyword and norm_keyword in norm_text:
        return True

    return False


def check_sr1(report):
    top = grader.get_top_candidate(report)
    if top is None:
        return False, "no unique top-ranked (max-confidence) candidate found"

    leak_source_reg = top.get("leak_source_reg", "")
    norm_value = grader.normalize(leak_source_reg)

    if "keyshadowreg" not in norm_value:
        return False, "top candidate's leak_source_reg ('{}') does not identify key_shadow_reg".format(
            leak_source_reg
        )

    return True, ""


def check_sr2(report):
    top = grader.get_top_candidate(report)
    if top is None:
        return False, "no unique top-ranked (max-confidence) candidate found"

    leak_sink_output = top.get("leak_sink_output", "")
    norm_value = grader.normalize(leak_sink_output)

    if "statusdbg" not in norm_value:
        return False, "top candidate's leak_sink_output ('{}') does not identify status_dbg".format(
            leak_sink_output
        )

    return True, ""


def check_sr3(report):
    top = grader.get_top_candidate(report)
    if top is None:
        return False, "no unique top-ranked (max-confidence) candidate found"

    rationale = top.get("rationale", "") or ""
    location_hint = top.get("location_hint", "") or ""
    combined = "{} {}".format(rationale, location_hint)

    trigger_bit_keywords = grader.GROUND_TRUTH.get("trigger_bit_keywords", [])
    trigger_start_keywords = grader.GROUND_TRUTH.get("trigger_start_keywords", [])

    has_bit_ref = any(_dual_contains(combined, kw) for kw in trigger_bit_keywords)
    has_start_ref = any(_dual_contains(combined, kw) for kw in trigger_start_keywords)

    if not has_bit_ref and not has_start_ref:
        return False, "top candidate's rationale/location_hint lacks both a bit-7/MSB reference and a tx_start reference"
    if not has_bit_ref:
        return False, "top candidate's rationale/location_hint lacks a bit-7/MSB/tx_data[7] reference"
    if not has_start_ref:
        return False, "top candidate's rationale/location_hint lacks a tx_start reference"

    return True, ""


def check_sr4(report):
    if not isinstance(report, dict):
        return False, "report is not a JSON object"

    candidates = report.get("candidates", None)
    if not isinstance(candidates, list) or len(candidates) == 0:
        return False, "candidates list is empty or missing (naive/empty submission)"

    confidences = []
    for cand in candidates:
        if isinstance(cand, dict):
            conf = cand.get("confidence", None)
            if isinstance(conf, (int, float)) and not isinstance(conf, bool):
                confidences.append(float(conf))

    if len(confidences) > 0 and all(c == 0.0 for c in confidences):
        return False, "all candidates have confidence 0.0 (no substantive finding asserted)"

    fields_to_check = [
        "signal_name",
        "leak_source_reg",
        "leak_sink_output",
        "rationale",
        "location_hint",
    ]

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        for field in fields_to_check:
            value = cand.get(field, "")
            norm_value = grader.normalize(value)
            if "keyshadowreg" in norm_value or "statusdbg" in norm_value:
                return True, ""

    return False, (
        "no candidate substantively references key_shadow_reg or status_dbg; "
        "report appears to be boilerplate or flags only unrelated signals"
    )