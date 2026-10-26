# HiveOS Custom Miners

Dépôt centralisé pour organiser les mineurs, leurs configurations et les Flight Sheets Hive OS.

## Catalogue des mineurs

| Coin | Dossier | Statut | Installation |
| --- | --- | --- | --- |
| Quantus (QTC) | [miners/quantus](miners/quantus/) | Développement : binaire non inclus | Compilation et empaquetage nécessaires |
| RigorChain (ORU) | [miners/oru](miners/oru/) | Intégration d'un paquet Hive OS tiers | [Flight Sheet ORU](flight-sheets/oru.md) |

## Arborescence

- `miners/` : un sous-dossier par coin/mineur.
- `flight-sheets/` : paramètres Hive OS documentés, coin par coin.
- `scripts/` : outils communs de validation et d'empaquetage.

## Important

Un dossier dans le catalogue n'implique **pas** que le dépôt fournisse un binaire minable.
La version Quantus attend son binaire `quantus-miner`.
Pour ORU, nous référençons le **paquet Hive OS d'Aria Energy RGR 1.1.0**, distribué par son éditeur et à vérifier avec le SHA-256 fourni dans `miners/oru/` avant installation. Nous ne redistribuons pas ce binaire.

Les intégrations et les optimisations GPU doivent être testées sur un rig réel avant de déclarer une version stable.
