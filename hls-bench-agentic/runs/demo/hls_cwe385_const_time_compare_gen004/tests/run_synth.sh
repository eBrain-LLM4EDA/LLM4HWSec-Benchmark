#!/bin/bash
set -e
echo "[INFO] Starting HLS synthesis"
mkdir -p synth_out
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 -o synth_out/ 2>&1 | tee synth_out/synth.log
if grep -q "Error" synth_out/synth.log; then
  echo "[FAIL] Synthesis failed"
  exit 1
fi
if [ -f synth_out/compare_token.v ]; then
  echo "[PASS] Synthesis completed successfully"
else
  echo "[FAIL] RTL output not generated"
  exit 1
fi
