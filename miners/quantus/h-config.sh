#!/usr/bin/env bash
set -euo pipefail
MINER_CONFIG="${MINER_DIR}/miner.conf"
NODE_ADDR="${CUSTOM_URL:-127.0.0.1:9833}"
EXTRA_ARGS="${CUSTOM_USER_CONFIG:-}"
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_COUNT="$(nvidia-smi --query-gpu=index --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ')"
else
  GPU_COUNT="0"
fi
if [[ "${GPU_COUNT}" -lt 1 ]]; then
  echo "Aucun GPU NVIDIA détecté."
  exit 1
fi
cat > "${MINER_CONFIG}" <<CFG
NODE_ADDR="${NODE_ADDR}"
GPU_COUNT="${GPU_COUNT}"
EXTRA_ARGS="${EXTRA_ARGS}"
CFG
