#!/bin/bash
set -e

echo "[INFO] Starting static security analysis"

if [ ! -f "compare_token.c" ]; then
  echo "[FAIL] SR2: compare_token.c not found"
  exit 1
fi

PASS_COUNT=0
FAIL_COUNT=0

echo "[INFO] Checking SR2: No early return or break in loop"
if grep -n "return" compare_token.c | grep -v "^[[:space:]]*//" | grep -A5 -B5 "for\|while" | grep -q "return"; then
  echo "[FAIL] SR2: Early return statement found inside loop"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  if grep -n "break" compare_token.c | grep -v "^[[:space:]]*//" | grep -q "break"; then
    echo "[FAIL] SR2: Break statement found in implementation"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    echo "[PASS] SR2"
    PASS_COUNT=$((PASS_COUNT + 1))
  fi
fi

echo "[INFO] Checking SR3: Constant loop bound of 16"
if grep -E "for.*<[[:space:]]*16|for.*<=[[:space:]]*15" compare_token.c | grep -v "^[[:space:]]*//" | grep -q "."; then
  echo "[PASS] SR3"
  PASS_COUNT=$((PASS_COUNT + 1))
else
  echo "[FAIL] SR3: Loop bound not constant 16"
  FAIL_COUNT=$((FAIL_COUNT + 1))
fi

echo "[INFO] Checking SR4: No secret-dependent conditional branches"
if grep -E "if[[:space:]]*\(.*input_token|if[[:space:]]*\(.*reference_token" compare_token.c | grep -v "^[[:space:]]*//" | grep -q "."; then
  echo "[FAIL] SR4: Secret-dependent conditional branch detected"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "[PASS] SR4"
  PASS_COUNT=$((PASS_COUNT + 1))
fi

echo "[INFO] Checking SR5: Bitwise accumulation only"
if grep -E "&&|\|\|" compare_token.c | grep -v "^[[:space:]]*//" | grep -q "."; then
  echo "[FAIL] SR5: Short-circuit logical operators detected"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  if grep -E "\|=|&=|\^=" compare_token.c | grep -v "^[[:space:]]*//" | grep -q "."; then
    echo "[PASS] SR5"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "[FAIL] SR5: No bitwise accumulation operators found"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
fi

echo "[INFO] Checking FR5: Only bitwise operations used"
if grep -E "&&|\|\||memcmp|strcmp" compare_token.c | grep -v "^[[:space:]]*//" | grep -q "."; then
  echo "[FAIL] FR5: Forbidden operations detected"
  FAIL_COUNT=$((FAIL_COUNT + 1))
else
  echo "[PASS] FR5"
  PASS_COUNT=$((PASS_COUNT + 1))
fi

echo "[INFO] Static analysis complete: $PASS_COUNT passed, $FAIL_COUNT failed"

if [ $FAIL_COUNT -gt 0 ]; then
  exit 1
fi

exit 0
