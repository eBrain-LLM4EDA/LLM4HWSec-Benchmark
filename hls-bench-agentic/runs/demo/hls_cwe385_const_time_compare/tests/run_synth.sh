#!/bin/bash
set -e

echo "=== HLS Synthesis ==="

# Check if bambu is available
if ! command -v bambu &> /dev/null; then
  echo "[FAIL] bambu command not found. PandA-Bambu is required for synthesis."
  exit 1
fi

echo "Running synthesis with PandA-Bambu..."
mkdir -p synth_out

# Run bambu synthesis
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 -o synth_out/ 2>&1 | tee synth_out/synth.log

# Check if synthesis completed successfully
if grep -q "Error" synth_out/synth.log || grep -q "error" synth_out/synth.log; then
  echo "[FAIL] Synthesis encountered errors"
  exit 1
fi

if [ ! -f synth_out/compare_token.v ] && [ ! -f synth_out/top.v ]; then
  echo "[FAIL] Synthesis did not produce expected RTL output"
  exit 1
fi

echo "[PASS] Synthesis completed successfully"
echo "=== HLS Synthesis Complete ==="
