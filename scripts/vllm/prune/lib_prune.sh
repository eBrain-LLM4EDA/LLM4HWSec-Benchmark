#!/usr/bin/env bash
# Shared helpers sourced by prune_wanda.sh / prune_shortgpt.sh. Not meant to
# be run directly.
set -euo pipefail

PRUNE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VLLM_DIR="$(cd "$PRUNE_DIR/.." && pwd)"

# Track whether the caller already exported ENV_NAME / LOG_DIR *before* we
# source ../lib.sh (which applies its own serving-specific defaults via
# common.env: ENV_NAME=hwsec-vllm, LOG_DIR=$PWD/logs). If they didn't,
# override both afterward:
#   - ENV_NAME: pruning needs llmcompressor/torch/datasets, not vllm, so it
#     gets its own conda env by default rather than reusing the serving one.
#   - LOG_DIR: common.env's "$PWD/logs" would resolve to a second,
#     un-gitignored prune/logs/ directory, since these scripts `cd` into
#     prune/ before sourcing it. Share ../logs instead (already covered by
#     ../.gitignore).
[[ -z "${ENV_NAME+x}" ]] && _env_name_was_default=1 || _env_name_was_default=0
[[ -z "${LOG_DIR+x}" ]] && _log_dir_was_default=1 || _log_dir_was_default=0

# shellcheck disable=SC1091
source "$VLLM_DIR/lib.sh"   # gives us: log, die, parse_conda_env_arg, setup_env, check_hf_auth

if [[ "$_env_name_was_default" == "1" ]]; then
  ENV_NAME="${PRUNE_ENV_NAME:-hwsec-prune}"
fi
if [[ "$_log_dir_was_default" == "1" ]]; then
  LOG_DIR="$VLLM_DIR/logs"
fi
unset _env_name_was_default _log_dir_was_default

# Default location for pruned checkpoints - colocated with the serving
# scripts for discoverability (see ../.gitignore - never committed). Override
# with PRUNE_OUTPUT_BASE or a script's --output.
PRUNE_OUTPUT_BASE="${PRUNE_OUTPUT_BASE:-$VLLM_DIR/pruned}"

# -----------------------------------------------------------------------------
# Resolve a short model key (matching the DEFAULT_* values in ../serve_*.sh)
# to its Hugging Face id and a filesystem-safe tag used to name the output
# directory. Anything not in the table is treated as a raw HF id or local
# checkpoint path, with the tag derived from its basename.
# -----------------------------------------------------------------------------
resolve_model() {
  local key="$1"
  case "$key" in
    qwen)
      MODEL_ID="Qwen/Qwen2.5-Coder-7B-Instruct"
      MODEL_TAG="qwen2.5-coder-7b-instruct"
      ;;
    deepseek)
      MODEL_ID="deepseek-ai/deepseek-coder-6.7b-instruct"
      MODEL_TAG="deepseek-coder-6.7b-instruct"
      ;;
    codellama)
      MODEL_ID="codellama/CodeLlama-7b-Instruct-hf"
      MODEL_TAG="codellama-7b-instruct"
      ;;
    granite)
      MODEL_ID="ibm-granite/granite-8b-code-instruct-128k"
      MODEL_TAG="granite-8b-code-instruct"
      ;;
    *)
      MODEL_ID="$key"
      # printf (not `basename | tr`) so no trailing newline ever enters the
      # `tr -c` step below - otherwise the newline itself gets converted into
      # a literal trailing '-' before command substitution can strip it.
      local base
      base="$(basename "$key")"
      MODEL_TAG="$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '-')"
      ;;
  esac
}

# -----------------------------------------------------------------------------
# llmcompressor + a compatible torch/transformers/datasets stack. Separate
# from ../lib.sh's ensure_vllm() - a different, lighter dependency set, and
# these scripts never launch a server so vLLM itself is not required here.
# -----------------------------------------------------------------------------
ensure_prune_deps() {
  if ! command -v uv >/dev/null 2>&1; then
    log "Installing uv into '$ENV_NAME' (one-time bootstrap)..."
    pip install -q -U pip
    pip install -q uv
  fi
  local py_bin
  py_bin="$(command -v python3)"
  if ! python3 -c "import llmcompressor" >/dev/null 2>&1; then
    log "Installing llmcompressor and dependencies into '$ENV_NAME' (first run only, this can take a few minutes)..."
    uv pip install --python "$py_bin" llmcompressor datasets hf_transfer "huggingface_hub[cli]"
  fi
  log "llmcompressor version: $(python3 -c 'import llmcompressor; print(getattr(llmcompressor, "__version__", "unknown"))')"
  mkdir -p "$HF_HOME" "$LOG_DIR" "$PRUNE_OUTPUT_BASE"
}

# -----------------------------------------------------------------------------
# Common --model/--sparsity/--conda-env CLI parsing shared by prune_wanda.sh
# and prune_shortgpt.sh. Populates MODEL_ID/MODEL_TAG (via resolve_model) and
# SPARSITY; --conda-env/-e overrides ENV_NAME directly (same convention as
# ../lib.sh's parse_conda_env_arg).
# -----------------------------------------------------------------------------
parse_prune_args() {
  local model_key="" sparsity=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model|-m)
        [[ $# -ge 2 ]] || die "--model requires a value, e.g. --model qwen (short keys: qwen, deepseek, codellama, granite - or any HF id / local path)"
        model_key="$2"; shift 2 ;;
      --model=*)
        model_key="${1#*=}"; shift ;;
      --sparsity|-s)
        [[ $# -ge 2 ]] || die "--sparsity requires a value, e.g. --sparsity 0.5"
        sparsity="$2"; shift 2 ;;
      --sparsity=*)
        sparsity="${1#*=}"; shift ;;
      --conda-env|-e)
        [[ $# -ge 2 ]] || die "--conda-env requires a value"
        ENV_NAME="$2"; shift 2 ;;
      --conda-env=*)
        ENV_NAME="${1#*=}"; shift ;;
      --output|-o)
        [[ $# -ge 2 ]] || die "--output requires a value"
        OUTPUT_DIR="$2"; shift 2 ;;
      --output=*)
        OUTPUT_DIR="${1#*=}"; shift ;;
      --calibration-dataset)
        [[ $# -ge 2 ]] || die "--calibration-dataset requires a value (c4 or wikitext2)"
        CALIBRATION_DATASET="$2"; shift 2 ;;
      --num-calibration-samples)
        [[ $# -ge 2 ]] || die "--num-calibration-samples requires a value"
        NUM_CALIBRATION_SAMPLES="$2"; shift 2 ;;
      --max-seq-length)
        [[ $# -ge 2 ]] || die "--max-seq-length requires a value"
        MAX_SEQ_LENGTH="$2"; shift 2 ;;
      *)
        die "Unknown argument: $1 (supported: --model KEY, --sparsity N, --conda-env NAME, --output DIR, --calibration-dataset {c4,wikitext2}, --num-calibration-samples N, --max-seq-length N)"
        ;;
    esac
  done
  [[ -n "$model_key" ]] || die "--model is required, e.g. --model qwen (short keys: qwen, deepseek, codellama, granite - or any HF id / local path)"
  [[ -n "$sparsity" ]] || die "--sparsity is required, e.g. --sparsity 0.5"

  resolve_model "$model_key"
  SPARSITY="$sparsity"
}
