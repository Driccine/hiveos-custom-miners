# Mineurs — un dossier par coin

Chaque dossier à la racine contient **tous les fichiers de son coin** : code, installation Hive OS, tests et documentation.

| Coin | Dossier | Statut |
| --- | --- | --- |
| RigorChain / ORU | [ORU/](ORU/) | Code PoW indépendant de référence en développement ; pas encore de mineur GPU Hive OS complet |
| Quantus / QTC | [QTC/](QTC/) | Wrapper Hive OS expérimental ; binaire `quantus-miner` non inclus |
| Daler / DLR | [DLR/](DLR/) | Custom Miner NVIDIA pour Crypto Connection, test des shares sur rig à confirmer · [Archive HiveOS](https://raw.githubusercontent.com/Driccine/hiveos-custom-miners/680bdcc7a50db6c8e3bb80152ec8790b5fb6f3ce/DLR/dlr-cc-1.0.0.tar.gz) |

## Structure

```text
.
├── DLR/
│   ├── README.md
│   ├── dlr-cc-1.0.0.tar.gz
│   └── hiveos/
├── ORU/
│   ├── README.md
│   ├── src/
│   ├── tests/
│   └── hiveos/
├── QTC/
│   ├── README.md
│   ├── hiveos/
│   └── tools/
└── README.md
```

**Règle :** un nouveau coin = un nouveau dossier à la racine ; aucun mélange de ses fichiers dans les autres dossiers.

Ce dépôt ne redistribue aucun mineur commercial tiers. Les modules en développement ne sont pas annoncés comme prêts à miner.
