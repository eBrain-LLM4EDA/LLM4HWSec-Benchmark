#!/bin/bash
set -e
echo "[INFO] Starting co-simulation for timing analysis"
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] SR1: src/impl.cpp not found"
  exit 1
fi
mkdir -p cosim_out
for test_case in match first_diff last_diff middle_diff random_diff; do
  echo "[INFO] Running co-simulation for test case: ${test_case}"
  bambu src/impl.cpp --top-fname=compare_token --clock-period=10 --simulate --simulator=VERILATOR 2>&1 | tee cosim_out/${test_case}.log
  if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "[FAIL] SR1: Co-simulation failed for ${test_case}"
    exit 1
  fi
done
echo "[INFO] Analyzing cycle counts"
python3 tests/timing_analysis.py cosim_out/*.log
if [ $? -eq 0 ]; then
  echo "[PASS] SR1"
else
  echo "[FAIL] SR1: Timing variation detected"
  exit 1
fi
exit 0
