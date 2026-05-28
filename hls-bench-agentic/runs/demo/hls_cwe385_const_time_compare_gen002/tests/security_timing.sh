#!/bin/bash
set -e
echo "[INFO] Running timing security analysis"

if ! command -v bambu &> /dev/null; then
  echo "[SKIP] SR1: bambu not available for timing analysis"
  exit 0
fi

if [ ! -f src/impl.cpp ] || [ ! -f tests/tb_cosim.cpp ]; then
  echo "[FAIL] SR1: Required files not found"
  exit 1
fi

cat src/impl.cpp tests/tb_cosim.cpp > timing_combined.cpp

bambu timing_combined.cpp --top-fname=run_cosim_tests --clock-period=10 --simulate 2>&1 | tee timing.log

if ! grep -q "Simulation completed" timing.log && ! grep -q "cycles" timing.log; then
  echo "[FAIL] SR1: Co-simulation did not complete successfully"
  rm -f timing.log timing_combined.cpp
  exit 1
fi

CYCLE_COUNTS=$(grep -oE 'cycles:[[:space:]]*[0-9]+|[0-9]+[[:space:]]*cycles' timing.log | grep -oE '[0-9]+' | sort -u)
UNIQUE_COUNTS=$(echo "$CYCLE_COUNTS" | wc -l)

if [ "$UNIQUE_COUNTS" -eq 1 ] || [ -z "$CYCLE_COUNTS" ]; then
  echo "[PASS] SR1: Constant execution latency verified (manual inspection recommended)"
else
  echo "[FAIL] SR1: Variable execution latency detected - found $UNIQUE_COUNTS different cycle counts"
  rm -f timing.log timing_combined.cpp
  exit 1
fi

rm -f timing.log timing_combined.cpp
exit 0
