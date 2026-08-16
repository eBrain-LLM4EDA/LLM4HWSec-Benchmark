#!/usr/bin/env bash
# Serves deepseek-ai/deepseek-coder-6.7b-instruct on an OpenAI-compatible
# vLLM endpoint. First run creates a conda env, bootstraps uv, installs vLLM
# via uv, and downloads the model from Hugging Face (open weights, no gating).
#
# Usage:
#   ./serve_deepseek_coder_6.7b.sh                       # base model, foreground
#   PORT=9002 ./serve_deepseek_coder_6.7b.sh              # custom port
#   DETACH=1 ./serve_deepseek_coder_6.7b.sh               # run in background
#   CUDA_VISIBLE_DEVICES=1 ./serve_deepseek_coder_6.7b.sh # pin a GPU
#
#   # Serve a locally pruned checkpoint instead of the base weights:
#   MODEL_OVERRIDE=/scratch/you/pruned/dsc6.7b_sparsegpt50 \
#     SERVED_NAME_SUFFIX=-sparsegpt50pct \
#     ./serve_deepseek_coder_6.7b.sh
#
#   # Use/create a specific conda env instead of the default "hwsec-vllm"
#   # (e.g. one you already have with vLLM installed):
#   ./serve_deepseek_coder_6.7b.sh --conda-env my_existing_env
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DEFAULT_MODEL_SOURCE="deepseek-ai/deepseek-coder-6.7b-instruct"
DEFAULT_SERVED_NAME="deepseek-coder-6.7b-instruct"
DEFAULT_PORT=8002
DEFAULT_MAX_LEN=16384   # model's native max context

# shellcheck disable=SC1091
source ./lib.sh
parse_conda_env_arg "$@"
setup_env
ensure_vllm
serve_model
