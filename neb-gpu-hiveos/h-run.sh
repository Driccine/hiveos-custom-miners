#!/usr/bin/env bash
set -Eeuo pipefail
# HiveOS bootstrap for Aria Energy NEB. The proprietary CUDA miner is NOT included.
VERSION=3.2.0
URL="https://dl.ariabrain.com/neb-dl/aria-energy-neb-${VERSION}.tar.gz"
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$BASE/.aria-${VERSION}"
log() { echo "[neb-gpu-hiveos] $*" >&2; }
command -v curl >/dev/null || { log 'curl is required'; exit 1; }
command -v tar >/dev/null || { log 'tar is required'; exit 1; }
if [[ ! -f "$VENDOR/.ready" ]]; then
  log "Downloading the official Aria Energy NEB ${VERSION} HiveOS package"
  TMP="$(mktemp -d "$BASE/.download.XXXXXXXX")"
  trap 'rm -rf "$TMP"' EXIT
  curl -fL --retry 3 --connect-timeout 15 -o "$TMP/miner.tar.gz" "$URL"
  tar -tzf "$TMP/miner.tar.gz" >/dev/null
  mkdir -p "$TMP/extract"
  tar -xzf "$TMP/miner.tar.gz" -C "$TMP/extract" --no-same-owner
  LAUNCHER="$(find "$TMP/extract" -maxdepth 3 -type f -name h-run.sh -print -quit)"
  if [[ -z "$LAUNCHER" ]]; then log 'Official package has no h-run.sh; refusing to guess arguments'; exit 1; fi
  REL="${LAUNCHER#"$TMP/extract"/}"
  printf '%s\n' "$REL" > "$TMP/extract/.launcher"
  touch "$TMP/extract/.ready"
  rm -rf "$VENDOR"
  mv "$TMP/extract" "$VENDOR"
  log 'Official package cached'
fi
REL="$(cat "$VENDOR/.launcher")"
LAUNCHER="$VENDOR/$REL"
[[ -f "$LAUNCHER" ]] || { log 'Missing official h-run.sh'; exit 1; }
cd "$(dirname "$LAUNCHER")"
exec bash "$LAUNCHER"
