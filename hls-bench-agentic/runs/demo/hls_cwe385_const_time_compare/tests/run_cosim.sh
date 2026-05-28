#!/bin/bash
set -e

echo "=== Co-Simulation ==="

# Check if bambu is available
if ! command -v bambu &> /dev/null; then
  echo "[FAIL] bambu command not found. PandA-Bambu is required for co-simulation."
  exit 1
fi

echo "Running co-simulation with PandA-Bambu..."
mkdir -p cosim_out

# Run bambu co-simulation
bambu src/impl.cpp --top-fname=compare_token --clock-period=10 --simulate 2>&1 | tee cosim_out/cosim.log

# Check if co-simulation completed successfully
if grep -q "Error" cosim_out/cosim.log || grep -q "error" cosim_out/cosim.log; then
  echo "[FAIL] Co-simulation encountered errors"
  exit 1
fi

if ! grep -q "simulation" cosim_out/cosim.log && ! grep -q "Simulation" cosim_out/cosim.log; then
  echo "[FAIL] Co-simulation did not execute properly"
  exit 1
fi

echo "[PASS] Co-simulation completed successfully"
echo "=== Co-Simulation Complete ==="
