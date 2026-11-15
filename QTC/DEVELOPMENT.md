# QTC / Quantus — développement du mineur indépendant

**Statut : spécifications identifiées, pas encore de moteur propriétaire opérationnel.**

## Attention : ce QTC est Quantus

C'est le coin Quantus Network (`Quantus-Network/chain`), et **pas** les projets tiers utilisant eux aussi le ticker QTC.

Sources techniques à respecter :
- [QPoW, documentation Quantus](https://docs.quantus.com/deep-dives/qpow/) : preuve de travail basée sur Poseidon2 et le corps de champ Goldilocks.
- [Protocole externe du mineur](https://docs.quantus.com/deep-dives/miner-protocol/) : communication de tâches via QUIC, avec authentification et vérification du certificat TLS sur les versions récentes.
- [Code du nœud Quantus](https://github.com/Quantus-Network/chain) : référence de consensus pour les vecteurs de tests.
- [Guide officiel de minage](https://docs.quantus.com/guides/mining/) : paramètres réseau mainnet.

## Cahier de construction d'une version originale

1. Extraire des **vecteurs QPoW** vérifiables du consensus, sans reprendre un exécutable de mineur tiers.
2. Implémenter Poseidon2/Goldilocks en C++/CUDA et comparer les digest GPU aux vecteurs indépendants.
3. Implémenter un client QUIC authentifié compatible avec la version actuelle du protocole Quantus.
4. Ajouter multi-GPU, tests sur RTX 20/30/50 et récupération automatique des nouveaux jobs.
5. Tester la réception et l'acceptation de résultats ; empaqueter le tout dans `QTC/hiveos/`.

Le wrapper Hive OS expérimental actuel ne contient pas de mineur GPU QPoW compilé. Il ne doit pas être annoncé comme une version utilisable.

**Aucun mineur payant ni commission externe à introduire.** Les règles de consensus publiques restent la source de compatibilité.
