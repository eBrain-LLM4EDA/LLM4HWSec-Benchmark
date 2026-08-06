# Hidden ground truth for the mixed XOR/MUX lock classification task.
# This file is private and must never be exposed to participants.

GROUND_TRUTH_LOCK_GATES = [
    {"gate_label": "lock_gate_0", "classification": "XOR", "key_bit": 0},
    {"gate_label": "lock_gate_1", "classification": "XNOR", "key_bit": 1},
    {"gate_label": "lock_gate_2", "classification": "MUX_0", "key_bit": 0},
    {"gate_label": "lock_gate_3", "classification": "MUX_1", "key_bit": 1},
]

GROUND_TRUTH_KEY = "0101"
GROUND_TRUTH_KEY_BITS = [0, 1, 0, 1]