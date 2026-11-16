"""Prepare les fichiers a deposer sur equation.africadataentry.com, deja nommes selon le reglement :
    EQUIPE_ETAPE_DEFI_ROLE_description_vN.ext   (sans espace ni accent)

Usage (racine du projet) :  backend/.venv/Scripts/python pipeline/preparer_depots.py [--version 2]
Resultat : dossier depots/ (non versionne), un sous-dossier par categorie de la plateforme.
"""
import argparse
import shutil
import zipfile
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
EQUIPE = "AB7C-938F-79BB"
DEFI = "D1"

# (categorie plateforme, etape, role, description, source, extension finale)
DEPOTS = [
    ("Donnees", "01-collecte", "engineer", "dgess-prescolaire-primaire-2016-2025-brut",
     "data/00_sources/DGESS_prescolaire_primaire_2016_2025.xlsx", ".xlsx"),
    ("Donnees", "01-collecte", "architect", "inventaire-sources",
     "data/01_collecte/inventaire_sources.csv", ".csv"),
    ("Donnees", "03-transformation", "architect", "contours-13-regions-geojson",
     "data/03_transformation/regions13.geojson", ".json"),
    ("Donnees", "03-transformation", "architect", "correspondance-regions-17-13",
     "data/03_transformation/correspondance_regions_17_13.csv", ".csv"),
    ("Documentation", "03-transformation", "architect", "schema-dictionnaire-donnees",
     "docs/dictionnaire_donnees.md", ".md"),
]
# Code : un seul zip (backend + pipeline + scripts de lancement)
CODE = ["backend/app", "backend/donnees_exemple", "backend/requirements.txt", "data/03_transformation",
        "pipeline", "run.bat", "run.sh", "README.md"]
EXCLURE = {"__pycache__", ".venv", "edualert.sqlite"}


def nom(etape: str, role: str, desc: str, version: int, ext: str) -> str:
    return f"{EQUIPE}_{etape}_{DEFI}_{role}_{desc}_v{version}{ext}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    v = ap.parse_args().version

    sortie = RACINE / "depots"
    shutil.rmtree(sortie, ignore_errors=True)
    lisez_moi = [f"LISEZ-MOI - Depots equipe {EQUIPE} - Defi 1 (EduAlert BF) - {date.today():%d/%m/%Y}", ""]

    for categorie, etape, role, desc, src, ext in DEPOTS:
        source = RACINE / src
        if not source.exists():
            print(f"  ABSENT (ignore) : {src}")
            continue
        cible = sortie / categorie / nom(etape, role, desc, v, ext)
        cible.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, cible)
        lisez_moi.append(f"[{categorie}] {cible.name}\n    origine : {src}")

    zip_nom = sortie / "Code" / nom("05-interpretation", "architect", "code-api-backend-pipeline", v, ".zip")
    zip_nom.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_nom, "w", zipfile.ZIP_DEFLATED) as z:
        for element in CODE:
            chemin = RACINE / element
            fichiers = [chemin] if chemin.is_file() else chemin.rglob("*")
            for f in fichiers:
                if f.is_file() and not EXCLURE & set(f.relative_to(RACINE).parts):
                    z.write(f, f.relative_to(RACINE))
    lisez_moi.append(f"[Code] {zip_nom.name}\n    API FastAPI, scripts pipeline, lancement : run.bat (Windows) ou run.sh")

    texte = "\n".join(lisez_moi) + "\n"
    for categorie in ("Donnees", "Code", "Documentation"):
        (sortie / categorie).mkdir(parents=True, exist_ok=True)
        (sortie / categorie / nom("00-lisez-moi", "architect", f"lisez-moi-{categorie.lower()}", v, ".txt")
         ).write_text(texte, encoding="utf-8")

    print(texte)
    print(f"-> {sortie}")


if __name__ == "__main__":
    main()
