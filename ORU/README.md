# ORU — Mineur original NVIDIA (branche de développement)

Notre projet ORU repose sur du code créé pour ce dépôt, et non sur le binaire d'un mineur tiers commercial.

## Fonctionnement

- Protocole RGRPOW01 : `SHA3-256("RGRPOW01" || header_80)`.
- `src/cuda/oru_cuda.cu` : scanner de nonces sur GPU NVIDIA en CUDA (prototype).
- `src/solo.py` : récupération du `getblocktemplate` de notre nœud, contrôle du paiement coinbase, recherche GPU multi-cartes, vérification CPU, puis `submitblock`.
- `src/rgrpow.py` : calcul SHA3 indépendant de référence et test CPU.
- `tests/` : vecteurs PoW et contrôles de sérialisation SOLO.
- `hiveos/` : scripts Custom Miner et génération du paquet Hive OS.

## Compiler et tester

```bash
python3 -m unittest discover -s ORU/tests -v
bash ORU/hiveos/build-package.sh
```

La compilation GPU nécessite `nvcc` (CUDA Toolkit NVIDIA). Pour la série RTX 50, prévoir une chaîne d'outils et des pilotes supportant ces GPU.

Le paquet généré localement est `ORU/oru-native-0.1.0_dev.tar.gz`. Il ne sera prêt à publier en Release que lorsque nous aurons validé la compilation, les vecteurs sur CUDA, le dialogue avec un vrai nœud RIGOR et l'acceptation d'un bloc. Les performances ne sont pas encore mesurées.

## Mode SOLO et confidentialité

Ce premier moteur fonctionne avec **ton propre nœud RIGOR**, pas un pool Stratum. Le nœud doit être synchronisé et utiliser le RPC JSON (mainnet, généralement `127.0.0.1:8761`). Pas de clés privées dans le miner, seulement une adresse ORU `rg1q...`.

Ne rends **jamais** l'interface RPC accessible à Internet. Utilise l'accès local ou un tunnel sécurisé si ton rig Hive OS est sur un autre hôte.

Instructions de Flight Sheet : [hiveos/README.md](hiveos/README.md).

## Licence et limites

- Source originale sous [licence MIT](LICENSE).
- Aucune commission de développeur ni binaire payant intégrés.
- Nous utilisons les règles de consensus publiées par le projet RIGOR comme spécification d'interopérabilité.
- **État : alpha non testée sur GPU ni nœud mainnet.** Aucun hashrate réel ou récompense n'est garanti.

Spécification : [RIGOR PoW](https://github.com/rigorchain/rigorchain/blob/main/core/src/rigor_kernel/pow_digest.cpp).
