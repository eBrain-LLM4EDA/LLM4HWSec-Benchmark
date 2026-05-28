#!/bin/bash
set -e
echo "[INFO] Starting RTL security analysis"
if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] SECURITY: src/impl.cpp not found"
  exit 1
fi
bash tests/static_analysis.sh src/impl.cpp
if [ $? -ne 0 ]; then
  echo "[FAIL] SECURITY: Static analysis detected violations"
  exit 1
fi
echo "[PASS] SECURITY: All static security checks passed"
exit 0
