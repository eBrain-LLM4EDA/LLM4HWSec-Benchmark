#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_WORKSPACE="runs/demo/hls_cwe385_const_time_compare"

WORKSPACE="${1:-${DEFAULT_WORKSPACE}}"
if [ $# -gt 0 ]; then
  shift
fi

if [ ! -d "${PROJECT_ROOT}/${WORKSPACE}" ] && [ ! -d "${WORKSPACE}" ]; then
  echo "[FAIL] Workspace not found: ${WORKSPACE}" >&2
  exit 1
fi

if [ -d "${PROJECT_ROOT}/${WORKSPACE}" ]; then
  HLS_BENCH_WORKSPACE="$(cd "${PROJECT_ROOT}/${WORKSPACE}" && pwd)"
else
  HLS_BENCH_WORKSPACE="$(cd "${WORKSPACE}" && pwd)"
fi
export HLS_BENCH_WORKSPACE

if [ $# -gt 0 ]; then
  HLS_BENCH_TEST_COMMAND="$*"
else
  HLS_BENCH_TEST_COMMAND="bash tests/run_csim.sh && bash tests/run_synth.sh && bash tests/run_cosim.sh && bash tests/run_rtl_security.sh"
fi
export HLS_BENCH_TEST_COMMAND

cd "${PROJECT_ROOT}"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "[FAIL] Docker Compose is not available. Install Docker Desktop or Docker Compose v2." >&2
  exit 1
fi

"${COMPOSE[@]}" build bambu-tests
"${COMPOSE[@]}" run --rm bambu-tests
