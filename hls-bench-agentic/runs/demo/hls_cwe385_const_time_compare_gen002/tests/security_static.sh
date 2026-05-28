#!/bin/bash
set -e
echo "[INFO] Running static security analysis"

if [ ! -f src/impl.cpp ]; then
  echo "[FAIL] SR2: src/impl.cpp not found"
  exit 1
fi

strip_comments() {
  sed 's|//.*$||g' "$1" | sed ':a;N;$!ba;s|/\*.*\*/||g'
}

IMPL_STRIPPED=$(mktemp)
strip_comments src/impl.cpp > "$IMPL_STRIPPED"

SR2_FAIL=0
if grep -n 'return' "$IMPL_STRIPPED" | grep -v '^[0-9]*:[[:space:]]*return[[:space:]]*[^;]*;[[:space:]]*$' | grep -q .; then
  LOOP_START=$(grep -n 'for\|while' "$IMPL_STRIPPED" | head -1 | cut -d: -f1)
  LOOP_END=$(tail -n +"$LOOP_START" "$IMPL_STRIPPED" | grep -n '}' | head -1 | cut -d: -f1)
  if [ -n "$LOOP_START" ] && [ -n "$LOOP_END" ]; then
    LOOP_END=$((LOOP_START + LOOP_END))
    if sed -n "${LOOP_START},${LOOP_END}p" "$IMPL_STRIPPED" | grep -q 'return'; then
      echo "[FAIL] SR2: Early return detected inside loop body"
      SR2_FAIL=1
    fi
  fi
fi

if grep -E 'break[[:space:]]*;|continue[[:space:]]*;' "$IMPL_STRIPPED" | grep -q .; then
  echo "[FAIL] SR2: break or continue statement detected"
  SR2_FAIL=1
fi

if [ $SR2_FAIL -eq 0 ]; then
  echo "[PASS] SR2: No early termination patterns detected"
fi

SR4_FAIL=0
if grep -E 'if[[:space:]]*\([^)]*\[[^]]*\][^)]*\)' "$IMPL_STRIPPED" | grep -q .; then
  if ! grep -E 'if[[:space:]]*\([^)]*\[[^]]*\][^)]*\)' "$IMPL_STRIPPED" | grep -q '#pragma'; then
    echo "[FAIL] SR4: Secret-dependent conditional branch detected"
    SR4_FAIL=1
  fi
fi

if grep -E '&&|\|\|' "$IMPL_STRIPPED" | grep -E '\[[^]]*\]' | grep -q .; then
  echo "[FAIL] SR4: Short-circuit operator on array element detected"
  SR4_FAIL=1
fi

if grep -E '\?[^:]*:' "$IMPL_STRIPPED" | grep -E '\[[^]]*\]' | grep -q .; then
  TERNARY_LINE=$(grep -n -E '\?[^:]*:' "$IMPL_STRIPPED" | grep -E '\[[^]]*\]' | head -1)
  if echo "$TERNARY_LINE" | grep -v -E 'test|Test|TEST|tb_|TB_' | grep -q .; then
    echo "[FAIL] SR4: Ternary operator with secret-dependent condition detected"
    SR4_FAIL=1
  fi
fi

if [ $SR4_FAIL -eq 0 ]; then
  echo "[PASS] SR4: No secret-dependent branches detected"
fi

SR5_FAIL=0
if ! grep -E '\^|\||&' "$IMPL_STRIPPED" | grep -q .; then
  echo "[FAIL] SR5: No bitwise operations detected for accumulation"
  SR5_FAIL=1
fi

if grep -E 'if[[:space:]]*\([^)]*==[^)]*\).*return' "$IMPL_STRIPPED" | grep -q .; then
  echo "[FAIL] SR5: Conditional return based on comparison detected"
  SR5_FAIL=1
fi

if [ $SR5_FAIL -eq 0 ]; then
  echo "[PASS] SR5: Bitwise accumulation pattern detected"
fi

rm -f "$IMPL_STRIPPED"

if [ $SR2_FAIL -eq 0 ] && [ $SR4_FAIL -eq 0 ] && [ $SR5_FAIL -eq 0 ]; then
  exit 0
else
  exit 1
fi
