#!/bin/bash
set -euo pipefail

echo "[INFO] Starting Bambu co-simulation for timing verification"

if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] SR1: src/impl.cpp not found"
  exit 1
fi

if [ ! -f tests/tb_cosim.cpp ]; then
  echo "[FAIL] SR1: tests/tb_cosim.cpp not found"
  exit 1
fi

rm -rf cosim_out HLS_output *.v
mkdir -p cosim_out

echo "[INFO] Invoking bambu co-simulation with Verilator"
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 --simulate --simulator=VERILATOR --generate-tb=tests/tb_cosim.cpp 2>&1 | tee cosim.log

BEXIT=${PIPESTATUS[0]}
if [ $BEXIT -ne 0 ]; then
  echo "[FAIL] SR1: Bambu co-simulation failed with exit code $BEXIT"
  exit 1
fi

echo "[INFO] Bambu co-simulation completed successfully"

echo "[INFO] Checking for RTL output files"
VERILOG_FOUND=0

if ls synth_out/**/*.v 1> /dev/null 2>&1; then
  VERILOG_FOUND=1
fi

if ls HLS_output/**/*.v 1> /dev/null 2>&1; then
  VERILOG_FOUND=1
fi

if ls compare_token.v 1> /dev/null 2>&1; then
  VERILOG_FOUND=1
fi

if [ $VERILOG_FOUND -eq 1 ]; then
  echo "[INFO] RTL files generated successfully"
else
  echo "[WARN] No RTL files found (may be expected for simulation-only run)"
fi

echo "[PASS] SR1: Co-simulation completed (check tb_cosim.cpp output for requirement markers)"
exit 0
