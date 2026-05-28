#!/bin/bash
set -e
echo "[INFO] Starting C simulation for functional requirements"
g++ -std=c++14 -I. -Isrc -o csim tests/tb_csim.cpp src/impl.cpp
if [ $? -ne 0 ]; then
  echo "[FAIL] FR5: Compilation failed"
  exit 1
fi
./csim
rm -f csim
echo "[INFO] C simulation completed"
