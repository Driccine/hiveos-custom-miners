# ORU — RigorChain

## Développement de notre propre mineur

Ce dossier est **réservé au développement original du mineur ORU**, sans redistribution ni dépendance au binaire Aria Energy.

L'algorithme de consensus officiel est **RGRPOW01** :
```
SHA3-256(b"RGRPOW01" + header_80)
```
- `header_80` : en-tête de bloc canonique de 80 octets ;
- nonce : quatre octets finaux de l'en-tête, little-endian ;
- digest de 32 octets comparé au target comme entier little-endian ;
- voie SOLO officielle : `getblocktemplate` / `submitblock` via un nœud RIGOR local.

Sources techniques du protocole : [poW officiel](https://github.com/rigorchain/rigorchain/blob/main/core/src/rigor_kernel/pow_digest.cpp) et [README du mineur de référence](https://github.com/rigorchain/rigorchain/blob/main/miner/README_MINER.md). Ces liens servent **à vérifier les règles de consensus**, pas à intégrer leur binaire.

## Ce qui existe maintenant

- `src/rgrpow.py` : **notre** implémentation simple du calcul PoW et de la recherche CPU de nonces, avec la bibliothèque standard Python ;
- `tests/test_pow.py` : vecteurs de vérification et tests ;
- `hiveos/README.md` : état de l'intégration Hive OS.

Exécuter les tests :
```bash
python3 -m unittest discover -s ORU/tests -v
```

Exécuter une recherche CPU de développement (header et cible fictifs, **aucune part soumise**) :
```bash
python3 ORU/src/rgrpow.py --header $(python3 -c 'print("00"*80)') --target $(python3 -c 'print("ff"*32)') --count 1024
```

**Statut : prototype PoW, pas encore un vrai mineur GPU / pool / Hive OS.**
Prochaines étapes techniques : implémenter le noyau CUDA multi-GPU, vérifier les vecteurs GPU/CPU, ajouter le client de travail SOLO ou Stratum puis l'empaquetage et les statistiques Hive OS. Aucun gain de hashrate n'est revendiqué.
