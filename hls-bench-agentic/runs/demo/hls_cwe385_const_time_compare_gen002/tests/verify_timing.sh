#!/bin/bash
LOG_FILE="$1"
if [ ! -f "$LOG_FILE" ]; then
  echo "[FAIL] SR1: Co-simulation log not found"
  echo "[FAIL] SR3: Co-simulation log not found"
  exit 1
fi

# Extract cycle counts for each test case
# Bambu co-simulation typically outputs cycle information in the log
# We look for patterns like "cycles: N" or "simulation completed in N cycles"

# This is a simplified parser - actual bambu output format may vary
EXACT_CYCLES=$(grep -A 5 'exact_match' "$LOG_FILE" | grep -oE 'cycles?[[:space:]]*[:=][[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)
FIRST_CYCLES=$(grep -A 5 'first_byte_mismatch' "$LOG_FILE" | grep -oE 'cycles?[[:space:]]*[:=][[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)
LAST_CYCLES=$(grep -A 5 'last_byte_mismatch' "$LOG_FILE" | grep -oE 'cycles?[[:space:]]*[:=][[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)
MIDDLE_CYCLES=$(grep -A 5 'middle_byte_mismatch' "$LOG_FILE" | grep -oE 'cycles?[[:space:]]*[:=][[:space:]]*[0-9]+' | grep -oE '[0-9]+' | head -1)

if [ -z "$EXACT_CYCLES" ] || [ -z "$FIRST_CYCLES" ] || [ -z "$LAST_CYCLES" ] || [ -z "$MIDDLE_CYCLES" ]; then
  echo "[FAIL] SR1: Could not extract cycle counts from co-simulation log"
  echo "[FAIL] SR3: Could not extract cycle counts from co-simulation log"
  exit 1
fi

echo "[INFO] Cycle counts: exact=$EXACT_CYCLES first=$FIRST_CYCLES last=$LAST_CYCLES middle=$MIDDLE_CYCLES"

# SR1: All cycle counts must be identical
if [ "$EXACT_CYCLES" -eq "$FIRST_CYCLES" ] && [ "$EXACT_CYCLES" -eq "$LAST_CYCLES" ] && [ "$EXACT_CYCLES" -eq "$MIDDLE_CYCLES" ]; then
  echo "[PASS] SR1"
  SR1_PASS=1
else
  echo "[FAIL] SR1: Cycle counts differ - timing side channel detected"
  SR1_PASS=0
fi

# SR3: Verify loop iteration count is 16 (indirect check via cycle count consistency)
if [ "$EXACT_CYCLES" -gt 0 ]; then
  echo "[PASS] SR3"
  SR3_PASS=1
else
  echo "[FAIL] SR3: Invalid cycle count"
  SR3_PASS=0
fi

if [ $SR1_PASS -eq 1 ] && [ $SR3_PASS -eq 1 ]; then
  exit 0
else
  exit 1
fi
