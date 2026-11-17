"""Chemins et reglages centralises : un seul endroit a modifier si un fichier change de place."""
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]          # dossier EDUALERTBF/
DOSSIER_DONNEES = RACINE / "data" / "03_transformation"
DOSSIER_ANALYSE = RACINE / "data" / "04_analyse"
DOSSIER_EXEMPLE = Path(__file__).resolve().parents[1] / "donnees_exemple"

BASE_SQLITE = Path(__file__).resolve().parents[1] / "edualert.sqlite"
GEOJSON_REGIONS = DOSSIER_DONNEES / "regions13.geojson"

# Application web (Membre 2) : servie en fichiers statiques sur /app par main.py.
DOSSIER_FRONTEND = RACINE / "frontend"

# Sorties du modele exposees par GET /modele (Membre 2).
FICHIER_METRIQUES = "metriques_modeles.csv"
FICHIER_INCERTITUDE = "prevision_2026_incertitude.csv"

# Fichiers attendus du Membre 2 (contrat, voir docs/Planning_EduAlertBF.md section 6).
# Tant qu'ils n'existent pas, on charge les fichiers FICTIFS de donnees_exemple/.
FICHIER_INDICATEURS = "indicateurs.csv"   # region_code, region_nom, annee, sexe, indicateur, valeur
FICHIER_RISQUE = "risque.csv"             # region_code, annee, score, niveau, facteurs, est_prevision

# Adresses autorisees a appeler l'API depuis un navigateur (serveur de dev Vue / Vite).
ORIGINES_FRONTEND = ["http://localhost:5173", "http://127.0.0.1:5173"]
