#!/bin/bash
set -e

SRC_FILE="src/impl.cpp"

if [ ! -f "$SRC_FILE" ]; then
  echo "[FAIL] SR2: Source file not found"
  exit 1
fi

echo "[INFO] Checking for forbidden patterns in $SRC_FILE"

sed 's|//.*||g' "$SRC_FILE" | sed 's|/\*.*\*/||g' > /tmp/impl_no_comments.cpp

if grep -E 'for\s*\([^)]*\)\s*\{[^}]*(return[^;]*;)' /tmp/impl_no_comments.cpp; then
  echo "[FAIL] SR2: return statement found inside loop body"
  rm /tmp/impl_no_comments.cpp
  exit 1
fi

if grep -E 'for\s*\([^)]*\)\s*\{[^}]*(break\s*;|continue\s*;)' /tmp/impl_no_comments.cpp; then
  echo "[FAIL] SR2: break or continue statement found inside loop"
  rm /tmp/impl_no_comments.cpp
  exit 1
fi

if grep -E '\|\||&&' /tmp/impl_no_comments.cpp | grep -v '#include' | grep -v 'for\s*(' | grep -q .; then
  echo "[FAIL] SR5: short-circuit operators found on comparison results"
  rm /tmp/impl_no_comments.cpp
  exit 1
fi

if grep -E 'if\s*\([^)]*\^[^)]*\)' /tmp/impl_no_comments.cpp; then
  echo "[FAIL] SR4: secret-dependent conditional branch detected"
  rm /tmp/impl_no_comments.cpp
  exit 1
fi

rm /tmp/impl_no_comments.cpp
echo "[INFO] Static analysis passed"
exit 0
