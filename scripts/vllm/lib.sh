#!/usr/bin/env bash
# Shared helpers sourced by every serve_<model>.sh script in this directory.
# Not meant to be run directly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.env"

log() { printf '[%(%Y-%m-%d %H:%M:%S)T] %s\n' -1 "$*"; }
die() { log "ERROR: $*"; exit 1; }

# -----------------------------------------------------------------------------
# 1. Python environment: conda. Idempotent - safe to re-run any time.
#    (No mamba dependency - plain `conda` only, since that's what's actually
#    on the HPC.)
# -----------------------------------------------------------------------------
setup_env() {
  command -v conda >/dev/null 2>&1 || die "conda not found on PATH. Load it first (e.g. 'module load anaconda' / 'module load miniconda') and re-run."

  if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    log "Creating conda env '$ENV_NAME' (python $PYTHON_VERSION)..."
    conda create -y -n "$ENV_NAME" "python=$PYTHON_VERSION"
  fi
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate "$ENV_NAME"
  log "Python environment ready: $(python3 --version) at $(command -v python3)"
}

# -----------------------------------------------------------------------------
# 2. uv (fast installer) + vLLM + fast HF download support. Idempotent.
#    uv itself is bootstrapped with a plain `pip install` the first time
#    (nothing external to download/curl), then used for every install after
#    that since it's much faster than pip for vLLM's large dependency tree.
# -----------------------------------------------------------------------------
ensure_vllm() {
  if ! command -v uv >/dev/null 2>&1; then
    log "Installing uv into '$ENV_NAME' (one-time bootstrap)..."
    pip install -q -U pip
    pip install -q uv
  fi
  log "uv version: $(uv --version)"

  local want_pkg="vllm"
  [[ -n "$VLLM_VERSION" ]] && want_pkg="vllm==$VLLM_VERSION"
  local py_bin
  py_bin="$(command -v python3)"
  if ! python3 -c "import vllm" >/dev/null 2>&1; then
    log "Installing $want_pkg (first run only, this can take a few minutes)..."
    uv pip install --python "$py_bin" "$want_pkg" "hf_transfer" "huggingface_hub[cli]"
  fi
  log "vLLM version: $(python3 -c 'import vllm; print(vllm.__version__)')"
  mkdir -p "$HF_HOME" "$LOG_DIR"
}

# -----------------------------------------------------------------------------
# 3. Gated repos (e.g. CodeLlama) need a Hugging Face token that has accepted
#    the model's license on the HF website. Fails fast with clear next steps
#    instead of letting the download 401 deep inside vLLM startup.
# -----------------------------------------------------------------------------
check_hf_auth() {
  local model_source="$1"
  [[ -d "$model_source" ]] && return 0   # local checkpoint path, not a HF id
  if [[ -n "${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-}}" ]]; then
    return 0
  fi
  if python3 -c "
from huggingface_hub import whoami
whoami()
" >/dev/null 2>&1; then
    return 0
  fi
  die "'$model_source' is a gated Hugging Face repo. Accept its license at
  https://huggingface.co/$model_source, then authenticate with either:
    huggingface-cli login
  or:
    export HF_TOKEN=hf_xxx
  and re-run this script."
}

# -----------------------------------------------------------------------------
# 4. Launch. DEFAULT_MODEL_SOURCE/DEFAULT_SERVED_NAME/DEFAULT_PORT/
#    DEFAULT_MAX_LEN come from the calling serve_<model>.sh; any of them can
#    be overridden at invocation time via env vars (see each script's header
#    comment for examples, e.g. MODEL_OVERRIDE to point at a local pruned
#    checkpoint instead of the base Hugging Face weights).
# -----------------------------------------------------------------------------
serve_model() {
  local model_source="${MODEL_OVERRIDE:-$DEFAULT_MODEL_SOURCE}"
  local served_name="${SERVED_NAME:-$DEFAULT_SERVED_NAME}${SERVED_NAME_SUFFIX:-}"
  local port="${PORT:-$DEFAULT_PORT}"
  local max_len="${MAX_MODEL_LEN:-$DEFAULT_MAX_LEN}"

  check_hf_auth "$model_source"

  log "Model source     : $model_source"
  log "Served as        : $served_name"
  log "Port             : $port"
  log "Max context      : $max_len"
  log "Tensor parallel  : $TP_SIZE"
  log "GPU(s)           : ${CUDA_VISIBLE_DEVICES:-<all visible>}"
  log "HF cache         : $HF_HOME"
  log "API key          : $VLLM_API_KEY"

  local log_file="$LOG_DIR/${served_name}.log"
  log "Logging to $log_file"

  local -a cmd=(
    vllm serve "$model_source"
    --served-model-name "$served_name"
    --port "$port"
    --host 0.0.0.0
    --api-key "$VLLM_API_KEY"
    --dtype "$DTYPE"
    --gpu-memory-utilization "$GPU_MEM_UTIL"
    --tensor-parallel-size "$TP_SIZE"
    --max-model-len "$max_len"
    --trust-remote-code
  )
  # shellcheck disable=SC2206
  [[ -n "${EXTRA_VLLM_ARGS:-}" ]] && cmd+=($EXTRA_VLLM_ARGS)

  log "Launch command: ${cmd[*]}"

  if [[ "${DETACH:-0}" == "1" ]]; then
    nohup "${cmd[@]}" >"$log_file" 2>&1 &
    local pid=$!
    echo "$pid" > "$LOG_DIR/${served_name}.pid"
    log "Started in background, PID=$pid"
    log "Stop it with: kill \$(cat $LOG_DIR/${served_name}.pid)  (or ./stop_server.sh $served_name)"
    wait_for_health "$port" "$served_name" "$log_file"
  else
    log "Running in foreground - Ctrl+C to stop. (set DETACH=1 to background it instead)"
    "${cmd[@]}" 2>&1 | tee "$log_file"
  fi
}

wait_for_health() {
  local port="$1" served_name="$2" log_file="$3"
  log "Waiting for server to become healthy on port $port ..."
  for _ in $(seq 1 180); do
    if curl -sf "http://localhost:${port}/health" >/dev/null 2>&1; then
      log "Server is healthy."
      print_ready_banner "$port" "$served_name"
      return 0
    fi
    sleep 5
  done
  log "Server did not become healthy within 15 minutes - check $log_file"
  return 1
}

print_ready_banner() {
  local port="$1" served_name="$2"
  local host
  host="$(hostname -f 2>/dev/null || hostname)"
  cat <<EOF

============================================================
vLLM OpenAI-compatible server is ready.
  Model      : $served_name
  Base URL   : http://${host}:${port}/v1
  API key    : ${VLLM_API_KEY}

  Test with:
    curl http://${host}:${port}/v1/models -H "Authorization: Bearer ${VLLM_API_KEY}"

  Point an OpenAI-compatible client (e.g. this repo's OpenRouterLLM) at it:
    export OPENROUTER_API_KEY="${VLLM_API_KEY}"
    # and set base_url: "http://${host}:${port}/v1" in the pipeline config,
    # model: "${served_name}" in the agent config.
============================================================

EOF
}
