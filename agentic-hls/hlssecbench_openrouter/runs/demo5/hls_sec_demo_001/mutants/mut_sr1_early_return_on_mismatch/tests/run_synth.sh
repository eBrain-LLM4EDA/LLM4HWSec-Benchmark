#!/usr/bin/env bash
set -euo pipefail
mkdir -p tests

if command -v bambu >/dev/null 2>&1; then
  # Filter common Vitis/Vivado pragmas that bambu may not accept.
  sed '/^\s*#pragma\s\+HLS\s\+PIPELINE/d' src/check_token.cpp > tests/_bambu_check_token.cpp
  if bambu --top-fname=check_token -I./src -I./tests tests/_bambu_check_token.cpp > tests/bambu.log 2>&1; then
    echo "[PASS] FR-4"
    exit 0
  else
    echo "[FAIL] FR-4: bambu synthesis failed (see tests/bambu.log)"
    exit 1
  fi
fi

echo "[FAIL] FR-4: no supported synthesis tool found (bambu missing)"
exit 1
