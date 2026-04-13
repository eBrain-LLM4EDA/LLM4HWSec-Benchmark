#!/bin/bash
set -e

# =============================================================================
# HLS Security Benchmark - Docker Entrypoint
# =============================================================================
#
# Modes:
#   1. Evaluation mode (default):
#      docker run --rm -v ./submissions:/data/submissions hls-security-benchmark
#
#   2. Interactive shell:
#      docker run --rm -it hls-security-benchmark bash
#
#   3. Direct bambu invocation:
#      docker run --rm -v ./code:/data/submissions hls-security-benchmark \
#          bambu /data/submissions/secure.cpp --top-fname=my_func
#
#   4. AST analysis only:
#      docker run --rm -v ./code:/data/submissions hls-security-benchmark \
#          python3 /benchmark/evaluation/analysis/ast_analyzer.py \
#          /data/submissions/secure.cpp
# =============================================================================

BENCHMARK_DIR="/benchmark"
EVAL_SCRIPT="${BENCHMARK_DIR}/evaluation/run_evaluation_v2.py"
EXAMPLES_DIR="${BENCHMARK_DIR}/examples"
SUBMISSIONS_DIR="/data/submissions"
OUTPUT_DIR="/data/output"

# ---- Check what we're being asked to do ----

# If first arg is "bash" or "sh", drop to shell
if [ "$1" = "bash" ] || [ "$1" = "sh" ]; then
    exec "$@"
fi

# If first arg is "bambu", pass everything to bambu directly
if [ "$1" = "bambu" ]; then
    exec "$@"
fi

# If first arg is "python3" or a .py file, run it directly
if [ "$1" = "python3" ] || [[ "$1" == *.py ]]; then
    exec "$@"
fi

# ---- Default: run evaluation ----

echo "============================================================"
echo "  HLS Security-Aware Code Generation Benchmark (Arda)"
echo "============================================================"
echo ""

# Check for submissions
if [ ! -d "$SUBMISSIONS_DIR" ] || [ -z "$(ls -A $SUBMISSIONS_DIR 2>/dev/null)" ]; then
    echo "No submissions found at ${SUBMISSIONS_DIR}"
    echo ""
    echo "Usage:"
    echo "  docker run --rm \\"
    echo "    -v \$(pwd)/llm_outputs:/data/submissions \\"
    echo "    -v \$(pwd)/results:/data/output \\"
    echo "    hls-security-benchmark --mode simulate"
    echo ""
    echo "Your submissions directory should have this structure:"
    echo "  llm_outputs/"
    echo "    01_aes_ift/"
    echo "      secure.cpp"
    echo "      vulnerability_report.md"
    echo "    02_memory_access_control/"
    echo "      secure.cpp"
    echo "      vulnerability_report.md"
    echo "    ..."
    echo ""
    echo "Running self-test against reference examples instead..."
    echo ""

    # Self-test: evaluate reference solutions
    mkdir -p /tmp/self_test
    for d in ${EXAMPLES_DIR}/*/; do
        eid=$(basename "$d")
        mkdir -p "/tmp/self_test/$eid"
        cp "$d/reference_secure.cpp" "/tmp/self_test/$eid/secure.cpp" 2>/dev/null || true
        cp "$d/vulnerability_report.md" "/tmp/self_test/$eid/vulnerability_report.md" 2>/dev/null || true
    done
    SUBMISSIONS_DIR="/tmp/self_test"
fi

# Report tool availability
echo "Tool availability:"
if command -v bambu &>/dev/null; then
    echo "  ✓ bambu (PandA-bambu HLS)"
else
    echo "  ✗ bambu (will use AST fallback for synthesis checks)"
fi
if command -v verilator &>/dev/null; then
    echo "  ✓ verilator (RTL co-simulation)"
else
    echo "  ✗ verilator"
fi
if python3 -c "import clang.cindex" &>/dev/null; then
    echo "  ✓ libclang (AST analysis)"
    # Verify stddef.h is findable
    STDDEF_CHECK=$(python3 -c "
import sys, os, glob
sys.path.insert(0, '/benchmark/evaluation')
from analysis.ast_analyzer import _get_system_include_args
args = _get_system_include_args()
if args:
    print(f'    include paths: {\" \".join(args[1::2])}')
else:
    print('    WARNING: no system include paths found - AST parsing may fail')
" 2>/dev/null)
    echo "$STDDEF_CHECK"
else
    echo "  ✗ libclang (will use regex fallback)"
fi
echo "  ✓ g++ (C-simulation with HLS stubs)"
echo ""

# Run evaluation
python3 "$EVAL_SCRIPT" \
    --input "$SUBMISSIONS_DIR" \
    --reference "$EXAMPLES_DIR" \
    --output "${OUTPUT_DIR}/evaluation_report.json" \
    "$@"

echo ""
echo "Report saved to: ${OUTPUT_DIR}/evaluation_report.json"

# Pretty-print summary if jq-like parsing is available
if [ -f "${OUTPUT_DIR}/evaluation_report.json" ]; then
    python3 -c "
import json, sys
with open('${OUTPUT_DIR}/evaluation_report.json') as f:
    r = json.load(f)
agg = r.get('aggregate', {})
print(f\"  Final grade: {agg.get('grade', 'N/A')}\")
print(f\"  Weighted score: {agg.get('difficulty_weighted', 0):.3f}\")
"
fi
