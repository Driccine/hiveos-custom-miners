# RigorChain ORU — Intégration Hive OS

**Statut : intégration documentée d'un mineur tiers, et non développement d'un nouvel algorithme GPU.**

- Blockchain : RigorChain
- Monnaie minée : ORU
- Algorithme : OpuHash (SHA3, domaine `RGRPOW01`)
- Adresse de paiement mainnet : `rg1q...` (une adresse `rg1p...` n'est pas une adresse ORU)
- Matériel : GPU NVIDIA (séries GTX 16 à RTX 50 d'après l'éditeur)
- Pilote NVIDIA : **580 ou plus récent**, selon l'éditeur du paquet

## Paquet Hive OS existant

Distributeur : **Aria Energy RGR 1.1.0** sur [AriaPool](https://pool.ariabrain.com/rgr.html).

- URL d'installation Hive OS :
  `https://dl.ariabrain.com/rgr-dl/aria-energy-rgr-1.1.0.tar.gz`
- SHA-256 publié pour le paquet Hive OS :
  `ca32ce6f7f4898401664fca74c99510f187d8aec9e297bca0ff467a0f4e43342`
- Commission de développement indiquée par l'éditeur : 2 % du temps de minage.
- Pool indiqué : `rgr.ariabrain.com:3356` ; PPLNS, commission annoncée 2 %.

**Sécurité :** vérifiez le checksum avant de déployer cette archive. Le script `verify-package.sh` permet de le faire sur un fichier local déjà téléchargé, ou de télécharger le paquet puis de vérifier son SHA-256. Il ne lance jamais le mineur.

## Utilisation

Consultez [la Flight Sheet ORU](../../flight-sheets/oru.md). Dans Hive OS, sélectionnez le **mineur Custom** et utilisez directement l'URL du paquet ci-dessus.

## Limites et suite

- Aucun binaire ORU n'est hébergé ou recompilé ici.
- Le dépôt ne revendique pas de gains de performances ou de compatibilité testée avec vos rigs.
- Les scripts `h-*.sh` du paquet tiers restent gérés par son distributeur ; nous ne les dupliquons pas sans inspection du paquet et tests.
- Une version ORU maison pourra être ajoutée ultérieurement dans un sous-dossier/version dédié, après validation de sa chaîne de compilation et de ses performances.
