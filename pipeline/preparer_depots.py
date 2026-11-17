"""Prepare les fichiers a deposer sur equation.africadataentry.com, deja nommes selon le reglement :
    EQUIPE_ETAPE_DEFI_ROLE_description_vN.ext   (sans espace ni accent)

Usage (racine du projet) :  backend/.venv/Scripts/python pipeline/preparer_depots.py [--version 2]
Resultat : dossier depots/ (non versionne), un sous-dossier par categorie de la plateforme.
"""
import argparse
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
EQUIPE = "AB7C-938F-79BB"
DEFI = "D1"

# (categorie plateforme, etape, role, description, source, extension finale)
# Un livrable par etape du parcours de donnees du challenge : la plateforme
# doit pouvoir refaire le chemin du fichier brut jusqu'a la carte.
DEPOTS = [
    # --- 01 collecte ---
    ("Donnees", "01-collecte", "engineer", "dgess-prescolaire-primaire-2016-2025-brut",
     "data/00_sources/DGESS_prescolaire_primaire_2016_2025.xlsx", ".xlsx"),
    ("Donnees", "01-collecte", "architect", "inventaire-sources",
     "data/01_collecte/inventaire_sources.csv", ".csv"),

    # --- 02 nettoyage ---
    ("Donnees", "02-nettoyage", "engineer", "dgess-regional-nettoye-format-long",
     "data/02_nettoyage/dgess_regional_long.csv", ".csv"),
    ("Donnees", "02-nettoyage", "engineer", "dgess-national-nettoye-format-long",
     "data/02_nettoyage/dgess_national_long.csv", ".csv"),
    ("Donnees", "02-nettoyage", "engineer", "controles-coherence-totaux",
     "data/02_nettoyage/controles_coherence.csv", ".csv"),
    ("Documentation", "02-nettoyage", "engineer", "journal-nettoyage",
     "data/02_nettoyage/journal_nettoyage.md", ".md"),

    # --- 03 transformation ---
    ("Donnees", "03-transformation", "engineer", "indicateurs-format-long",
     "data/03_transformation/indicateurs.csv", ".csv"),
    ("Donnees", "03-transformation", "engineer", "survie-cohortes-national",
     "data/03_transformation/survie_cohortes_national.csv", ".csv"),
    ("Donnees", "03-transformation", "architect", "contours-13-regions-geojson",
     "data/03_transformation/regions13.geojson", ".json"),
    ("Donnees", "03-transformation", "architect", "correspondance-regions-17-13",
     "data/03_transformation/correspondance_regions_17_13.csv", ".csv"),
    ("Documentation", "03-transformation", "architect", "schema-dictionnaire-donnees",
     "docs/dictionnaire_donnees.md", ".md"),

    # --- 04 analyse ---
    ("Donnees", "04-analyse", "analyst", "score-risque-13-regions-2017-2026",
     "data/04_analyse/risque.csv", ".csv"),
    ("Donnees", "04-analyse", "analyst", "prevision-2026-incertitude",
     "data/04_analyse/prevision_2026_incertitude.csv", ".csv"),
    ("Donnees", "04-analyse", "analyst", "metriques-validation-modeles",
     "data/04_analyse/metriques_modeles.csv", ".csv"),
    ("Donnees", "04-analyse", "analyst", "importance-variables",
     "data/04_analyse/importance_variables.csv", ".csv"),
    ("Donnees", "04-analyse", "analyst", "sensibilite-poids-indice",
     "data/04_analyse/sensibilite_poids.csv", ".csv"),
    ("Documentation", "04-analyse", "analyst", "rapport-modele-risque",
     "data/04_analyse/rapport_modele.md", ".md"),

    # --- 05 interpretation ---
    ("Documentation", "05-interpretation", "architect", "documentation-solution",
     "docs/documentation_EduAlertBF.md", ".md"),
    ("Documentation", "05-interpretation", "architect", "planning-equipe",
     "docs/Planning_EduAlertBF.md", ".md"),
]

# Les fiches PDF, les figures et les captures partent en un seul zip de
# livrables : les deposer un a un saturerait la plateforme sans servir la
# lecture.
LIVRABLES = ["data/05_interpretation/fiches", "data/05_interpretation/graphiques",
             "data/05_interpretation/captures"]
# Code : un seul zip (backend + pipeline + scripts de lancement)
# Tout ce qu'il faut pour relancer l'application complete sur un poste vierge :
# source DGESS (le pipeline se rejoue), indicateurs, scores de risque et interface web.
CODE = ["backend/app", "backend/donnees_exemple", "backend/requirements.txt",
        "data/00_sources", "data/03_transformation", "data/04_analyse", "frontend",
        "pipeline", "run.bat", "run.sh", "README.md"]
EXCLURE = {"__pycache__", ".venv", "edualert.sqlite"}


def nom(etape: str, role: str, desc: str, version: int, ext: str) -> str:
    return f"{EQUIPE}_{etape}_{DEFI}_{role}_{desc}_v{version}{ext}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, default=1)
    v = ap.parse_args().version

    sortie = RACINE / "depots"
    shutil.rmtree(sortie, ignore_errors=True)
    lisez_moi = [f"LISEZ-MOI - Depots equipe {EQUIPE} - Defi 1 (EduAlert BF) - {date.today():%d/%m/%Y}", ""]
    absents: list[str] = []

    for categorie, etape, role, desc, src, ext in DEPOTS:
        source = RACINE / src
        if not source.exists():
            absents.append(src)
            print(f"  ABSENT : {src}")
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

    # --- Livrables produits : fiches PDF, figures, captures ---
    livrables_zip = sortie / "Documentation" / nom(
        "05-interpretation", "architect", "fiches-figures-captures", v, ".zip")
    livrables_zip.parent.mkdir(parents=True, exist_ok=True)
    compte = 0
    with zipfile.ZipFile(livrables_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for element in LIVRABLES:
            dossier = RACINE / element
            if not dossier.exists():
                absents.append(element)
                print(f"  ABSENT : {element}")
                continue
            for f in sorted(dossier.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(RACINE))
                    compte += 1
    lisez_moi.append(f"[Documentation] {livrables_zip.name}\n"
                     f"    {compte} fichiers : 13 fiches PDF, figures et captures d'ecran")

    texte = "\n".join(lisez_moi) + "\n"
    for categorie in ("Donnees", "Code", "Documentation"):
        (sortie / categorie).mkdir(parents=True, exist_ok=True)
        (sortie / categorie / nom("00-lisez-moi", "architect", f"lisez-moi-{categorie.lower()}", v, ".txt")
         ).write_text(texte, encoding="utf-8")

    print(texte)
    print(f"-> {sortie}")

    # Un depot incomplet ne doit pas passer pour un depot reussi : la
    # plateforme n'a aucun moyen de signaler le fichier qui manque.
    if absents:
        print(f"\nECHEC : {len(absents)} source(s) absente(s), le depot est incomplet :")
        for src in absents:
            print(f"  - {src}")
        return 1
    print(f"\n{len(DEPOTS)} fichiers deposes + 2 archives. Depot complet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
