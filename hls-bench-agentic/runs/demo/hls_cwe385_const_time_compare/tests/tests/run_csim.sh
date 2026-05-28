#!/bin/bash
set -e

echo "=== C Simulation ==="

# Compile and run functional testbench
echo "Compiling functional testbench..."
g++ -std=c++14 -I. -Isrc -o csim_func tests/tb_csim.cpp src/impl.cpp 2>&1
if [ $? -ne 0 ]; then
  echo "[FAIL] Compilation failed"
  exit 1
fi

echo "Running functional tests..."
./csim_func

# Compile and run timing testbench
echo "Compiling timing testbench..."
g++ -std=c++14 -I. -Isrc -o csim_timing tests/tb_timing.cpp src/impl.cpp 2>&1
if [ $? -ne 0 ]; then
  echo "[FAIL] Timing testbench compilation failed"
  exit 1
fi

echo "Running timing tests..."
./csim_timing

echo "=== C Simulation Complete ==="
