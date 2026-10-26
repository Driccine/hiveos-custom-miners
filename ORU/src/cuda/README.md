# ORU CUDA kernel — our own SHA3-256 RGRPOW01 implementation

The CUDA source in this directory is written for this repository and performs a GPU nonce search.

Build with CUDA Toolkit 12.8+ (recommended for GeForce RTX 50) and an NVIDIA driver compatible with your GPU:

\`\`\`bash
nvcc -O3 -std=c++17 \
  -gencode arch=compute_75,code=sm_75 \
  -gencode arch=compute_75,code=compute_75 \
  ORU/src/cuda/oru_cuda.cu -o ORU/oru-cuda
\`\`\`

The executable accepts:
\`\`\`text
--header 160_HEX_CHARS --target 64_HEX_BIG_ENDIAN --start 0 --count 1048576 --device 0
\`\`\`
and prints \`FOUND nonce attempts\` or \`NONE attempts\`. Host \`solo.py\` **recalculates** a claimed winning hash before submission.

**Development limitations**
- No successful compilation or GPU run has been verified yet: this environment has no NVIDIA GPU or nvcc.
- Current kernel runs all 24 Keccak rounds independently for every nonce. It has **not** been tuned/benchmarked against existing miners.
- Supports CUDA, not AMD GPUs.
- Pool Stratum is not yet implemented. The first integration targets the documented RIGOR node SOLO workflow.
- Performance and stability on mixed NVIDIA rigs must be verified on actual Hive OS equipment.

The source is distributed under MIT (see \`ORU/LICENSE\`).
