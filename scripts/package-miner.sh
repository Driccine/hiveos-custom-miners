#!/usr/bin/env bash
set -euo pipefail
MINER="${1:-}"
[[ -n "${MINER}" ]] || { echo "Usage: $0 <nom-du-miner>"; exit 1; }
DIR="miners/${MINER}"
VERSION="$(tr -d '[:space:]' < "${DIR}/version")"
OUT="${MINER}-hiveos-v${VERSION}.tar.gz"
"${PWD}/scripts/validate-miner.sh" "${MINER}"
[[ -x "${DIR}/${MINER}-miner" ]] || { echo "Binaire absent ou non exécutable : ${DIR}/${MINER}-miner"; exit 1; }
tar -C "${DIR}" -czf "${OUT}" "${MINER}-miner" h-manifest.conf h-config.sh h-run.sh h-stats.sh version README.md
echo "Paquet créé : ${OUT}"
