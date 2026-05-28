#!/bin/bash
set -e
echo "[INFO] Starting co-simulation"
if ! command -v bambu &> /dev/null; then
  echo "[SKIP] Co-simulation: bambu not available"
  exit 0
fi
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] Co-simulation: src/impl.cpp not found"
  exit 1
fi
if [ ! -f tests/tb_cosim.cpp ]; then
  echo "[FAIL] Co-simulation: tests/tb_cosim.cpp not found"
  exit 1
fi
cat src/impl.cpp tests/tb_cosim.cpp > cosim_combined.cpp
bambu cosim_combined.cpp --top-fname=run_cosim_tests --clock-period=10 --simulate 2>&1 | tee cosim.log
if grep -q "Error" cosim.log; then
  echo "[FAIL] Co-simulation: bambu reported errors"
  rm -f cosim.log cosim_combined.cpp
  exit 1
fi
grep "\[PASS\]\|\[FAIL\]" cosim.log || echo "[FAIL] Co-simulation: No test results found"
rm -f cosim.log cosim_combined.cpp
echo "[INFO] Co-simulation completed"
