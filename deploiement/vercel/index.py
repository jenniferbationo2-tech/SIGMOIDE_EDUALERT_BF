"""Point d'entree Vercel : sert l'application FastAPI de backend/app.

Vercel detecte ce fichier (FastAPI) et lui remet TOUTES les URL : les routes
de l'API comme le front monte sur /app. Les fichiers necessaires a l'execution
sont embarques par `includeFiles` dans vercel.json ; les chemins relatifs de
backend/app/config.py pointent donc sur les bons dossiers.

Le bundle est assemble par `preparer.sh` dans .build/ — ne pas deployer ce
dossier source directement, il ne contient pas les donnees.
"""
import mimetypes
import sys
from pathlib import Path

# Starlette deduit le type MIME des fichiers statiques : sans cette ligne, la
# police Inter part en application/octet-stream (certains navigateurs refusent).
mimetypes.add_type("font/woff2", ".woff2")

RACINE = Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE / "backend"))

from app.main import app  # noqa: E402,F401
