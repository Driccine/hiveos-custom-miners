# QTC — Quantus

Tous les fichiers dédiés à Quantus sont dans ce dossier.

- `hiveos/` : wrapper Hive OS existant, documentation et paramètres.
- `tools/` : validation et empaquetage du seul mineur QTC.

**Statut : développement.** Le binaire `quantus-miner` n'est pas inclus.

Avant de générer l'archive, compiler le véritable moteur `quantus-miner` puis le placer dans `QTC/hiveos/quantus-miner`.

Depuis la racine du dépôt :
```bash
bash QTC/tools/validate-miner.sh
bash QTC/tools/package-miner.sh
```
