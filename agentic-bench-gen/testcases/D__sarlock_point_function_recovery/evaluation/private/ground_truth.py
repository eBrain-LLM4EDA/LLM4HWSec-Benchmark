# Ground truth constants for SARLock point-function key recovery
# These are hidden from participants and used only by evaluate.py

CORRECT_KEY = "101101"

GROUND_TRUTH_NETS = {
    "lock_comp/xor_0",
    "lock_comp/xor_1",
    "lock_comp/xor_2",
    "lock_comp/xor_3",
    "lock_comp/xor_4",
    "lock_comp/xor_5",
    "lock_comp/and_stage1_0",
    "lock_comp/and_stage1_1",
    "lock_comp/and_stage2",
    "lock_comp/corrupt_xor",
}