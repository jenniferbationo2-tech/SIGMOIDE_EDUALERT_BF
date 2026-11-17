"""Enchaine les etapes 02 a 04 du pipeline de donnees (Membre 2).

Usage :
    python pipeline/executer_pipeline.py

Equivalent a lancer, dans cet ordre :
    python pipeline/nettoyer_dgess.py
    python pipeline/calculer_indicateurs.py
    python pipeline/modele_risque.py

Le chargement dans la base (backend : python -m app.charger) se fait ensuite,
il est appele par run.bat / run.sh.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "data" / "00_sources" / "DGESS_prescolaire_primaire_2016_2025.xlsx"

ETAPES = [
    ("02 nettoyage", "nettoyer_dgess.py"),
    ("03 indicateurs", "calculer_indicateurs.py"),
    ("04 risque et prevision", "modele_risque.py"),
]


def main() -> int:
    if not SOURCE.exists():
        print(f"Fichier source absent : {SOURCE}")
        print("Le pipeline ne peut pas etre rejoue ; les CSV deja presents "
              "dans data/ sont conserves.")
        return 1

    for numero, (libelle, script) in enumerate(ETAPES, start=1):
        chemin = Path(__file__).resolve().parent / script
        print(f"\n=== [{numero}/{len(ETAPES)}] {libelle} ({script}) ===")
        resultat = subprocess.run([sys.executable, str(chemin)], cwd=RACINE)
        if resultat.returncode != 0:
            print(f"\nEchec de l'etape « {libelle} » (code "
                  f"{resultat.returncode}). Pipeline interrompu.")
            return resultat.returncode

    print("\n=== Pipeline termine ===")
    print("Sorties : data/02_nettoyage/, data/03_transformation/, data/04_analyse/")
    print("Etape suivante : cd backend && python -m app.charger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
