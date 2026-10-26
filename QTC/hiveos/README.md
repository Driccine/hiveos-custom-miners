# Quantus Hive OS (développement)

Ce dossier regroupe la configuration Hive OS existante. Le binaire `quantus-miner` **n'est pas inclus**.

Les scripts `h-config.sh`, `h-run.sh`, `h-stats.sh` et `h-manifest.conf` proviennent de l'intégration Quantus antérieure. Ils restent expérimentaux et nécessitent des tests.

Voir [Flight Sheet](flight-sheet.md).

Pour préparer l'archive depuis la racine du dépôt :
```bash
bash QTC/tools/validate-miner.sh
bash QTC/tools/package-miner.sh
```
