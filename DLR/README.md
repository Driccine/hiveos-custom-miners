# DLR-CC 1.0.0

Custom Miner HiveOS x86-64 pour Daler (DLR), chaîne Ting. Il démarre le moteur
CUDA NVIDIA Crypto Connection Miner 0.10.1 sur le port GPU
`stratum+tcp://crypto-connection.net:4073`. Le moteur ne prélève pas de frais
développeur. Les frais de la pool sont distincts.

## Prérequis

- NVIDIA avec un pilote compatible avec le binaire CUDA 12 et vos cartes.
- glibc 2.34 minimum. Vérifier avec `getconf GNU_LIBC_VERSION`.
- Bash, Python 3.6+, curl, sha256sum et tar.
- Connexion HTTPS à GitHub au premier lancement. Le paquet télécharge le binaire
  officiel, contrôle le SHA-256 fixé à la version, puis le réutilise au redémarrage.
- Compte **public** Ting de 64 caractères hexadécimaux. Utiliser Ting ID ou
  `ting wallet create` du projet Ting. Garder les clés privées dans le wallet.

## Installation sur un rig

Copier `dlr-cc-1.0.0.tar.gz` sur le rig. Depuis son dossier de téléchargement :

```bash
sudo tar --no-same-owner -xzf dlr-cc-1.0.0.tar.gz -C /hive/miners/custom
sudo chown -R user /hive/miners/custom/dlr-cc
```

Dans HiveOS, créer la Flight Sheet suivante.

| Champ | Valeur |
| --- | --- |
| Coin | DLR (coin personnalisé si nécessaire) |
| Wallet | Compte public Ting |
| Pool | Configure in miner |
| Miner | Custom |
| Miner name | dlr-cc |
| Installation URL | Vide si le paquet a été extrait localement |
| Hash algorithm | ting si disponible |
| Wallet and worker template | `%WAL%.%WORKER_NAME%` |
| Pool URL | `stratum+tcp://crypto-connection.net:4073` |
| Pass | `x` |
| Extra config arguments | Vide |

Le port et le mot de passe sont déjà fixés dans le lanceur. Si l'interface
demande une URL d'installation, héberger l'archive sans changer son nom sur
un serveur HTTP(S) que le rig peut joindre et coller son URL directe.

Les noms de workers acceptent de 1 à 32 caractères parmi les lettres ASCII,
chiffres, tiret et underscore. En cas de problème de substitution de HiveOS,
renseigner directement `COMPTE_TING.RingGPU04` dans le champ Wallet and worker template.

## Validation sur RingGPU04

Tester d'abord sur les trois RTX 3060. Le port TCP se vérifie avec
`timeout 5 bash -c '</dev/tcp/crypto-connection.net/4073'`.
Un code de retour 0 indique que la connexion TCP s'ouvre. Ouvrir ensuite le journal
avec `miner` et attendre une hausse du compteur de shares acceptées. Vérifier
le worker dans « My stats » sur Crypto Connection avec le même compte Ting.
Le taux par carte s'affiche après le premier rapport du moteur, à environ 15 s.

Moteur amont et code source :
https://github.com/gacanga/crypto-connection-miner/tree/v0.10.1

Wallet du projet Ting :
https://github.com/ting-organization/ting-id
