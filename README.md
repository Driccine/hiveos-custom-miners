# HiveOS Custom Miners

Dépôt dédié aux Custom Miners utilisables dans les Flight Sheets HiveOS.

## Mineurs disponibles

- Quantus GPU — version de développement

## Structure

- `miners/quantus/` : wrapper HiveOS du mineur Quantus
- `flight-sheets/quantus.md` : configuration à saisir dans HiveOS
- `scripts/` : validation et création du paquet `.tar.gz`

## Important

Le binaire `quantus-miner` n'est pas inclus dans ce dépôt initial.
Il doit être compilé puis copié dans `miners/quantus/quantus-miner`
avant de créer le paquet HiveOS.
