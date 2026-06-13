#!/bin/bash
set -euo pipefail

echo "[INFO] Starting C simulation for functional requirements"

if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] FR1: src/impl.cpp not found"
  exit 1
fi

g++ -std=c++14 -I. -Isrc -Wall -Wextra -o csim tests/tb_csim.cpp src/impl.cpp 2>&1 | tee csim_compile.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] FR1: Compilation failed"
  exit 1
fi

echo "[INFO] Running functional testbench"
./csim 2>&1 | tee csim_run.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] Testbench execution failed"
  exit 1
fi

echo "[INFO] C simulation completed successfully"
exit 0
