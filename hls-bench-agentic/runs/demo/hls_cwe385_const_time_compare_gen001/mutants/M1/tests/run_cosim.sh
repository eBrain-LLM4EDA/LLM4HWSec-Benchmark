#!/bin/bash
set -e

echo "[INFO] Starting co-simulation for cycle-accurate timing verification"

if [ ! -f "compare_token.c" ]; then
  echo "[FAIL] SR1: compare_token.c not found"
  exit 1
fi

if [ ! -f "tests/security_checks.cpp" ]; then
  echo "[FAIL] SR1: security_checks.cpp not found"
  exit 1
fi

echo "[INFO] Compiling security testbench"
g++ -std=c++11 -I. -o security_tb compare_token.c tests/security_checks.cpp 2>&1

if [ $? -ne 0 ]; then
  echo "[FAIL] SR1: Security testbench compilation failed"
  exit 1
fi

echo "[INFO] Running security checks"
./security_tb

echo "[INFO] Invoking bambu co-simulation"
mkdir -p cosim_out
bambu compare_token.c --top-fname=compare_token --clock-period=10 --simulate 2>&1 | tee cosim.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] SR1: Co-simulation failed"
  cat cosim.log
  exit 1
fi

if grep -q "ERROR" cosim.log; then
  echo "[FAIL] SR1: Co-simulation errors detected"
  exit 1
fi

echo "[INFO] Co-simulation completed"
