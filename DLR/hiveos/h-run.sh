#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
source ./h-manifest.conf

account=
if ! read -r account < "$CUSTOM_CONFIG_FILENAME" ||
   [[ ! $account =~ ^[[:xdigit:]]{64}\.[a-zA-Z0-9_-]{1,32}$ ]]; then
    echo "DLR: configuration HiveOS manquante ou compte Ting invalide." >&2
    exit 1
fi

minimum=2.34
glibc=$(getconf GNU_LIBC_VERSION)
glibc=${glibc##* }
if [[ $(printf '%s\n' "$minimum" "$glibc" | sort -V | head -n 1) != "$minimum" ]]; then
    echo "DLR: glibc $glibc détectée. Ce moteur Linux demande glibc $minimum ou plus récente." >&2
    exit 1
fi

binary=./crypto-connection-miner
if [[ ! -x $binary ]]; then
    release=CryptoConnectionMiner-v0.10.1-linux-x64-cuda12
    checksum=029811300c76988969887d6d36983fbc4b31c6f5bcf296114fa77e686c5cca74
    staging=$(mktemp -d ./.dlr-download.XXXXXX)
    trap 'rm -rf -- "$staging"' EXIT
    curl --fail --location --silent --show-error --retry 2 --connect-timeout 10 --max-time 120 \
        --output "$staging/upstream.tar.gz" \
        "https://github.com/gacanga/crypto-connection-miner/releases/download/v0.10.1/$release.tar.gz"
    printf '%s  %s\n' "$checksum" "$staging/upstream.tar.gz" | sha256sum --check
    tar -xOzf "$staging/upstream.tar.gz" "$release/crypto-connection-miner" > "$staging/miner"
    chmod 755 "$staging/miner"
    mv -f -- "$staging/miner" "$binary"
    rm -rf -- "$staging"
    trap - EXIT
fi

mkdir -p "$(dirname -- "$CUSTOM_LOG_BASENAME")"
: > "$CUSTOM_LOG_BASENAME.log"
date +%s > "$CUSTOM_LOG_BASENAME.started"
export CUDA_DEVICE_ORDER=PCI_BUS_ID
exec "$binary" --algo ting --pool crypto-connection.net:4073 \
    --user "$account" --pass x --stats 15 --log "$CUSTOM_LOG_BASENAME.log"
