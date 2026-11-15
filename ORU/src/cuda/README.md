# Moteur CUDA ORU

Fichier : `oru_cuda.cu`.

Cette implémentation originale réalise une recherche de nonce NVIDIA pour la preuve de travail RIGOR : `SHA3-256("RGRPOW01" + header80)`. Chaque thread GPU traite un nonce.

Compilation conseillée depuis la racine :

```bash
nvcc -O3 -std=c++17 -gencode arch=compute_75,code=sm_75 -gencode arch=compute_75,code=compute_75 ORU/src/cuda/oru_cuda.cu -o ORU/oru-cuda
```

L'exécutable prend `--header` (160 chiffres hex), `--target` (64 chiffres hex représentant la cible numérique en big-endian), `--start`, `--count`, `--device` et optionnellement `--batch`.

Il renvoie `FOUND <nonce> <attempts>` ou `NONE <attempts>`. Le coordinateur `src/solo.py` recalcule systématiquement les hash gagnants sur CPU avant soumission.

**Limites :** pas de compilation CUDA réussie observée dans cet environnement, aucun benchmark réel, optimisation Keccak non aboutie. Pas de support AMD/Stratum pour cette première version.

Source sous licence MIT (voir `ORU/LICENSE`).
