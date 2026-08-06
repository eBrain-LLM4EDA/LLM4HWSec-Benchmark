GATE_PRIMITIVES = ['and', 'or', 'nand', 'nor', 'not', 'xor', 'xnor', 'buf']

# Hidden ground-truth trigger input, per task hidden_spec:
#   a = 8'b10110100 (180 decimal)
#   b = 8'b01101011 (107 decimal)
# These are used only for informational/diagnostic messaging in evaluate.py;
# the actual PASS/FAIL verdict for SR4 is determined behaviorally by
# simulating the real netlist via iverilog/vvp (see simulate_check in
# evaluate.py), so this module never gates correctness on these literals
# alone.
EXPECTED_A = 0b10110100  # 180
EXPECTED_B = 0b01101011  # 107

# Required payload gate instance name and role.
EXPECTED_PAYLOAD_NODE = 'payload_xor_p7'
EXPECTED_PAYLOAD_ROLE = 'payload'

# Required final trigger gate instance name and role.
EXPECTED_TRIGGER_FINAL_NODE = 'trig_and_final'
EXPECTED_TRIGGER_FINAL_ROLE = 'trigger'

# Bonus (non-gating) trigger nodes: full credit tier lists these too, but
# they are not required for a PASS -- only trig_and_final + payload_xor_p7
# are strictly required per SR2/SR3.
EXPECTED_BONUS_TRIGGER_NODES = [
    'trig_and1',
    'trig_and2',
    'trig_and3',
    'trig_and4',
    'trig_and5',
    'trig_and6',
]

# ---------------------------------------------------------------------
# CONTROL_VECTORS: 12 deterministic (a, b) 8-bit pairs used by SR4's
# false-positive-rate cross-check. Each pair is chosen so that, no matter
# which specific rare trigger condition a correct submission reports,
# these vectors are guaranteed -- by construction against the fixed
# structural AND-tree tapped onto pp_2_3/pp_4_1/pp_5_6/pp_1_7/pp_6_2/
# pp_3_5 in inputs/mult8_netlist.v -- to leave at least one of the a-bit
# taps (a[1]..a[6]) at 0, so the trigger's six-way AND cannot all be 1
# simultaneously regardless of the b operand. This keeps the control set
# safe/non-triggering independent of the exact rare input a correct
# submission ultimately reports, while still covering diverse edge cases
# (all-zero, single-bit, alternating, and near-boundary operands).
# ---------------------------------------------------------------------
CONTROL_VECTORS = [
    (0, 0),
    (1, 1),
    (2, 255),
    (4, 254),
    (8, 170),
    (16, 85),
    (32, 128),
    (64, 127),
    (128, 64),
    (170, 32),
    (85, 16),
    (3, 8),
]