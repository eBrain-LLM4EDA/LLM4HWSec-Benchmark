#!/usr/bin/env bash
# ShortGPT-style structured layer pruning (no fine-tuning) for any of the 4
# base models this benchmark serves, at a given fraction of decoder layers
# removed. See prune/shortgpt_prune.py for the Block Influence (BI) scoring
# method (arXiv:2403.03853).
#
# Usage:
#   ./prune_shortgpt.sh --model qwen --sparsity 0.25
#   ./prune_shortgpt.sh --model granite --sparsity 0.5 --conda-env my_env
#
# --model accepts the short keys qwen/deepseek/codellama/granite (resolving
# to the same Hugging Face ids as ../serve_*.sh), or any other HF id / local
# checkpoint path. Note: --sparsity here is the FRACTION OF LAYERS REMOVED,
# not a weight-sparsity ratio - it is not directly comparable in magnitude to
# prune_wanda.sh's --sparsity. Expect much steeper quality loss at high
# values (e.g. 0.75) than the equivalent Wanda weight-sparsity ratio.
#
# Output: pruned/<model-tag>_shortgpt<sparsity_pct>/ (override with
# --output, or the PRUNE_OUTPUT_BASE env var to change the base directory).
#
# Calibration defaults to C4 (128 samples x 2048 tokens), falling back to
# WikiText-2 automatically if C4 is unreachable. Override with
# --calibration-dataset {c4,wikitext2}, --num-calibration-samples N,
# --max-seq-length N.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CALIBRATION_DATASET="c4"
NUM_CALIBRATION_SAMPLES=128
MAX_SEQ_LENGTH=2048
OUTPUT_DIR=""

# shellcheck disable=SC1091
source ./lib_prune.sh
parse_prune_args "$@"
setup_env
ensure_prune_deps
check_hf_auth "$MODEL_ID"

sparsity_pct="$(awk -v s="$SPARSITY" 'BEGIN{printf "%d", s*100}')"
: "${OUTPUT_DIR:=$PRUNE_OUTPUT_BASE/${MODEL_TAG}_shortgpt${sparsity_pct}}"

log "Model            : $MODEL_ID"
log "Layer removal    : $SPARSITY ($sparsity_pct% of decoder layers)"
log "Calibration      : $CALIBRATION_DATASET x $NUM_CALIBRATION_SAMPLES samples, max_seq_length=$MAX_SEQ_LENGTH"
log "Output           : $OUTPUT_DIR"

mkdir -p "$OUTPUT_DIR"
log_file="$LOG_DIR/prune_shortgpt_${MODEL_TAG}_${sparsity_pct}.log"
python3 "$PRUNE_DIR/shortgpt_prune.py" \
  --model "$MODEL_ID" \
  --output "$OUTPUT_DIR" \
  --sparsity "$SPARSITY" \
  --calibration-dataset "$CALIBRATION_DATASET" \
  --num-calibration-samples "$NUM_CALIBRATION_SAMPLES" \
  --max-seq-length "$MAX_SEQ_LENGTH" \
  2>&1 | tee "$log_file"

log "Done. Log saved to $log_file"
log "Serve it with:"
log "  MODEL_OVERRIDE=$OUTPUT_DIR SERVED_NAME_SUFFIX=-shortgpt${sparsity_pct}pct ../serve_<model>.sh"
