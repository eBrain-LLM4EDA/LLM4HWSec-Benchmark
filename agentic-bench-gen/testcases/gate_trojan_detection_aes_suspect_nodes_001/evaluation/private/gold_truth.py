"""
Private ground-truth data for gate_trojan_detection_aes_suspect_nodes_001.

This module is imported ONLY by evaluation/evaluate.py. It must never be
referenced from participant-facing files (README, docs, etc.). It contains
no executable grading logic -- pure constants -- so all control flow and
comparison logic remains centralized in evaluate.py, shared identically by
both the real-submission grading path (check_sr1..check_sr4 against the
actual report fields) and the SR5 naive-baseline reasoning path (check_sr1..
check_sr4 against the naive-baseline fixture, plus the standalone
is_naive_equivalent(...) check applied to the actual submission).
"""

# Ground-truth infection label for inputs/aes_sub_netlist.v
GOLD_INFECTED = True

# The AND-tree trigger instances that actually appear in
# inputs/aes_sub_netlist.v (t_and0, t_and1, t_and2 feed t_and_final,
# which produces trig_sig).
GOLD_TRIGGER_NODES = ["t_and0", "t_and1", "t_and2", "t_and_final"]

# The XOR payload instance spliced onto the path to sbox_out[3].
GOLD_PAYLOAD_NODE = "payload_xor"

# The primary output port (from inputs/port_map.json) that is corrupted
# by the payload logic.
GOLD_OUTPUT = "sbox_out"

# Minimum number of the 4 trigger-tree nodes that must be named in
# suspect_nodes for SR2 to pass (payload_xor is required separately,
# in addition to this coverage threshold).
GOLD_TRIGGER_MIN_COVERAGE = 3

# Semantic keyword groups used by SR4/check_sr4. The rationale must hit
# terms from at least two DISTINCT groups to demonstrate real understanding
# of the rare-activation AND-tree trigger mechanism, rather than generic or
# boilerplate wording. Each group covers one facet of the mechanism;
# phrasing may vary arbitrarily as long as it lands in the group's
# semantic territory.
GOLD_RATIONALE_KEYWORD_GROUPS = [
    # Group 1: structural / gate-tree phrasing
    [
        "and-tree",
        "and tree",
        "and-gate tree",
        "tree of and",
        "and gates",
        "gate tree",
        "cascade of and",
        "chain of and",
        "combinational tree",
        "and0",
        "and1",
        "and2",
        "and_final",
    ],
    # Group 2: rareness / low-probability phrasing
    [
        "rare",
        "rarely",
        "rareness",
        "low-probability",
        "low probability",
        "unlikely",
        "improbable",
        "hamming",
        "2^-8",
        "2^-",
        "probability",
        "seldom",
        "infrequent",
    ],
    # Group 3: trigger / activation phrasing
    [
        "trigger",
        "activation",
        "activates",
        "activated",
        "fires",
        "firing",
        "trig_sig",
        "rare condition",
        "rare pattern",
        "specific pattern",
        "specific combination",
        "corner case",
    ],
]