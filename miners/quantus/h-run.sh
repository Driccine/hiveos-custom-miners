#!/usr/bin/env bash
set -euo pipefail
cd "${MINER_DIR}"
CONFIG="${MINER_DIR}/miner.conf"
BIN="${MINER_DIR}/quantus-miner"
[[ -x "${BIN}" ]] || { echo "Binaire absent ou non exécutable : ${BIN}"; exit 1; }
[[ -f "${CONFIG}" ]] || { echo "Configuration absente : ${CONFIG}"; exit 1; }
source "${CONFIG}"
export RUST_LOG="${RUST_LOG:-info}"
export WGPU_BACKEND="${WGPU_BACKEND:-vulkan}"
CMD=("${BIN}" serve --node-addr "${NODE_ADDR}" --cpu-workers 0 --gpu-devices "${GPU_COUNT}" --metrics-port 9900)
if [[ -n "${EXTRA_ARGS}" ]]; then
  read -r -a EXTRA_ARRAY <<< "${EXTRA_ARGS}"
  CMD+=("${EXTRA_ARRAY[@]}")
fi
exec "${CMD[@]}"
