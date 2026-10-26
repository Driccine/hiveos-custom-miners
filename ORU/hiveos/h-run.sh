#!/usr/bin/env bash
set -euo pipefail
# h-config.sh writes the env NEXT TO THE SCRIPTS. Resolve the same directory.
ORU_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="${ORU_DIR}/oru.env"
LOG="${ORU_LOG_FILE:-/var/log/miner/oru-native/oru-native.log}"

if [[ ! -f "$CONFIG" ]]; then
  echo "ORU: missing config: $CONFIG. Run h-config.sh before h-run.sh." >&2
  exit 1
fi
source "$CONFIG"
[[ -x "${ORU_DIR}/oru-cuda" ]] || { echo "ORU: CUDA executable missing in ${ORU_DIR}" >&2; exit 1; }
[[ -f "${ORU_DIR}/solo.py" && -f "${ORU_DIR}/rgrpow.py" ]] || { echo "ORU: missing Python sources" >&2; exit 1; }
mkdir -p "$(dirname -- "$LOG")"
export PYTHONUNBUFFERED=1
python3 "${ORU_DIR}/solo.py" --cuda-bin "${ORU_DIR}/oru-cuda" \
  --devices "${ORU_DEVICES:-0}" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
