#!/usr/bin/env bash
set -euo pipefail
# Exécuter depuis n'importe quel répertoire.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIR="${ROOT}/QTC/hiveos"
for file in h-manifest.conf h-config.sh h-run.sh h-stats.sh version README.md; do
  [[ -f "${DIR}/${file}" ]] || { echo "Fichier manquant : ${DIR}/${file}" >&2; exit 1; }
done
for file in h-config.sh h-run.sh h-stats.sh; do
  bash -n "${DIR}/${file}"
done
[[ -f "${DIR}/quantus-miner" ]] || echo "Attention : binaire Quantus absent (version développement)."
echo "Vérification des scripts QTC réussie."
