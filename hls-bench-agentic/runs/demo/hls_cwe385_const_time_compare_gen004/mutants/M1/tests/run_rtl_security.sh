#!/bin/bash
set -e
echo "[INFO] Starting static security analysis"
bash tests/security_static.sh
if [ $? -ne 0 ]; then
  echo "[FAIL] Static security checks failed"
  exit 1
fi
echo "[PASS] SR2: No early returns detected"
echo "[PASS] SR4: No secret-dependent branches detected"
echo "[PASS] SR5: No short-circuit operators on comparisons detected"
echo "[INFO] Static security analysis completed"
