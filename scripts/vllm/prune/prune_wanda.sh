#!/usr/bin/env bash
# One-shot UNSTRUCTURED Wanda pruning (via llmcompressor) for any of the 4
# base models this benchmark serves, at a given sparsity ratio. Calibration
# only - no fine-tuning/retraining.
#
# Usage:
#   ./prune_wanda.sh --model qwen --sparsity 0.5
#   ./prune_wanda.sh --model deepseek --sparsity 0.25
#   ./prune_wanda.sh --model codellama --sparsity 0.75 --conda-env my_env
#   ./prune_wanda.sh --model /path/to/any/hf/checkpoint --sparsity 0.5
#
# --model accepts the short keys qwen/deepseek/codellama/granite (resolving
# to the same Hugging Face ids as ../serve_*.sh), or any other HF id / local
# checkpoint path.
#
# Output: pruned/<model-tag>_wanda<sparsity_pct>/ (override with
# --output, or the PRUNE_OUTPUT_BASE env var to change the base directory).
#
# Calibration defaults to C4 (128 samples x 2048 tokens, the standard
# Wanda-paper setting), falling back to WikiText-2 automatically if C4 is
# unreachable. Override with --calibration-dataset {c4,wikitext2},
# --num-calibration-samples N, --max-seq-length N.
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
: "${OUTPUT_DIR:=$PRUNE_OUTPUT_BASE/${MODEL_TAG}_wanda${sparsity_pct}}"

log "Model            : $MODEL_ID"
log "Sparsity         : $SPARSITY ($sparsity_pct% unstructured)"
log "Calibration      : $CALIBRATION_DATASET x $NUM_CALIBRATION_SAMPLES samples, max_seq_length=$MAX_SEQ_LENGTH"
log "Output           : $OUTPUT_DIR"

mkdir -p "$OUTPUT_DIR"
log_file="$LOG_DIR/prune_wanda_${MODEL_TAG}_${sparsity_pct}.log"
python3 "$PRUNE_DIR/wanda_prune.py" \
  --model "$MODEL_ID" \
  --output "$OUTPUT_DIR" \
  --sparsity "$SPARSITY" \
  --calibration-dataset "$CALIBRATION_DATASET" \
  --num-calibration-samples "$NUM_CALIBRATION_SAMPLES" \
  --max-seq-length "$MAX_SEQ_LENGTH" \
  2>&1 | tee "$log_file"

log "Done. Log saved to $log_file"
log "Serve it with:"
log "  MODEL_OVERRIDE=$OUTPUT_DIR SERVED_NAME_SUFFIX=-wanda${sparsity_pct}pct ../serve_<model>.sh"
