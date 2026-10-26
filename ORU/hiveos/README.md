# ORU — Installation Hive OS (alpha / pas encore validée sur GPU)

**Ce paquet est construit entièrement à partir du code présent dans ce dépôt.** Il n'utilise aucun mineur commercial ou payant.

## Préparation

Une machine Linux avec CUDA Toolkit NVIDIA (`nvcc`) doit compiler la version et générer une archive :

```bash
python3 -m unittest discover -s ORU/tests -v
bash ORU/hiveos/build-package.sh
```

La commande génère `ORU/oru-native-0.1.0_dev.tar.gz`, archive contenant le dossier `oru-native/` requis par Hive OS.

Dans Hive OS, renseigner le Custom Miner après hébergement de l'archive à une URL HTTPS stable, par exemple un asset GitHub Release **créé après validation**.

## Flight Sheet prévue

| Paramètre Hive OS | Valeur |
| --- | --- |
| Mineur | Custom / `oru-native` |
| Wallet and worker | Adresse ORU `rg1q...`, **sans suffixe worker** |
| Pool URL | **URL JSON-RPC de ton nœud**, par exemple `http://127.0.0.1:8761` |
| Extra config | `{"rpc_user":"identifiant","rpc_password":"mot-de-passe","devices":"0,1"}` |
| Installation URL | URL de la future archive compilée et publiée par ce dépôt |

Le mot de passe RPC est nécessaire au nœud ; ne partage jamais cette Flight Sheet si elle contient ces identifiants. Vérifie que le rig peut joindre l'interface RPC par réseau privé ou tunnel : le RPC ne doit pas être ouvert sur Internet.

## Compatibilité

Mode **SOLO RIGOR uniquement** : `getblocktemplate` → calcul GPU RGRPOW01 → `submitblock`.

**Un pool Stratum ne fonctionnera pas** comme RPC SOLO. Un client Stratum indépendant nécessitera une intégration de protocole supplémentaire.

## Statut actuel

Le code source, les tests et l'outil de génération de paquet sont présents. Cette version n'a pas été compilée avec nvcc ici et n'a pas été testée sur une carte NVIDIA ou un nœud mainnet. Ne pas la déclarer stable ni diffuser d'URL d'installation qui n'existe pas.
