#!/usr/bin/env bash
set -euo pipefail

cd /workspace

if [[ $# -eq 0 ]]; then
  set -- bench
fi

case "$1" in
  bench)
    shift
    python3 run_benchmark.py \
      --examples examples \
      --submissions submissions \
      --results results/evaluation_report.json \
      "$@"
    ;;
  test)
    shift
    python3 -m unittest discover -s tests -p "test_*.py" "$@"
    ;;
  shell)
    shift
    exec bash "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
