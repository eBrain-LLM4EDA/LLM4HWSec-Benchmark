#!/bin/bash
set -e

echo "[INFO] Starting C simulation tests"

if [ ! -f "compare_token.c" ]; then
  echo "[FAIL] FR1: compare_token.c not found"
  exit 1
fi

echo "[INFO] Compiling implementation and testbench"
g++ -std=c++11 -I. -o tb_csim compare_token.c tests/tb_csim.cpp 2>&1 | tee compile.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] FR1: Compilation failed"
  cat compile.log
  exit 1
fi

echo "[INFO] Running functional tests"
./tb_csim

echo "[INFO] C simulation completed"
