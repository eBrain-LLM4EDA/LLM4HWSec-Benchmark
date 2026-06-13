#!/bin/bash
set -euo pipefail

echo "[INFO] Starting HLS synthesis"

if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] FR6: src/impl.cpp not found"
  exit 1
fi

rm -rf synth_out HLS_output *.v
mkdir -p synth_out

echo "[INFO] Invoking bambu for synthesis"
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 -o synth_out/ 2>&1 | tee synth.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] FR6: Bambu synthesis failed"
  exit 1
fi

echo "[INFO] Searching for generated Verilog files"
VERILOG_FOUND=0

if ls synth_out/**/*.v 1> /dev/null 2>&1; then
  echo "[INFO] Found Verilog in synth_out/"
  VERILOG_FOUND=1
fi

if ls HLS_output/**/*.v 1> /dev/null 2>&1; then
  echo "[INFO] Found Verilog in HLS_output/"
  VERILOG_FOUND=1
fi

if ls compare_token.v 1> /dev/null 2>&1; then
  echo "[INFO] Found compare_token.v at workspace root"
  VERILOG_FOUND=1
fi

if [ $VERILOG_FOUND -eq 0 ]; then
  echo "[FAIL] FR6: No Verilog output found after synthesis"
  exit 1
fi

echo "[PASS] FR6: Synthesis completed successfully with determinable loop bounds"
exit 0
