#!/bin/bash
set -e

echo "[INFO] Starting HLS synthesis"

if [ ! -f "compare_token.c" ]; then
  echo "[FAIL] Synthesis: compare_token.c not found"
  exit 1
fi

echo "[INFO] Invoking bambu for synthesis"
mkdir -p synth_out
bambu compare_token.c --top-fname=compare_token --clock-period=10 -o synth_out/ 2>&1 | tee synth.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] Synthesis failed"
  cat synth.log
  exit 1
fi

if grep -q "ERROR" synth.log; then
  echo "[FAIL] Synthesis errors detected"
  exit 1
fi

echo "[PASS] Synthesis completed successfully"
echo "[INFO] Synthesis output in synth_out/"
