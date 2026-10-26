#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
command -v nvcc >/dev/null || { echo "CUDA nvcc compiler not found; install CUDA Toolkit first" >&2; exit 1; }
python3 -m unittest discover -s ORU/tests -v
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/oru-native"
nvcc -O3 -std=c++17 \
  -gencode arch=compute_75,code=sm_75 \
  -gencode arch=compute_86,code=sm_86 \
  -gencode arch=compute_89,code=sm_89 \
  -gencode arch=compute_120,code=sm_120 \
  -gencode arch=compute_120,code=compute_120 \
  ORU/src/cuda/oru_cuda.cu -o "$STAGE/oru-native/oru-cuda"
cp ORU/src/solo.py ORU/src/rgrpow.py ORU/hiveos/benchmark.py "$STAGE/oru-native/"
cp ORU/hiveos/h-manifest.conf ORU/hiveos/h-config.sh ORU/hiveos/h-run.sh ORU/hiveos/h-stats.sh "$STAGE/oru-native/"
chmod +x "$STAGE/oru-native/oru-cuda" "$STAGE/oru-native/"*.sh
OUT="$ROOT/ORU/oru-native-0.1.0_dev.tar.gz"
tar -C "$STAGE" -czf "$OUT" oru-native
sha256sum "$OUT"
echo "Hive OS archive created: $OUT"
