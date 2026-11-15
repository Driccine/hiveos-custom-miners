# Mineurs GPU indépendants pour Hive OS

**Un dossier par coin**, contenant le moteur de calcul, le protocole, les tests et sa configuration Hive OS.

| Coin | Code | État |
| --- | --- | --- |
| RigorChain / ORU | [ORU](ORU/) | Noyau CUDA original + coordinateur SOLO + scripts Hive OS, **alpha à compiler et tester** |
| Quantus / QTC | [QTC](QTC/) | Wrapper Hive OS historique ; moteur de calcul indépendant encore à développer |

## Principes du dépôt

1. Pas de mineur commercial tiers redistribué ; pas de frais de développeur intégrés à nos mineurs.
2. Code propre à chaque coin : les blockchains utilisent des preuves de travail et des protocoles différents.
3. Un coin se construit, se teste et s'empaquette dans son propre dossier.
4. Une version n'est dite **stable** que lorsque sa compilation et le fonctionnement de son réseau ont été démontrés sur un rig réel.

Le développement ORU est initialement sur une branche de travail afin de ne pas confondre **prototype** et **version Hive OS opérationnelle**.

## Ordre d'intégration envisagé

Après ORU : QTC (Quantus / QPoW Poseidon2 et protocole QUIC), puis les autres coins suivis (Pearl, Numen, NULL, VELA, CMFD), chacun après vérification de ses spécifications publiques.

Le code de référence d'un protocole peut être utilisé pour vérifier la compatibilité et les vecteurs de test, sans utiliser les binaires d'un mineur payant.
