#!/usr/bin/env bash
# Hive sources this file.
khs=0
stats=null
dlr_stats_file="${CUSTOM_LOG_BASENAME:-/var/log/miner/dlr-cc/dlr-cc}"
if dlr_stats_json=$(python3 "$(dirname -- "${BASH_SOURCE[0]}")/stats.py" "$dlr_stats_file"); then
    if [[ -n $dlr_stats_json ]]; then
        read -r khs stats <<< "$dlr_stats_json"
    fi
fi
unset dlr_stats_json dlr_stats_file
