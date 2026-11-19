# NEB mainnet 1.0.1 sur HiveOS

## NVIDIA sur AriaPool

| Champ HiveOS | Valeur |
| --- | --- |
| Miner | Custom |
| Miner name | `aria-energy-neb` |
| Installation URL | `https://dl.ariabrain.com/neb-dl/aria-energy-neb-3.2.0.tar.gz` |
| Hash algorithm | `nebhash` |
| Wallet and worker template | `%WAL%` avec le wallet public `neb1…` |
| Pool URL | `neb.ariabrain.com:3370` (PPLNS) ou `neb.ariabrain.com:3371` (solo sur pool) |
| Pass / Extra config | Laisser vides pour le premier essai |

Aria Energy 3.2.0 demande un pilote NVIDIA 580 ou supérieur. Vérifier la version sur chaque rig avec `nvidia-smi`. Aria documente Energy 3.1 pour les RTX 30 et 40 et Energy 3.2 pour les RTX 50. La documentation consultée ne confirme pas les RTX 2080 Ti pour cette version. Le binaire Aria conserve les frais développeur annoncés de 1 %.

Aria mesure 61,1 / 76,0 MH/s sur RTX 3080 Ti à 400 W et 266,2 / 298,9 MH/s sur RTX 5090 desktop à 575 W, respectivement sur Kepler et TESS. Pour comparer deux mineurs, relever le travail accepté côté pool et la puissance, avec les mêmes limites, fréquences et GPU. Ces essais restent à faire sur les rigs.

## Téléchargement vérifié

```bash
bash download-hiveos.sh aria .
bash download-hiveos.sh solo .
```

Le script télécharge l'archive d'origine, vérifie le SHA-256 et place l'archive validée dans le dossier demandé. Il utilise le manifeste de l'éditeur pour Aria et une empreinte épinglée de la release officielle pour le mode solo. Le script ne lance aucun mineur.

## Mineur officiel open source, solo via un nœud local

Le package officiel `nebminer` inclut le mineur CUDA, les scripts HiveOS, le nœud et le dataset mainnet. Il accepte les GPU NVIDIA compute capability 7.5 et plus, dont les RTX 2080 Ti, avec un pilote 580+ et une image HiveOS basée sur Ubuntu 22.04. Dans la flight sheet, renseigner le wallet NEB et laisser le champ Pool URL vide pour utiliser les relais configurés par défaut. L'option `--devices 0,1` permet de sélectionner des GPU.

Le mainnet 1.0.1 utilise KEP1 sur les deux datasets. Les options `--gpu-kernel k1` et `k2` concernent l'ancien réseau de neurones du testnet. Le code CUDA officiel vérifie ses résultats contre la référence CPU. Les optimisations internes Energy 3.1 et 3.2 ne sont pas décrites dans les sources Aria consultées. Ce dossier fournit l'intégration et le téléchargement des binaires existants.

- [Documentation et benchmarks AriaPool](https://pool.ariabrain.com/neb.html)
- [NEB 1.0.1 et package HiveOS officiel](https://github.com/SilasEigen/neb/releases/tag/v1.0.1)
- [Code source des moteurs NEB](https://github.com/SilasEigen/neb/blob/v1.0.1/docs/mining.md)
