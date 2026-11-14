#!/usr/bin/env bash
(
    set -euo pipefail
    base="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    source "$base/h-manifest.conf"
    cd "$base"
    [[ -f SHA256SUMS ]] || { echo "Archive incomplete: SHA256SUMS absent" >&2; exit 1; }
    sha256sum --quiet -c SHA256SUMS
    mkdir -p "$(dirname "$CUSTOM_LOG_BASENAME")"
    export PYTHONUNBUFFERED=1 CUDA_DEVICE_ORDER=PCI_BUS_ID
    # HiveOS owns this foreground process and its children. No screen or systemd.
    python3 -u "$base/gnr.py" run "$CUSTOM_CONFIG_FILENAME" 2>&1 | tee -a "${CUSTOM_LOG_BASENAME}.log"
)
