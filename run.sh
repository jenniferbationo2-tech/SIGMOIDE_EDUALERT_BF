#!/usr/bin/env sh
# EduAlert BF - lancement en une commande (Linux / macOS / Git Bash)
set -e
cd "$(dirname "$0")/backend"
PY=python3; command -v $PY >/dev/null || PY=python
[ -d .venv ] || $PY -m venv .venv
VPY=.venv/bin/python; [ -x $VPY ] || VPY=.venv/Scripts/python
$VPY -m pip install -q -r requirements.txt
[ -d ../DataPack_DCB_2026 ] && $VPY ../pipeline/geo_regions.py
# Prepare les donnees du Membre 2 si le fichier source est present
# (nettoyage -> indicateurs -> risque). Sans lui, on garde les CSV du depot.
if [ -f ../data/00_sources/DGESS_prescolaire_primaire_2016_2025.xlsx ]; then
  $VPY ../pipeline/executer_pipeline.py || echo "Pipeline non rejoue : on garde les CSV existants."
fi
$VPY -m app.charger
echo ""
echo "Application : http://localhost:8000/app/"
echo "API (doc)   : http://localhost:8000/docs"
echo ""
$VPY -m uvicorn app.main:app --port 8000
