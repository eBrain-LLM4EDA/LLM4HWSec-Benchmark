#!/usr/bin/env bash
# Serves codellama/CodeLlama-7b-Instruct-hf on an OpenAI-compatible vLLM
# endpoint. First run creates a conda/venv env, installs vLLM, and downloads
# the model from Hugging Face.
#
# NOTE: this is a GATED repo. Before running for the first time:
#   1. Accept the license at https://huggingface.co/codellama/CodeLlama-7b-Instruct-hf
#   2. Authenticate on this machine: `huggingface-cli login`, or
#      `export HF_TOKEN=hf_xxx`
#
# Usage:
#   ./serve_codellama_7b.sh                       # base model, foreground
#   PORT=9003 ./serve_codellama_7b.sh              # custom port
#   DETACH=1 ./serve_codellama_7b.sh               # run in background
#   CUDA_VISIBLE_DEVICES=2 ./serve_codellama_7b.sh # pin a GPU
#
#   # Serve a locally pruned checkpoint instead of the base weights:
#   MODEL_OVERRIDE=/scratch/you/pruned/codellama7b_llmpruner50 \
#     SERVED_NAME_SUFFIX=-llmpruner50pct \
#     ./serve_codellama_7b.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

DEFAULT_MODEL_SOURCE="codellama/CodeLlama-7b-Instruct-hf"
DEFAULT_SERVED_NAME="codellama-7b-instruct"
DEFAULT_PORT=8003
DEFAULT_MAX_LEN=16384   # base 4K, RoPE-scaled to 16K by the model config

# shellcheck disable=SC1091
source ./lib.sh
setup_env
ensure_vllm
serve_model
