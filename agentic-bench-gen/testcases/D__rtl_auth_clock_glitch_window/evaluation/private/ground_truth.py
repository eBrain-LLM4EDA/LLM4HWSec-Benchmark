import re

# Private ground truth constants for the RTL auth clock glitch window task.
# These values are hidden from participants and used by evaluate.py to grade submissions.

GROUND_TRUTH_CYCLE = 2
GROUND_TRUTH_STATE_REG = "state_q"
GROUND_TRUTH_RESULT_REG = "auth_result_q"

def extract_signal_names(rtl_path):
    """
    Extract all declared signal names from the RTL file.
    Looks for 'reg' and 'wire' declarations, capturing the signal name.
    Returns a set of signal name strings.
    """
    signal_names = set()
    # Patterns for reg/wire declarations: optional type, optional range, then name
    # e.g., reg [2:0] state_q;  or wire access_granted;
    # Also match input/output port declarations that may include reg/wire
    patterns = [
        r'\b(?:reg|wire)\s+(?:\[\d+:\d+\]\s+)?(\w+)\s*[;,)]',
        r'\b(input|output)\s+(?:reg|wire)?\s*(?:\[\d+:\d+\]\s+)?(\w+)\s*[;,)]',
    ]
    try:
        with open(rtl_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return signal_names  # empty set if file missing; FR3 will fail appropriately

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            # For input/output pattern, the signal name is in group 2
            if match.lastindex == 2:
                signal_names.add(match.group(2))
            else:
                signal_names.add(match.group(1))
    return signal_names