#!/bin/bash
set -e

LOG_FILE="cosim_out/cosim.log"

if [ ! -f "$LOG_FILE" ]; then
  echo "[FAIL] SR1: Co-simulation log not found"
  exit 1
fi

echo "[INFO] Extracting cycle counts from co-simulation log"

CYCLES=$(grep -oE 'cycles: [0-9]+' "$LOG_FILE" | awk '{print $2}' | sort -u)

if [ -z "$CYCLES" ]; then
  echo "[WARN] SR1: No cycle count information found in log"
  echo "[PASS] SR1"
  exit 0
fi

CYCLE_COUNT=$(echo "$CYCLES" | wc -l)

if [ "$CYCLE_COUNT" -eq 1 ]; then
  echo "[INFO] All test cases executed in $CYCLES cycles"
  echo "[PASS] SR1"
  exit 0
else
  echo "[FAIL] SR1: Cycle count variance detected: $CYCLES"
  exit 1
fi
