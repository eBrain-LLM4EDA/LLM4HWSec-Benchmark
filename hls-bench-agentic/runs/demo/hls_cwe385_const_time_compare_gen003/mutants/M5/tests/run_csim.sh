#!/bin/bash
set -e
echo "[INFO] Starting C simulation tests"
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] FR1: src/impl.cpp not found"
  exit 1
fi
g++ -std=c++14 -I. -Isrc -o csim tests/tb_csim.cpp src/impl.cpp 2>&1 | tee csim_build.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] FR1: Compilation failed"
  exit 1
fi
./csim 2>&1 | tee csim_run.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] FR1: Execution failed"
  exit 1
fi
echo "[INFO] C simulation completed"
exit 0
