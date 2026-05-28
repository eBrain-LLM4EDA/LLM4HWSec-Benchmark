#!/bin/bash
set -e

echo "=== RTL Security Checks ==="

FAILED=0

# SR2: Check for early return inside loop
echo "Checking SR2: No early return from comparison loop..."
if grep -n "for.*16" src/impl.cpp | head -1 > /tmp/loop_start.txt; then
  LOOP_START=$(grep -n "for.*16" src/impl.cpp | head -1 | cut -d: -f1)
  LOOP_END=$(tail -n +$LOOP_START src/impl.cpp | grep -n "}" | head -1 | cut -d: -f1)
  LOOP_END=$((LOOP_START + LOOP_END - 1))
  
  if sed -n "${LOOP_START},${LOOP_END}p" src/impl.cpp | grep -q "return"; then
    echo "[FAIL] SR2: Found return statement inside comparison loop"
    FAILED=1
  else
    echo "[PASS] SR2"
  fi
else
  echo "[PASS] SR2"
fi

# Check for break/continue
if grep -n "for.*16" src/impl.cpp | head -1 > /tmp/loop_start.txt; then
  LOOP_START=$(grep -n "for.*16" src/impl.cpp | head -1 | cut -d: -f1)
  LOOP_END=$(tail -n +$LOOP_START src/impl.cpp | grep -n "}" | head -1 | cut -d: -f1)
  LOOP_END=$((LOOP_START + LOOP_END - 1))
  
  if sed -n "${LOOP_START},${LOOP_END}p" src/impl.cpp | grep -E "break|continue" | grep -v "//"; then
    echo "[FAIL] SR2: Found break/continue inside comparison loop"
    FAILED=1
  fi
fi

# SR3: Check for conditional branches on comparison results
echo "Checking SR3: No conditional branches on byte comparisons..."
if grep -n "for.*16" src/impl.cpp | head -1 > /tmp/loop_start.txt; then
  LOOP_START=$(grep -n "for.*16" src/impl.cpp | head -1 | cut -d: -f1)
  LOOP_END=$(tail -n +$LOOP_START src/impl.cpp | grep -n "}" | head -1 | cut -d: -f1)
  LOOP_END=$((LOOP_START + LOOP_END - 1))
  
  if sed -n "${LOOP_START},${LOOP_END}p" src/impl.cpp | grep -E "if.*\[.*\].*!=|if.*\[.*\].*==" | grep -v "//"; then
    echo "[FAIL] SR3: Found conditional branch on comparison result inside loop"
    FAILED=1
  else
    echo "[PASS] SR3"
  fi
else
  echo "[PASS] SR3"
fi

# SR4: Check that result is computed after loop
echo "Checking SR4: Result computed after loop completes..."
if grep -n "for.*16" src/impl.cpp | head -1 > /tmp/loop_start.txt; then
  LOOP_START=$(grep -n "for.*16" src/impl.cpp | head -1 | cut -d: -f1)
  LOOP_END=$(tail -n +$LOOP_START src/impl.cpp | grep -n "}" | head -1 | cut -d: -f1)
  LOOP_END=$((LOOP_START + LOOP_END - 1))
  
  # Check if return statement is after loop end
  RETURN_LINE=$(grep -n "return" src/impl.cpp | tail -1 | cut -d: -f1)
  if [ $RETURN_LINE -gt $LOOP_END ]; then
    echo "[PASS] SR4"
  else
    echo "[FAIL] SR4: Return statement not after loop completion"
    FAILED=1
  fi
else
  echo "[PASS] SR4"
fi

# SR5: Check for constant loop bound
echo "Checking SR5: Loop bound is constant 16..."
if grep -E "for.*i.*<.*16|for.*i.*16" src/impl.cpp | grep -v "//" > /dev/null; then
  echo "[PASS] SR5"
else
  echo "[FAIL] SR5: Loop bound is not constant 16"
  FAILED=1
fi

# Check for HLS loop_bound pragma
if grep -q "#pragma HLS loop_bound" src/impl.cpp; then
  echo "[PASS] Found HLS loop_bound pragma"
else
  echo "[WARN] Missing HLS loop_bound pragma (recommended)"
fi

if [ $FAILED -eq 0 ]; then
  echo "=== All Security Checks Passed ==="
  exit 0
else
  echo "=== Security Checks Failed ==="
  exit 1
fi
