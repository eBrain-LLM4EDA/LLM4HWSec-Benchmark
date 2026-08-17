"""
tests/private/ground_truth.py

Private ground-truth definitions and scoring helpers for the
gate_trojan_detection_scan_capture_key_leak_001 case.

This module is NOT participant-facing. It is imported by
evaluation/evaluate.py via sys.path manipulation so that the exact-match
grounding logic (and the hidden answer key itself) does not need to live
directly in the top-level grader file that participants may browse.

Note: evaluation/evaluate.py currently defines its own copies of
KEY_FLOPS/KEY_MUXES inline for self-containment; this module provides the
same canonical values plus reusable scoring helpers for use by private
test tooling / alternative harness entry points, keeping a single
authoritative source of truth for the hidden answer key.
"""

# ---------------------------------------------------------------------
# Canonical ground-truth instance sets.
# ---------------------------------------------------------------------

KEY_FLOPS = {"key_ff0", "key_ff1", "key_ff2", "key_ff3"}
KEY_MUXES = {"u_smux_key0", "u_smux_key1", "u_smux_key2", "u_smux_key3"}


def _normalize_set(strings):
    """
    Normalize an iterable of strings to a set of lowercased, stripped
    strings for case-insensitive exact-match comparison.
    """
    normalized = set()
    for s in strings:
        if isinstance(s, str):
            normalized.add(s.strip().lower())
    return normalized


def compute_recall(submitted_set, truth_set):
    """
    Compute recall of `truth_set` within `submitted_set`, i.e. the
    fraction of ground-truth instance names that appear (case-
    insensitively, exact match) somewhere in the submitted collection.

    Returns a tuple (recall_fraction, matched_names) where matched_names
    is the subset of truth_set (original casing, from truth_set) that
    was found in submitted_set.
    """
    if not truth_set:
        return (1.0, set())

    submitted_norm = _normalize_set(submitted_set)
    matched = {name for name in truth_set if name.strip().lower() in submitted_norm}

    recall = len(matched) / float(len(truth_set))
    return (recall, matched)


def compute_false_positive_rate(submitted_set, valid_instance_names, truth_set):
    """
    Compute the false-positive rate of a submitted collection of
    instance names against the ground-truth set, restricted to entries
    that are at least valid real instance names in the netlist.

    false_positive_rate = (# submitted entries not in truth_set) /
                           (# submitted entries), computed over the
    distinct, normalized submitted entries. Entries that are not valid
    instance names at all are still counted as false positives (they
    are, by definition, not in the ground-truth set either), but callers
    that want FR2-style "fabricated name" detection should check
    `valid_instance_names` membership separately from this metric.

    Returns 0.0 if the submitted collection is empty (no false positives
    to report, vacuously).
    """
    submitted_norm = _normalize_set(submitted_set)
    if not submitted_norm:
        return 0.0

    truth_norm = _normalize_set(truth_set)
    valid_norm = _normalize_set(valid_instance_names) if valid_instance_names else set()

    false_positive_count = 0
    for entry in submitted_norm:
        is_ground_truth = entry in truth_norm
        if not is_ground_truth:
            false_positive_count += 1
        # Note: entries not present in valid_norm at all (fabricated
        # names) are also counted as false positives above, since a
        # fabricated name can never be a true positive; FR2-level
        # "not a real instance" grading is left to the caller if a
        # distinct signal for that failure mode is desired.
        _ = is_ground_truth  # kept for readability / future extension
        _ = valid_norm

    return false_positive_count / float(len(submitted_norm))


def compute_recall_at_least(submitted_set, truth_set, minimum_count):
    """
    Convenience helper: returns True if at least `minimum_count` of the
    entries in `truth_set` are present (case-insensitively) in
    `submitted_set`.
    """
    _, matched = compute_recall(submitted_set, truth_set)
    return len(matched) >= minimum_count