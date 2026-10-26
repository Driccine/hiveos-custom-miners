# Mineurs — un dossier par coin

Chaque dossier à la racine contient **tous les fichiers de son coin** : code, installation Hive OS, tests et documentation.

| Coin | Dossier | Statut |
| --- | --- | --- |
| RigorChain / ORU | [ORU/](ORU/) | Code PoW indépendant de référence en développement ; pas encore de mineur GPU Hive OS complet |
| Quantus / QTC | [QTC/](QTC/) | Wrapper Hive OS expérimental ; binaire `quantus-miner` non inclus |

## Structure

```text
.
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
