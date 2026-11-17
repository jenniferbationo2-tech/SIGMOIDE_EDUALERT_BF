#!/usr/bin/env bash
# Assemble le bundle de deploiement Vercel dans deploiement/vercel/.build/.
#
# Le depot n'est pas deploye tel quel : Vercel n'a besoin que du code de
# l'API, de la base SQLite, des trois fichiers de donnees lus a l'execution
# et du front. Le bundle est donc reconstruit a chaque envoi, jamais edite.
#
# Usage : bash deploiement/vercel/preparer.sh
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(cd "$ICI/../.." && pwd)"
SORTIE="$ICI/.build"

echo "== Nettoyage =="
rm -rf "$SORTIE"
mkdir -p "$SORTIE/backend" "$SORTIE/data/03_transformation" "$SORTIE/data/04_analyse"

echo "== Code de l'API =="
cp -r "$RACINE/backend/app" "$SORTIE/backend/app"
find "$SORTIE" -name "__pycache__" -type d -prune -exec rm -rf {} +

echo "== Base SQLite =="
if [ ! -f "$RACINE/backend/edualert.sqlite" ]; then
  echo "   absente du depot (fichier ignore par git) : reconstruction"
  ( cd "$RACINE/backend" && .venv/bin/python -m app.charger )
fi
cp "$RACINE/backend/edualert.sqlite" "$SORTIE/backend/edualert.sqlite"

echo "== Donnees lues a l'execution =="
cp "$RACINE/data/03_transformation/regions13.geojson" "$SORTIE/data/03_transformation/"
cp "$RACINE/data/04_analyse/metriques_modeles.csv" \
   "$RACINE/data/04_analyse/prevision_2026_incertitude.csv" "$SORTIE/data/04_analyse/"

echo "== Front (fichiers statiques servis sur /app) =="
cp -r "$RACINE/frontend" "$SORTIE/frontend"

echo "== Configuration Vercel =="
cp "$ICI/index.py" "$ICI/vercel.json" "$ICI/requirements.txt" "$SORTIE/"

echo "== Bundle pret : $(du -sh "$SORTIE" | cut -f1) =="
