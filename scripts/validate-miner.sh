#!/usr/bin/env bash
set -euo pipefail
MINER="${1:-}"
[[ -n "${MINER}" ]] || { echo "Usage: $0 <nom-du-miner>"; exit 1; }
DIR="miners/${MINER}"
for file in h-manifest.conf h-config.sh h-run.sh h-stats.sh version README.md; do
  [[ -f "${DIR}/${file}" ]] || { echo "Fichier manquant : ${DIR}/${file}"; exit 1; }
done
for file in h-config.sh h-run.sh h-stats.sh; do bash -n "${DIR}/${file}"; done
[[ -f "${DIR}/${MINER}-miner" ]] || echo "Attention : binaire absent : ${DIR}/${MINER}-miner"
echo "Validation réussie pour ${MINER}."
