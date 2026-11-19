# Mesurer les performances NEB sur les rigs NVIDIA

| Matériel | Premier essai | Comparaison |
| --- | --- | --- |
| RingGPU02 · RTX 3070 Ti | Aria Energy NEB 3.2.0 · PPLNS Europe, port 3370 | Suprminer 1.9.45 · Suprnova, port 7804 |
| RingGPU04 · RTX 3060 / autres rigs 3060 Ti | Aria Energy NEB 3.2.0 · PPLNS Europe | Suprminer 1.9.45 avec le même protocole |
| RingGPU01 · RTX 2080 Ti | Suprminer 1.9.45 sur une carte avant extension au rig | Vérifier la détection CUDA et les shares acceptées. Le support Turing dans Aria 3.2.0 reste à établir. |
| RTX 5090 Laptop · Windows | Suprminer Windows, `suprminer-neptune.exe -a neb --neb-test` | Comparer à puissance mesurée identique sur le laptop. Les chiffres desktop ne prédisent pas le résultat mobile. |

Le package Aria direct évite les étapes du bootstrap, qui lance le même binaire. L’archive `neb-gpu-hiveos-1.0.0.tar.gz` inspectée contient seulement `h-run.sh`. Elle ne fournit pas les fichiers de configuration et statistiques HiveOS. Utiliser les packages des éditeurs pour la comparaison. Les guides HiveOS NEB des deux mineurs indiquent un pilote NVIDIA 580 ou supérieur.

## Protocole sur un rig

1. Partir des fréquences d’origine et mesurer le temps de connexion TCP aux pools. Utiliser un worker par essai pour retrouver les chiffres côté pool.
2. Comparer les mineurs sur les mêmes cartes, avec des fréquences et une limite de puissance identiques. Après les premières shares acceptées, mesurer deux heures par essai. Prolonger à 24 h si l’écart est faible ou si les statistiques du pool sont instables.
3. Relever le hashrate effectif ou le travail accepté par unité de temps, les shares stale et invalides, et les watts moyens. Les pools peuvent attribuer des difficultés différentes aux shares. Calculer l’efficacité en MH/s acceptés par watt. Pour extrapoler à toute la ferme, mesurer aussi la consommation à la prise.
4. Sur le mineur retenu, réduire la limite de puissance de 10 % à chaque essai, mémoire d’origine. Garder le meilleur compromis stable. Ajuster ensuite la fréquence mémoire seule si elle améliore le travail accepté par watt.
5. Pour comparer le rendement des pools, relever les NEB nets crédités sur une durée suffisante, en tenant compte de la maturité des blocs et de la fenêtre PPLNS. Les frais développeur annoncés sont de 1 % chez Aria et de 0 % pour Suprminer sur NEB. Les frais de pool s’ajoutent.

## Piste pour un moteur CUDA indépendant

Suprminer documente le calcul des contributions par échantillon une fois par modèle, leur réutilisation pour chaque nonce et un kernel warp qui évite une étape en mémoire partagée. Sur le mainnet 1.0.1, Kepler et TESS utilisent tous deux KEP1. Le benchmark de développement doit donc couvrir les deux datasets et les changements de modèle. Vérifier les tickets bit à bit et les shares contre la référence CPU avant de comparer les débits.

- [AriaPool et benchmarks](https://pool.ariabrain.com/neb.html)
- [Suprminer et notes CUDA](https://github.com/ocminer/suprminer)
- [Guide NEB Suprnova, HiveOS et Windows](https://neb.suprnova.cc/StartMining.html)
- [Spécification du mainnet NEB](https://github.com/SilasEigen/neb/blob/v1.0.1/docs/mainnet.md)
