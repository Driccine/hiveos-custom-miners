#!/usr/bin/env bash
set -euo pipefail
DIR="${MINER_DIR:-/hive/miners/custom/oru-native}"
source "${DIR}/oru.env"
LOG="/var/log/miner/oru-native/oru-native.log"
mkdir -p "$(dirname "${LOG}")"
[[ -x "${DIR}/oru-cuda" ]] || { echo "ORU CUDA binary missing in ${DIR}" >&2; exit 1; }
[[ -f "${DIR}/solo.py" && -f "${DIR}/rgrpow.py" ]] || { echo "ORU Python sources missing" >&2; exit 1; }
export PYTHONUNBUFFERED=1
python3 "${DIR}/solo.py" --cuda-bin "${DIR}/oru-cuda" \
  --devices "${ORU_DEVICES:-0}" 2>&1 | tee -a "${LOG}"
exit "${PIPESTATUS[0]}"
