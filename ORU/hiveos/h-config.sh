#!/usr/bin/env bash
set -euo pipefail
umask 077
DIR="${MINER_DIR:-/hive/miners/custom/oru-native}"
CONFIG="${DIR}/oru.env"
WALLET="${CUSTOM_TEMPLATE:-}"
RPC="${CUSTOM_URL:-http://127.0.0.1:8761}"
if [[ ! "${WALLET}" =~ ^rg1q[a-z0-9]+$ ]]; then
  echo "ORU: wallet expected in Wallet and worker field (rg1q...)" >&2
  exit 1
fi
if [[ ! "${RPC}" =~ ^https?:// ]]; then
  echo "ORU: Pool URL must be YOUR node JSON-RPC URL (http://127.0.0.1:8761)" >&2
  exit 1
fi
# Extra config: JSON {"rpc_user":"...","rpc_password":"...","devices":"0,1"}.
CUSTOM_USER_CONFIG="${CUSTOM_USER_CONFIG:-}"
if [[ -n "${CUSTOM_USER_CONFIG}" ]]; then
  command -v jq >/dev/null || { echo "ORU: jq required" >&2; exit 1; }
  echo "${CUSTOM_USER_CONFIG}" | jq -e 'type=="object"' >/dev/null || { echo "ORU: Extra config must be JSON" >&2; exit 1; }
fi
field() { if [[ -z "${CUSTOM_USER_CONFIG}" ]]; then echo ""; else jq -r --arg key "$1" '.[$key] // ""' <<< "${CUSTOM_USER_CONFIG}"; fi; }
RPC_USER="$(field rpc_user)"
RPC_PASS="$(field rpc_password)"
DEVICES="$(field devices)"
DEVICES="${DEVICES:-0}"
if [[ ! "${DEVICES}" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
  echo "ORU: devices must be comma-separated GPU indexes" >&2; exit 1
fi
{
  printf 'export ORU_WALLET=%q\n' "$WALLET"
  printf 'export ORU_RPC_URL=%q\n' "$RPC"
  printf 'export ORU_RPC_USER=%q\n' "$RPC_USER"
  printf 'export ORU_RPC_PASSWORD=%q\n' "$RPC_PASS"
  printf 'export ORU_DEVICES=%q\n' "$DEVICES"
} > "$CONFIG"
chmod 600 "$CONFIG"
echo "ORU: config saved. RPC credentials are not printed."
