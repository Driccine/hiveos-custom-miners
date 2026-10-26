# Flight Sheet Hive OS — RigorChain ORU

Intégration du mineur tiers **Aria Energy RGR 1.1.0** (paquet Hive OS).

| Champ Hive OS | Valeur |
| --- | --- |
| Coin | ORU / RigorChain |
| Miner | **Custom** |
| Installation URL | `https://dl.ariabrain.com/rgr-dl/aria-energy-rgr-1.1.0.tar.gz` |
| Wallet and worker | Votre **adresse ORU `rg1q...`**, sans remplacer par un nom de rig |
| Pool URL | `rgr.ariabrain.com:3356` |
| Mot de passe Stratum | `x` si demandé par l'interface |
| Extra config | Vide pour le premier essai |

L'éditeur du paquet indique que son processus pilote tous les GPU du rig et que son pilote NVIDIA minimal est la version **580**.

**Avant installation :** contrôlez que le SHA-256 du paquet correspond à
`ca32ce6f7f4898401664fca74c99510f187d8aec9e297bca0ff467a0f4e43342`.
Script : [verify-package.sh](../miners/oru/verify-package.sh).

**Après installation :** vérifiez dans les logs le démarrage, la connexion au pool et les shares acceptées. Ces étapes n'ont pas encore été testées sur vos rigs.

Documentation : [AriaPool ORU](https://pool.ariabrain.com/rgr.html) et [intégration du dépôt](../miners/oru/README.md).
