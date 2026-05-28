#!/bin/bash
SRC_FILE="$1"
if [ ! -f "${SRC_FILE}" ]; then
  echo "[FAIL] SR2: Source file not found: ${SRC_FILE}"
  exit 1
fi
echo "[INFO] Removing comments from source for analysis"
sed 's|//.*||g' "${SRC_FILE}" | sed ':a;N;$!ba;s|/\*.*\*/||g' > /tmp/impl_no_comments.cpp
echo "[INFO] Checking SR2: Fixed loop bound with pragma"
if ! grep -q "#pragma HLS loop_bound" /tmp/impl_no_comments.cpp; then
  echo "[FAIL] SR2: Missing loop_bound pragma"
  exit 1
fi
if grep -q "#pragma HLS loop_bound min=16 max=16" /tmp/impl_no_comments.cpp; then
  echo "[PASS] SR2"
else
  echo "[FAIL] SR2: loop_bound pragma does not specify min=16 max=16"
  exit 1
fi
echo "[INFO] Checking SR3: No conditional branches on byte comparisons"
if grep -E "if\s*\(.*\[.*\].*==" /tmp/impl_no_comments.cpp | grep -v "mismatch.*==.*0" | grep -q .; then
  echo "[FAIL] SR3: Found if statement with byte comparison"
  exit 1
fi
if grep -qE "\&\&|\|\|" /tmp/impl_no_comments.cpp; then
  echo "[FAIL] SR3: Found short-circuit logical operators"
  exit 1
fi
echo "[PASS] SR3"
echo "[INFO] Checking SR4: Single return at function end"
RETURN_COUNT=$(grep -c "return" /tmp/impl_no_comments.cpp || true)
if [ "${RETURN_COUNT}" -ne 1 ]; then
  echo "[FAIL] SR4: Found ${RETURN_COUNT} return statements, expected exactly 1"
  exit 1
fi
FUNC_START=$(grep -n "compare_token" /tmp/impl_no_comments.cpp | head -1 | cut -d: -f1)
FUNC_END=$(tail -n +${FUNC_START} /tmp/impl_no_comments.cpp | grep -n "}" | head -1 | cut -d: -f1)
RETURN_LINE=$(grep -n "return" /tmp/impl_no_comments.cpp | cut -d: -f1)
LAST_LINES=$((FUNC_START + FUNC_END - 3))
if [ "${RETURN_LINE}" -lt "${LAST_LINES}" ]; then
  echo "[FAIL] SR4: Return statement not at function end"
  exit 1
fi
echo "[PASS] SR4"
echo "[INFO] Checking SR5: Bitwise operations for accumulation"
if ! grep -qE "\|=|\&=|\^" /tmp/impl_no_comments.cpp; then
  echo "[FAIL] SR5: No bitwise operations found for accumulation"
  exit 1
fi
echo "[PASS] SR5"
echo "[INFO] Checking for forbidden patterns"
if grep -qE "break|continue" /tmp/impl_no_comments.cpp; then
  echo "[FAIL] FORBIDDEN: Found break or continue statement"
  exit 1
fi
if grep -qE "\?.*:" /tmp/impl_no_comments.cpp; then
  echo "[FAIL] FORBIDDEN: Found ternary operator"
  exit 1
fi
LOOP_START=$(grep -n "for\|while" /tmp/impl_no_comments.cpp | head -1 | cut -d: -f1)
if [ -n "${LOOP_START}" ]; then
  LOOP_BODY=$(tail -n +${LOOP_START} /tmp/impl_no_comments.cpp | sed -n '/{/,/}/p' | head -20)
  if echo "${LOOP_BODY}" | grep -q "return"; then
    echo "[FAIL] FORBIDDEN: Found return statement inside loop"
    exit 1
  fi
fi
echo "[INFO] All static security checks passed"
rm -f /tmp/impl_no_comments.cpp
exit 0
