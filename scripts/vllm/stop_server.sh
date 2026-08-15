#!/usr/bin/env bash
# Stops a server started with DETACH=1 by one of the serve_*.sh scripts.
#
# Usage:
#   ./stop_server.sh qwen2.5-coder-7b-instruct
#   ./stop_server.sh                              # stops all known PID files
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
# shellcheck disable=SC1091
source ./common.env

stop_one() {
  local pid_file="$1"
  local name
  name="$(basename "$pid_file" .pid)"
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    echo "[$name] not running (stale pid file, removing)"
    rm -f "$pid_file"
    return
  fi
  echo "[$name] stopping PID $pid ..."
  kill "$pid"
  rm -f "$pid_file"
}

if [[ $# -ge 1 ]]; then
  stop_one "$LOG_DIR/$1.pid"
else
  shopt -s nullglob
  files=("$LOG_DIR"/*.pid)
  if [[ ${#files[@]} -eq 0 ]]; then
    echo "No running servers found (no .pid files in $LOG_DIR)."
  fi
  for f in "${files[@]}"; do
    stop_one "$f"
  done
fi
