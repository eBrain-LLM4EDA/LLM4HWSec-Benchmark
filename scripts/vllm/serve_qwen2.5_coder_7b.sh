#!/usr/bin/env bash
# Serves Qwen/Qwen2.5-Coder-7B-Instruct on an OpenAI-compatible vLLM endpoint.
# First run creates a conda env, bootstraps uv, installs vLLM via uv, and
# downloads the model from Hugging Face (open weights, no gating) - all
# handled automatically.
#
# Usage:
#   ./serve_qwen2.5_coder_7b.sh                       # base model, foreground
#   PORT=9001 ./serve_qwen2.5_coder_7b.sh              # custom port
#   DETACH=1 ./serve_qwen2.5_coder_7b.sh               # run in background
#   CUDA_VISIBLE_DEVICES=0 ./serve_qwen2.5_coder_7b.sh # pin a GPU
#
#   # Serve a locally pruned checkpoint instead of the base weights, keeping
#   # everything else (port, max-len, dtype) the same, with a distinct name
#   # so results don't collide with the base model's:
#   MODEL_OVERRIDE=/scratch/you/pruned/qwen25coder7b_wanda50 \
#     SERVED_NAME_SUFFIX=-wanda50pct \
#     ./serve_qwen2.5_coder_7b.sh
#
#   # Use/create a specific conda env instead of the default "hwsec-vllm"
#   # (e.g. one you already have with vLLM installed):
#   ./serve_qwen2.5_coder_7b.sh --conda-env my_existing_env
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DEFAULT_MODEL_SOURCE="Qwen/Qwen2.5-Coder-7B-Instruct"
DEFAULT_SERVED_NAME="qwen2.5-coder-7b-instruct"
DEFAULT_PORT=8001
DEFAULT_MAX_LEN=32768   # native context is 128K; capped here to control KV-cache memory

# shellcheck disable=SC1091
source ./lib.sh
parse_conda_env_arg "$@"
setup_env
ensure_vllm
serve_model
