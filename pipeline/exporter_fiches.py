"""Exporte les 13 fiches PDF (une par region) dans data/05_interpretation/fiches/.

Le script reutilise l'API elle-meme : il importe les fonctions de
`backend/app` (meme code que `GET /regions/{code}/fiche.pdf`, donc exactement
le PDF que telecharge un directeur regional) sans avoir besoin de lancer un
serveur.

Lancer depuis la racine du depot, apres `python -m app.charger` :

    python pipeline/exporter_fiches.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
BACKEND = RACINE / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.db import lignes  # noqa: E402
from app.fiche_pdf import generer_fiche  # noqa: E402
from app.main import fiche_region  # noqa: E402

DOSSIER_SORTIE = RACINE / "data" / "05_interpretation" / "fiches"


def main() -> int:
    if not (BACKEND / "edualert.sqlite").exists():
        print("Base absente. Lancer d'abord : cd backend && python -m app.charger")
        return 1

    source = lignes("SELECT valeur FROM meta WHERE cle = 'source_risque'")
    origine = source[0]["valeur"] if source else "FICTIF"
    if origine != "reel":
        print("ATTENTION : les donnees chargees sont FICTIVES, les fiches le diront.")

    regions = lignes("SELECT region_code FROM regions ORDER BY region_code")
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)

    for region in regions:
        code = region["region_code"]
        fiche = fiche_region(code)
        pdf = generer_fiche(fiche, origine)
        fichier = DOSSIER_SORTIE / f"EduAlertBF_fiche_{code}.pdf"
        fichier.write_bytes(pdf)
        niveau = fiche["risque_actuel"]["niveau"] if fiche["risque_actuel"] else "?"
        print(f"{code:<16} {niveau:<9} {len(pdf):>6} octets  -> {fichier.name}")

    print(f"\n{len(regions)} fiches ecrites dans {DOSSIER_SORTIE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
