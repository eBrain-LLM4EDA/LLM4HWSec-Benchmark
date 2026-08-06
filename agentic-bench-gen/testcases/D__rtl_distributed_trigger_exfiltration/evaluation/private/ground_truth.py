# Hidden ground truth constants for the RTL Trojan detection task.
# This file is NOT shipped to participants.

# Expected trigger signals: (module_name, signal_name)
EXPECTED_TRIGGER_SIGNALS = [
    ("counter", "counter_terminal"),
    ("command_decoder", "command_match"),
    ("error_handler", "sticky_error"),
]

# Keywords that must appear in the rationale of the payload finding (top.v)
EXPECTED_PAYLOAD_KEYWORDS = [
    "secret_reg[0]",
    "status_out",
    "multiplexer",
    "mux",
    "conditional",
    "select",
    "leak",
    "exfiltrat",
]

# Minimum overall confidence required for SR5
MIN_CONFIDENCE = 0.7

# Expected value of trojan_detected for a correct submission
EXPECTED_TROJAN_DETECTED = True