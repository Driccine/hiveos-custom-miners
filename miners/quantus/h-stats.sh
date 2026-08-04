#!/usr/bin/env bash
set -euo pipefail
API_PORT="${CUSTOM_API_PORT:-9900}"
METRICS_URL="http://127.0.0.1:${API_PORT}/metrics"
temps='[]'; fans='[]'; powers='[]'
if command -v nvidia-smi >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
  temps="$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | jq -Rsc 'split("\n") | map(select(length>0) | tonumber)')"
  fans="$(nvidia-smi --query-gpu=fan.speed --format=csv,noheader,nounits 2>/dev/null | jq -Rsc 'split("\n") | map(select(length>0) | tonumber)')"
  powers="$(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits 2>/dev/null | jq -Rsc 'split("\n") | map(select(length>0) | tonumber)')"
fi
uptime="$(ps -eo etimes,cmd | awk '/quantus-miner serve/ && !/awk/ {print $1; exit}')"; uptime="${uptime:-0}"
hashrate=0
if command -v curl >/dev/null 2>&1; then
  metrics="$(curl -fsS --max-time 2 "${METRICS_URL}" 2>/dev/null || true)"
  if [[ -n "${metrics}" ]]; then
    hashrate="$(printf '%s\n' "${metrics}" | awk '/hashrate/ && $1 !~ /^#/ {sum += $NF} END {print sum+0}')"
  fi
fi
jq -nc --argjson hs "[${hashrate}]" --arg hs_units "hs" --argjson temp "${temps}" --argjson fan "${fans}" --argjson power "${powers}" --argjson uptime "${uptime}" --argjson ar '[0,0]' --arg algo 'qpow' --arg ver '0.1.0-dev' '{hs:$hs,hs_units:$hs_units,temp:$temp,fan:$fan,power:$power,uptime:$uptime,ar:$ar,algo:$algo,ver:$ver}'
