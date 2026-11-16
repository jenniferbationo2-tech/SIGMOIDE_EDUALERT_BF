#!/usr/bin/env sh
# EduAlert BF - lancement en une commande (Linux / macOS / Git Bash)
set -e
cd "$(dirname "$0")/backend"
PY=python3; command -v $PY >/dev/null || PY=python
[ -d .venv ] || $PY -m venv .venv
VPY=.venv/bin/python; [ -x $VPY ] || VPY=.venv/Scripts/python
$VPY -m pip install -q -r requirements.txt
[ -d ../DataPack_DCB_2026 ] && $VPY ../pipeline/geo_regions.py
$VPY -m app.charger
echo "API : http://localhost:8000/docs"
$VPY -m uvicorn app.main:app --port 8000
