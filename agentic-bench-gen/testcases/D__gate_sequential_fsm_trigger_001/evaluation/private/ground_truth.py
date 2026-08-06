# Hidden ground truth constants for gate_sequential_fsm_trigger_001
# These are used by evaluate.py to grade the participant's trojan_report.json

TRIGGER_DFFS = {"u_trig_dff0", "u_trig_dff1", "u_trig_dff2", "u_trig_dff3"}
PAYLOAD_GATE = "u_xor_payload"
ROLE_MAP = {
    "u_trig_dff0": "trigger_logic",
    "u_trig_dff1": "trigger_logic",
    "u_trig_dff2": "trigger_logic",
    "u_trig_dff3": "trigger_logic",
    "u_xor_payload": "payload_gate",
}
MAX_FALSE_POSITIVES = 2