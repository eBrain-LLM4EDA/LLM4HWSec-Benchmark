# Hidden ground truth for gate_clock_enable_payload
# These constants define the correct answer for the Trojan detection task.
# They are imported by evaluate.py and used to grade the submission.

EXPECTED_TROJAN_DETECTED = True
EXPECTED_SUSPECT_NODES = ['nand4_out', 'payload_gate']