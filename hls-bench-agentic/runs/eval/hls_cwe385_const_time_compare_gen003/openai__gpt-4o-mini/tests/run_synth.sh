#!/bin/bash
set -e
echo "[INFO] Starting HLS synthesis"
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] SYNTH: src/impl.cpp not found"
  exit 1
fi
mkdir -p synth_out
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 -o synth_out/ 2>&1 | tee synth.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
  echo "[FAIL] SYNTH: Synthesis failed"
  grep -i "error" synth.log || true
  exit 1
fi
if [ ! -f synth_out/compare_token.v ]; then
  echo "[FAIL] SYNTH: RTL output not generated"
  exit 1
fi
echo "[PASS] SYNTH: Synthesis completed successfully"
exit 0
