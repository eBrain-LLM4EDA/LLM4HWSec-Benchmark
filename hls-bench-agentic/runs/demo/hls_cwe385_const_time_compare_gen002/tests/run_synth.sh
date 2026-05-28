#!/bin/bash
set -e
echo "[INFO] Starting HLS synthesis"
if ! command -v bambu &> /dev/null; then
  echo "[SKIP] Synthesis: bambu not available"
  exit 0
fi
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] Synthesis: src/impl.cpp not found"
  exit 1
fi
mkdir -p synth_out
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 -o synth_out/ 2>&1 | tee synth.log
if grep -q "Error" synth.log; then
  echo "[FAIL] Synthesis: bambu reported errors"
  exit 1
fi
echo "[PASS] Synthesis completed successfully"
rm -f synth.log
