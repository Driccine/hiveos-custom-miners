#!/usr/bin/env bash
# HiveOS sources this file when generating the config. Never trust MINER_DIR:
# it can denote the shared custom miner parent instead of this package folder.
set -euo pipefail
umask 077

ORU_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="${ORU_DIR}/oru.env"
WALLET="${CUSTOM_TEMPLATE:-}"
RPC="${CUSTOM_URL:-http://127.0.0.1:8761}"
if [[ ! "$WALLET" =~ ^rg1q[a-z0-9]+$ ]]; then
  echo "ORU: wallet mainnet expected in 'Wallet and worker' (rg1q...)" >&2
  exit 1
fi
if [[ ! "$RPC" =~ ^https?:// ]]; then
  echo "ORU: Pool URL must be YOUR RIGOR node HTTP(S) RPC (not a Stratum pool)" >&2
  exit 1
fi
CUSTOM_USER_CONFIG="${CUSTOM_USER_CONFIG:-}"
if [[ -n "$CUSTOM_USER_CONFIG" ]]; then
  command -v jq >/dev/null || { echo "ORU: jq required for Extra config" >&2; exit 1; }
  jq -e 'type=="object"' <<<"$CUSTOM_USER_CONFIG" >/dev/null || { echo "ORU: Extra config must be JSON object" >&2; exit 1; }
fi
field() {
  if [[ -z "$CUSTOM_USER_CONFIG" ]]; then
    printf '\n'
  else
    jq -r --arg key "$1" '.[$key] // "" | tostring' <<<"$CUSTOM_USER_CONFIG"
  fi
}
RPC_USER="$(field rpc_user)"
RPC_PASS="$(field rpc_password)"
DEVICES="$(field devices)"
DEVICES="${DEVICES:-0}"
if [[ ! "$DEVICES" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
  echo "ORU: devices must be comma-separated GPU indexes, e.g. 0,1" >&2
  exit 1
fi
TEMP_CONFIG="$(mktemp "${ORU_DIR}/.oru-env.XXXXXXXX")"
trap 'rm -f -- "$TEMP_CONFIG"' EXIT
{
  printf 'export ORU_WALLET=%q\n' "$WALLET"
  printf 'export ORU_RPC_URL=%q\n' "$RPC"
  printf 'export ORU_RPC_USER=%q\n' "$RPC_USER"
  printf 'export ORU_RPC_PASSWORD=%q\n' "$RPC_PASS"
  printf 'export ORU_DEVICES=%q\n' "$DEVICES"
} > "$TEMP_CONFIG"
chmod 600 "$TEMP_CONFIG"
mv -f -- "$TEMP_CONFIG" "$CONFIG"
trap - EXIT
echo "ORU: config saved in ${CONFIG}. RPC credentials are not printed."
