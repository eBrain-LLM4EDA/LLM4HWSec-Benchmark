# Ground truth constants for SCFA-001 task
# These values are used by evaluate.py to grade the submission
# DO NOT SHIP TO PARTICIPANTS

GROUND_TRUTH_NET = 'recombine_xor'
GROUND_TRUTH_REG = 'recombined_sbox_q'

BENIGN_REGISTERS = {
    'share0_q',
    'share1_q',
    'share0_out',
    'share1_out',
}

BENIGN_NETS = {
    'inv_share0',
    'inv_share1',
    'a_unmasked',
    'inv_unmasked',
}