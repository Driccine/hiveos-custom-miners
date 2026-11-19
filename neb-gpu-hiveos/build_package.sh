#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-$BASE/neb-gpu-hiveos-1.0.0.tar.gz}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/neb-gpu-hiveos"
cp "$BASE/h-run.sh" "$TMP/neb-gpu-hiveos/h-run.sh"
chmod +x "$TMP/neb-gpu-hiveos/h-run.sh"
tar -czf "$OUT" -C "$TMP" neb-gpu-hiveos
printf 'Package created: %s\n' "$OUT"
