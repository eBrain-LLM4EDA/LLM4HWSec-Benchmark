#!/usr/bin/env bash
# Serves ibm-granite/granite-8b-code-instruct-128k on an OpenAI-compatible
# vLLM endpoint. First run creates a conda env, bootstraps uv, installs vLLM
# via uv, and downloads the model from Hugging Face (Apache-2.0, no gating).
#
# Usage:
#   ./serve_granite_8b_code.sh                       # base model, foreground
#   PORT=9004 ./serve_granite_8b_code.sh              # custom port
#   DETACH=1 ./serve_granite_8b_code.sh               # run in background
#   CUDA_VISIBLE_DEVICES=3 ./serve_granite_8b_code.sh # pin a GPU
#
#   # Serve a locally pruned checkpoint instead of the base weights:
#   MODEL_OVERRIDE=/scratch/you/pruned/granite8b_shortgpt50 \
#     SERVED_NAME_SUFFIX=-shortgpt50pct \
#     ./serve_granite_8b_code.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DEFAULT_MODEL_SOURCE="ibm-granite/granite-8b-code-instruct-128k"
DEFAULT_SERVED_NAME="granite-8b-code-instruct"
DEFAULT_PORT=8004
DEFAULT_MAX_LEN=32768   # native context is 128K; capped here to control KV-cache memory

# shellcheck disable=SC1091
source ./lib.sh
setup_env
ensure_vllm
serve_model
