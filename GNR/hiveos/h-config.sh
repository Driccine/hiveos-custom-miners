#!/usr/bin/env bash
_gnr_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$_gnr_dir/h-manifest.conf"
GNR_WALLET="${CUSTOM_TEMPLATE:-}" \
GNR_NODE="${CUSTOM_URL:-https://genoryn.io}" \
GNR_EXTRA="${CUSTOM_USER_CONFIG:-}" \
python3 "$_gnr_dir/gnr.py" configure "$CUSTOM_CONFIG_FILENAME" || { return 1 2>/dev/null || exit 1; }
unset _gnr_dir
