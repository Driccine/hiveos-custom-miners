# Développement des mineurs — suivi par coin

Objectif : implémentations originales, optimisées pour GPU NVIDIA sur Hive OS, **sans binaire commercial ni frais de développeur**.

| Coin | Dossier | Moteur de calcul | Réseau / Hive OS |
| --- | --- | --- | --- |
| ORU (RigorChain) | [ORU](ORU/) | CUDA RGRPOW01 alpha écrit, **pas testé sur GPU** | SOLO JSON-RPC + scripts Hive OS alpha, sans release |
| QTC (Quantus) | [QTC](QTC/) | Pas encore de CUDA natif QPoW | Wrapper hérité, intégration QUIC requise |
| PRL (Pearl) | Pas encore créé | Spécification et vecteurs de validation à vérifier | À développer |
| NUMN (Numen) | Pas encore créé | Proof of Scan à documenter et implémenter | À développer |
| NULL | Pas encore créé | Spécification vérifiable nécessaire | À développer |
| VELA | Pas encore créé | Spécification vérifiable nécessaire | À développer |
| CMFD | Pas encore créé | Spécification vérifiable nécessaire | À développer |

**Politique :** on crée le dossier propre à un coin lorsque son premier code ou cahier technique vérifié est prêt. Aucun dossier vide servant uniquement de vitrine.

## Validation minimale avant version Hive OS installable

- Calcul du protocole exact, comparé aux vecteurs officiels ;
- compilation sur le GPU visé, tests de nonces réels et comparaison CPU/GPU ;
- connexion à un nœud ou pool autorisé, jobs renouvelés correctement ;
- acceptation mesurée des résultats, statistiques honnêtes, résilience réseau ;
- archive Hive OS valide avec une URL de release qui existe.

Un code qui passe des tests unitaires n'est pas encore une preuve de compatibilité mainnet ou de rentabilité.
