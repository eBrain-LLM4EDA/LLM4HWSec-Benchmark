#!/bin/bash
set -e
echo "[INFO] Starting co-simulation for timing verification"
mkdir -p cosim_out
cp tests/tb_cosim.cpp cosim_out/
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 --simulate --simulator=VERILATOR 2>&1 | tee cosim_out/cosim.log
if grep -q "Error" cosim_out/cosim.log; then
  echo "[FAIL] SR1: Co-simulation failed"
  exit 1
fi
bash tests/security_timing.sh
echo "[INFO] Co-simulation completed"
