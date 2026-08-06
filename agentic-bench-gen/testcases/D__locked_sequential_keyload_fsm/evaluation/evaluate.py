#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys
import tempfile

# ----------------------------------------------------------------------
# Hidden ground truth (never revealed to participant)
# ----------------------------------------------------------------------
CORRECT_KEY = "0110"
CORRECT_LOCK_REGS = [
    "top.lock_reg[0]",
    "top.lock_reg[1]",
    "top.lock_reg[2]",
    "top.lock_reg[3]",
]

# ----------------------------------------------------------------------
# Helper: emit a test result marker and track overall status
# ----------------------------------------------------------------------
all_pass = True

def emit(requirement_id, passed, reason=""):
    global all_pass
    if passed:
        print(f"[TEST] PASS: {requirement_id}")
    else:
        all_pass = False
        msg = f"[TEST] FAIL: {requirement_id}"
        if reason:
            msg += f": {reason}"
        print(msg)

# ----------------------------------------------------------------------
# FR1: submission file exists and is valid JSON
# ----------------------------------------------------------------------
submission_path = "submission/recovered_key.json"
if not os.path.isfile(submission_path):
    emit("FR1", False, f"{submission_path} not found")
    # Cannot continue without the file; exit early
    sys.exit(1)

try:
    with open(submission_path, "r") as f:
        submission = json.load(f)
except (json.JSONDecodeError, ValueError) as e:
    emit("FR1", False, f"invalid JSON: {e}")
    sys.exit(1)

emit("FR1", True)

# ----------------------------------------------------------------------
# FR2: key_sequence is a 4-bit string of '0'/'1'
# ----------------------------------------------------------------------
key_seq = submission.get("key_sequence")
if not isinstance(key_seq, str):
    emit("FR2", False, "key_sequence missing or not a string")
elif len(key_seq) != 4:
    emit("FR2", False, f"key_sequence length is {len(key_seq)}, expected 4")
elif not all(c in "01" for c in key_seq):
    emit("FR2", False, "key_sequence contains characters other than '0'/'1'")
else:
    emit("FR2", True)

# ----------------------------------------------------------------------
# FR3: lock_registers is a list of 4 valid hierarchical names present in
#      inputs/locked_fsm.v
# ----------------------------------------------------------------------
lock_regs = submission.get("lock_registers")
if not isinstance(lock_regs, list):
    emit("FR3", False, "lock_registers missing or not a list")
elif len(lock_regs) != 4:
    emit("FR3", False, f"lock_registers has {len(lock_regs)} entries, expected 4")
else:
    # Read the netlist to extract all hierarchical signal names
    netlist_path = "inputs/locked_fsm.v"
    if not os.path.isfile(netlist_path):
        emit("FR3", False, f"{netlist_path} not found")
    else:
        with open(netlist_path, "r") as f:
            netlist_text = f.read()
        # Simple extraction: look for identifiers that look like hierarchical names
        # (module.reg[bit] or module.reg)
        # We'll collect all words that match the pattern \w+(\.\w+(\[\d+\])?)+
        # This is intentionally permissive to avoid false negatives.
        found_names = set(re.findall(r'\b\w+(?:\.\w+(?:\[\d+\])?)+\b', netlist_text))
        missing = [name for name in lock_regs if name not in found_names]
        if missing:
            emit("FR3", False, f"lock_registers not found in netlist: {missing}")
        else:
            emit("FR3", True)

# ----------------------------------------------------------------------
# SR1: fail-on-presence – key sequence must not appear as a contiguous
#      constant in the netlist
# ----------------------------------------------------------------------
# Vulnerability in baseline: the comparison logic contains the pattern
#   if (!lock_reg[3] && lock_reg[2] && lock_reg[1] && !lock_reg[0])
# which encodes the key bits directly. We search for the string "0110"
# appearing as a contiguous sequence (e.g., 4'b0110, "0110", or the bit
# pattern in a single expression).
netlist_path = "inputs/locked_fsm.v"
if not os.path.isfile(netlist_path):
    emit("SR1", False, f"{netlist_path} not found")
