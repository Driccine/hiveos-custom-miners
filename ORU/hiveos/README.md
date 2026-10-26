# ORU — Installation Hive OS (alpha / pas encore validée sur GPU)

**Ce paquet est construit entièrement à partir du code présent dans ce dépôt.** Il n'utilise aucun mineur commercial ou payant.

## Préparation

Une machine Linux avec CUDA Toolkit NVIDIA (`nvcc`) doit compiler la version et générer une archive :

```bash
python3 -m unittest discover -s ORU/tests -v
bash ORU/hiveos/build-package.sh
```

La commande génère `ORU/oru-native-0.1.1_dev.tar.gz`, archive contenant le dossier `oru-native/` requis par Hive OS.

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


## Mesurer et comparer le hashrate ORU

Après installation de la version compilée sur un rig NVIDIA :

```bash
cd /hive/miners/custom/oru-native
python3 benchmark.py --devices 0,1,2 --nonces 8388608 --samples 3 --csv oru-bench.csv
```

Sur chaque GPU, lire la moyenne médiane en MH/s, puis comparer à la mesure
**du même algorithme ORU**, sur **le même rig**, avec un autre mineur (même pilote,
overclocking et limite de puissance). Exemple pour une référence mesurée à 50 MH/s :

```bash
python3 benchmark.py --devices 0,1,2 --baseline-name "Autre miner ORU" --baseline-hs 50000000
```

Le benchmark fait des recherches avec une cible nulle qui ne rapporte pas de monnaie.
Il compte la préparation CUDA et les copies mémoire. Les hashrates de coins différents
ne sont pas comparables directement.

Attention : ce paquet **n'a pas été exécuté sur GPU** dans l'environnement GitHub Actions ;
une compilation réussie ne prouve pas l'absence d'erreurs à l'exécution.

## Correction des chemins (0.1.1_dev)

La configuration `oru.env` est maintenant créée dans le **même dossier que les scripts `h-config.sh`/`h-run.sh`**, indépendamment de `MINER_DIR`. Cette version corrige l'erreur `oru.env: No such file or directory` du paquet 0.1.0_dev. L'installation reste une alpha SOLO qui nécessite ton propre nœud RIGOR et ne fonctionne pas avec une URL de pool Stratum.
