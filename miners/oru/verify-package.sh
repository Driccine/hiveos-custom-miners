#!/usr/bin/env bash
# Vérifie le paquet Hive OS ORU d'Aria Energy sans l'exécuter.
set -euo pipefail

URL="https://dl.ariabrain.com/rgr-dl/aria-energy-rgr-1.1.0.tar.gz"
EXPECTED_SHA256="ca32ce6f7f4898401664fca74c99510f187d8aec9e297bca0ff467a0f4e43342"

if ! command -v sha256sum >/dev/null 2>&1; then
  echo "Erreur : sha256sum est requis." >&2
  exit 1
fi

if [[ "$#" -gt 1 ]]; then
  echo "Utilisation : $0 [chemin/vers/paquet.tar.gz]" >&2
  exit 2
fi

if [[ "$#" -eq 1 ]]; then
  ARCHIVE="$1"
  [[ -f "$ARCHIVE" ]] || { echo "Fichier introuvable : $ARCHIVE" >&2; exit 1; }
else
  command -v curl >/dev/null 2>&1 || { echo "Erreur : curl est requis." >&2; exit 1; }
  ARCHIVE="./aria-energy-rgr-1.1.0.tar.gz"
  echo "Téléchargement du paquet tiers : $URL"
  curl --fail --location --show-error --silent --retry 2 --output "$ARCHIVE" "$URL"
fi

echo "Contrôle SHA-256 du paquet..."
ACTUAL_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then
  echo "ERREUR : SHA-256 différent. N'installez pas ce paquet." >&2
  echo "Attendu : $EXPECTED_SHA256" >&2
  echo "Obtenu  : $ACTUAL_SHA256" >&2
  exit 1
fi
echo "SHA-256 confirmé : $ACTUAL_SHA256"
echo "Archive vérifiée : $ARCHIVE"
echo "Aucun binaire n'a été exécuté."
