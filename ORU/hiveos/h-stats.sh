#!/usr/bin/env bash
# Sourced by the Hive OS agent: must assign $khs and $stats.
LOG="/var/log/miner/oru-native/oru-native.log"
rate=0
if [[ -r "$LOG" ]]; then
  rate="$(grep -oE 'avg_hs=[0-9.]+' "$LOG" | tail -1 | cut -d= -f2 || true)"
  rate="${rate:-0}"
fi
khs="$(awk -v rate="$rate" 'BEGIN { printf "%.3f", rate/1000 }')"
if command -v jq >/dev/null 2>&1; then
  stats="$(jq -nc --argjson hs "$khs" '{"hs":[$hs],"hs_units":"khs","temp":[],"fan":[],"uptime":0,"ar":[0,0],"algo":"rgrpow01","ver":"0.1.0_dev"}')"
else
  stats='{"hs":[0],"hs_units":"khs","temp":[],"fan":[],"uptime":0,"ar":[0,0],"algo":"rgrpow01","ver":"0.1.0_dev"}'
fi