else:
    with open(netlist_path, "r") as f:
        netlist_text = f.read()
    # Look for the exact key sequence as a contiguous string, but allow
    # Verilog constant prefixes like 4'b, 4'h, etc.
    pattern = r'(?:\d+\'[bB])?0110'
    if re.search(pattern, netlist_text):
        emit("SR1", False, "key sequence '0110' found as contiguous constant in netlist")
    else:
        emit("SR1", True)

# ----------------------------------------------------------------------
# SR2: behavioral cross-check via simulation
# ----------------------------------------------------------------------
def run_simulation(key_to_test):
    """
    Simulate locked_fsm.v with the given 4-bit key sequence.
    Returns the observed data_out trace as a list of integers (0/1).
    """
    tb_path = "evaluation/tb_check.v"
    if not os.path.isfile(tb_path):
        return None  # testbench missing, cannot simulate

    with tempfile.TemporaryDirectory() as tmpdir:
        vvp_out = os.path.join(tmpdir, "sim.vvp")
        # Compile
        cmd_compile = [
            "iverilog", "-g2012", "-o", vvp_out,
            netlist_path, tb_path,
        ]
        try:
            subprocess.run(cmd_compile, check=True, capture_output=True, text=True, timeout=10)
        except subprocess.CalledProcessError as e:
            # Compilation failure – treat as simulation failure
            return None
        except subprocess.TimeoutExpired:
            return None

        # Run simulation, passing the key as a plusarg
        cmd_run = ["vvp", vvp_out, f"+KEY={key_to_test}"]
        try:
            result = subprocess.run(cmd_run, check=True, capture_output=True, text=True, timeout=10)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

        # Parse output: lines starting with [SR2_CROSSCHECK] contain the trace
        trace = []
        for line in result.stdout.splitlines():
            if line.startswith("[SR2_CROSSCHECK]"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        trace.append(int(parts[1]))
                    except ValueError:
                        pass
        return trace

# Only run SR2 if the submission passed FR2 (we have a valid key_sequence)
if not isinstance(key_seq, str) or len(key_seq) != 4 or not all(c in "01" for c in key_seq):
    emit("SR2", False, "cannot perform cross-check: key_sequence invalid")
else:
    # Simulate with the submitted key
    trace_submitted = run_simulation(key_seq)
    if trace_submitted is None:
        emit("SR2", False, "simulation failed (iverilog/vvp missing or testbench error)")
    else:
        # Simulate with a known incorrect key (all zeros)
        trace_incorrect = run_simulation("0000")
        if trace_incorrect is None:
            emit("SR2", False, "simulation failed for incorrect key")
        else:
            # Determine functional vs decoy behavior
            # Functional: after key loading, data_out should equal data_in
            # Decoy: data_out should be ~data_in
            # We'll check the last few cycles where data_in toggles.
            # The testbench drives a known pattern; we just verify that
            # the submitted key trace shows functional behavior and the
            # incorrect key trace shows decoy behavior.
            # For simplicity, we check that the submitted key trace is NOT
            # identical to the decoy trace (all ~data_in) and that the
            # incorrect key trace IS decoy.
            # A more precise check would compare against expected functional
            # output, but this is sufficient to catch a wrong key.
            if len(trace_submitted) < 5 or len(trace_incorrect) < 5:
                emit("SR2", False, "simulation trace too short")
            else:
                # The testbench drives data_in = 0 for first cycles, then toggles.
                # In functional mode, data_out follows data_in.
                # In decoy mode, data_out is ~data_in.
                # We'll check the last 4 cycles where data_in is 1.
                # Expected functional: 1, 1, 1, 1
                # Expected decoy:     0, 0, 0, 0
                # We'll look at the last 4 entries of the trace.
                submitted_last4 = trace_submitted[-4:]
                incorrect_last4 = trace_incorrect[-4:]
                functional_ok = all(v == 1 for v in submitted_last4)
                decoy_ok = all(v == 0 for v in incorrect_last4)
                if functional_ok and decoy_ok:
                    emit("SR2", True)
                else:
                    reason_parts = []
                    if not functional_ok:
                        reason_parts.append("submitted key did not produce functional output")
                    if not decoy_ok:
                        reason_parts.append("incorrect key did not produce decoy output")
                    emit("SR2", False, "; ".join(reason_parts))

# ----------------------------------------------------------------------
# Final exit
# ----------------------------------------------------------------------
sys.exit(0 if all_pass else 1)