#!/bin/bash
set -e
echo "[INFO] Starting C simulation tests"
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] FR1: src/impl.cpp not found"
  exit 1
fi
g++ -std=c++11 -I. tests/tb_csim.cpp src/impl.cpp -o tb_csim 2>&1 || {
  echo "[FAIL] FR1: Compilation failed"
  exit 1
}
./tb_csim
rm -f tb_csim
echo "[INFO] C simulation tests completed"
