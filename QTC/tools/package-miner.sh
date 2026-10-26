#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIR="${ROOT}/QTC/hiveos"
VERSION="$(tr -d '[:space:]' < "${DIR}/version")"
"${ROOT}/QTC/tools/validate-miner.sh"
[[ -x "${DIR}/quantus-miner" ]] || { echo "Binaire absent/non exécutable : ${DIR}/quantus-miner" >&2; exit 1; }
OUT="${ROOT}/QTC/quantus-hiveos-v${VERSION}.tar.gz"
tar -C "${DIR}" -czf "${OUT}" quantus-miner h-manifest.conf h-config.sh h-run.sh h-stats.sh version README.md
echo "Archive QTC créée : ${OUT}"
