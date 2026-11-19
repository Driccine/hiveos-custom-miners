# NEB sur Suprnova · HiveOS NVIDIA

Dans les [assets de Suprminer 1.9.47](https://github.com/ocminer/suprminer/releases/tag/v1.9.47), copier l’URL du package NVIDIA HiveOS Ubuntu 22.04, suffixe `_u2204.tar.gz`. Vérifier sur le rig la version du pilote avec `nvidia-smi` (pilote 580 minimum selon le guide Suprnova).

| Champ | Valeur |
| --- | --- |
| Coin | NEB |
| Pool | Configure in miner |
| Miner | Custom |
| Miner name | `suprminer-neptune` |
| Hash algorithm | `neb` |
| Wallet and worker | `%WAL%.%WORKER_NAME%` |
| Pool URL | `stratum+tcp://neb.suprnova.cc:7804` |
| Password | `x` |
| Extra config | Vide |

Suprnova indique 1 % de frais PPLNS. Suprminer annonce 0 % de frais mineur sur NEB. Le dataset mainnet 1.0.1 est récupéré au premier lancement. [Guide officiel Suprnova](https://neb.suprnova.cc/StartMining.html).
