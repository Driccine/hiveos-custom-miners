# Catalogue de mineurs Hive OS

Chaque mineur ou coin possède son propre dossier sous `miners/`.

| Coin | Dossier | Statut |
| --- | --- | --- |
| Quantus / QTC | [quantus/](quantus/) | Wrapper Hive OS expérimental ; binaire absent |
| RigorChain / ORU | [oru/](oru/) | Référence du paquet officiel de l'opérateur Aria Energy, avec vérification SHA-256 |

## Convention pour les futures intégrations

- `README.md` : origine du logiciel, installation, limites et prérequis.
- `miner.json` : métadonnées de l'intégration, quand une distribution tierce est utilisée.
- `h-manifest.conf`, `h-config.sh`, `h-run.sh`, `h-stats.sh` : uniquement pour les wrappers développés et effectivement empaquetés dans ce dépôt.
- `flight-sheets/<coin>.md` : configuration Hive OS associée.

Ne pas présenter une simple intégration ou documentation comme un mineur compilé et testé.
