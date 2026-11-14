#!/usr/bin/env bash
khs=0
stats=null
_gnr_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$_gnr_dir/h-manifest.conf"
mapfile -t _gnr_values < <(python3 "$_gnr_dir/gnr.py" stats "${CUSTOM_CONFIG_FILENAME%/*}/stats.json" 2>/dev/null)
khs="${_gnr_values[0]:-0}"
stats="${_gnr_values[1]:-null}"
unset _gnr_dir _gnr_values
