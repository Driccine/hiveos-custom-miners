#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
INSTALL="$TMP/installed/oru-native"
mkdir -p "$INSTALL"
cp "$ROOT/ORU/hiveos/h-config.sh" "$ROOT/ORU/hiveos/h-run.sh" "$INSTALL/"
printf '#!/bin/bash\nexit 0\n' > "$INSTALL/oru-cuda"
chmod +x "$INSTALL/oru-cuda"
touch "$INSTALL/rgrpow.py"
cat > "$INSTALL/solo.py" <<'PY'
import os
assert os.environ["ORU_WALLET"] == "rg1qintegrationtest"
assert os.environ["ORU_RPC_URL"] == "http://127.0.0.1:8761"
assert os.environ["ORU_DEVICES"] == "0"
print("ORU_HIVE_PATHS_OK")
PY
# Hive can have MINER_DIR pointing at a parent or unrelated directory.
export MINER_DIR="$TMP/wrong-base"
export CUSTOM_TEMPLATE="rg1qintegrationtest"
export CUSTOM_URL="http://127.0.0.1:8761"
export CUSTOM_USER_CONFIG=""
export ORU_LOG_FILE="$TMP/rig.log"
(
  cd "$TMP"
  bash "$INSTALL/h-config.sh"
)
[[ -f "$INSTALL/oru.env" ]] || { echo "Config was not written beside scripts" >&2; exit 1; }
[[ ! -e "$MINER_DIR/oru.env" ]] || { echo "Config was written to incorrect MINER_DIR" >&2; exit 1; }
OUTPUT="$(cd / && bash "$INSTALL/h-run.sh")"
grep -q "ORU_HIVE_PATHS_OK" <<< "$OUTPUT"
printf 'ORU Hive config/run path integration PASS\n'
