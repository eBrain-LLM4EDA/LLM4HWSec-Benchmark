#!/bin/bash
set -euo pipefail

echo "[INFO] Starting static and RTL security checks"

if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] Security checks: src/impl.cpp not found"
  exit 1
fi

if [ ! -f tests/static_security.sh ]; then
  echo "[FAIL] Security checks: tests/static_security.sh not found"
  exit 1
fi

chmod +x tests/static_security.sh

echo "[INFO] Running static security analysis"
bash tests/static_security.sh

if [ $? -ne 0 ]; then
  echo "[FAIL] Static security checks failed"
  exit 1
fi

echo "[INFO] Verifying loop bounds in implementation"
if grep -E "for.*<.*16|for.*<=.*15" src/impl.cpp > /dev/null; then
  echo "[PASS] SR3: Loop bound appears to be statically 16"
else
  echo "[FAIL] SR3: Could not verify static loop bound of 16"
  exit 1
fi

echo "[INFO] All static security checks passed"
exit 0
