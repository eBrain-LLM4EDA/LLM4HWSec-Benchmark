#!/usr/bin/env python3
"""
grading_lib.py -- Stdlib-only pure helper functions for grading recovered_key.json
submissions against hidden ground truth.

Provides:
  - parse_key_gates_field(key_gates): validate/normalize FR2 shape.
  - compute_f1(submitted_pairs, truth_pairs): precision/recall/F1 over pairs.
  - compute_key_recovery_rate(submitted_key_bits, truth_key_bits, true_indices):
    fraction of true lock bit positions that match.

No hidden constants or ground-truth data live in this module; it is pure
arithmetic/validation logic reusable both for grading a real submission and
for the SR3 synthetic-baseline self-check performed by evaluate.py.
"""


def parse_key_gates_field(key_gates):
    """
    Validate that `key_gates` is a list of well-formed objects with fields:
      - 'instance_name': str
      - 'key_bit_index': int
      - 'resolved_value': 0 or 1

    Returns a list of normalized tuples (instance_name:str, key_bit_index:int,
    resolved_value:int).

    Raises ValueError with a human-readable reason on the first malformed
    element or missing field/wrong type encountered.
    """
    if not isinstance(key_gates, list):
        raise ValueError("'key_gates' is not a JSON array")

    normalized = []
    for idx, elem in enumerate(key_gates):
        if not isinstance(elem, dict):
            raise ValueError(
                "key_gates[%d] is not a JSON object" % idx
            )

        if "instance_name" not in elem:
            raise ValueError(
                "key_gates[%d] missing required field 'instance_name'" % idx
            )
        instance_name = elem["instance_name"]
        if not isinstance(instance_name, str) or len(instance_name) == 0:
            raise ValueError(
                "key_gates[%d].instance_name is not a non-empty string" % idx
            )

        if "key_bit_index" not in elem:
            raise ValueError(
                "key_gates[%d] missing required field 'key_bit_index'" % idx
            )
        key_bit_index = elem["key_bit_index"]
        # Reject bool explicitly (bool is a subclass of int in Python).
        if isinstance(key_bit_index, bool) or not isinstance(key_bit_index, int):
            raise ValueError(
                "key_gates[%d].key_bit_index is not an integer" % idx
            )
        if key_bit_index < 0:
            raise ValueError(
                "key_gates[%d].key_bit_index is negative" % idx
            )

        if "resolved_value" not in elem:
            raise ValueError(
                "key_gates[%d] missing required field 'resolved_value'" % idx
            )
        resolved_value = elem["resolved_value"]
        if isinstance(resolved_value, bool) or resolved_value not in (0, 1):
            raise ValueError(
                "key_gates[%d].resolved_value is not 0 or 1" % idx
            )

        normalized.append((instance_name, int(key_bit_index), int(resolved_value)))

    return normalized


def compute_f1(submitted_pairs, truth_pairs):
    """
    Compute precision, recall, and F1 score over sets of (instance_name,
    key_bit_index) pairs.

    Returns (precision:float, recall:float, f1:float).

    If both submitted_pairs and truth_pairs are empty, returns (0.0, 0.0, 0.0)
    -- deliberately conservative so an empty submission never accidentally
    scores a perfect F1 against an (unexpected) empty ground truth.
    """
    submitted_pairs = set(submitted_pairs)
    truth_pairs = set(truth_pairs)

    if len(submitted_pairs) == 0 and len(truth_pairs) == 0:
        return 0.0, 0.0, 0.0

    true_positives = len(submitted_pairs & truth_pairs)

    if len(submitted_pairs) == 0:
        precision = 0.0
    else:
        precision = true_positives / float(len(submitted_pairs))

    if len(truth_pairs) == 0:
        recall = 0.0
    else:
        recall = true_positives / float(len(truth_pairs))

    if precision + recall == 0.0:
        f1 = 0.0
    else:
        f1 = 2.0 * precision * recall / (precision + recall)

    return precision, recall, f1


def compute_key_recovery_rate(submitted_key_bits, truth_key_bits, true_indices):
    """
    Compute the fraction of `true_indices` positions at which
    submitted_key_bits[i] == truth_key_bits[i].

    Returns 0.0 if true_indices is empty (no true lock positions to check --
    conservative default) or if submitted_key_bits is not indexable/too short
    to safely check any true_index (out-of-range indices are counted as
    mismatches rather than raising).
    """
    if not isinstance(submitted_key_bits, str):
        return 0.0
    if not isinstance(truth_key_bits, str):
        return 0.0
    if not true_indices:
        return 0.0

    matches = 0
    for i in true_indices:
        if i < 0:
            continue
        if i >= len(submitted_key_bits) or i >= len(truth_key_bits):
            continue
        if submitted_key_bits[i] == truth_key_bits[i]:
            matches += 1

    return matches / float(len(true_indices))