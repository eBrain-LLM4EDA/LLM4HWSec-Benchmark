#!/bin/bash
set -e
echo "[INFO] Starting RTL security checks"
if [ ! -f tests/security_static.sh ]; then
  echo "[FAIL] Security: security_static.sh not found"
  exit 1
fi
bash tests/security_static.sh
if [ -f tests/security_timing.sh ]; then
  bash tests/security_timing.sh
fi
echo "[INFO] RTL security checks completed"
