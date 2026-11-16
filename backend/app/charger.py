"""Charge les CSV (contrat avec le Membre 2) dans la base SQLite.

Usage, depuis backend/ :   python -m app.charger
A relancer a chaque fois que le Membre 2 livre une nouvelle version des CSV.
"""
import pandas as pd

from .config import (DOSSIER_ANALYSE, DOSSIER_DONNEES, DOSSIER_EXEMPLE,
                     FICHIER_INDICATEURS, FICHIER_RISQUE, BASE_SQLITE)
from .db import SCHEMA, connexion

COLONNES_INDICATEURS = ["region_code", "region_nom", "annee", "sexe", "indicateur", "valeur"]
COLONNES_RISQUE = ["region_code", "annee", "score", "niveau", "facteurs", "est_prevision"]


def trouver(nom: str, dossier_reel) -> tuple:
    """Prend le vrai fichier s'il existe, sinon l'exemple fictif."""
    reel = dossier_reel / nom
    if reel.exists():
        return reel, "reel"
    return DOSSIER_EXEMPLE / nom, "FICTIF"


def verifier(df: pd.DataFrame, colonnes: list[str], nom: str) -> None:
    manquantes = set(colonnes) - set(df.columns)
    if manquantes:
        raise SystemExit(f"{nom} : colonnes manquantes {sorted(manquantes)} (attendu : {colonnes})")


def main() -> None:
    f_ind, src_ind = trouver(FICHIER_INDICATEURS, DOSSIER_DONNEES)
    f_risq, src_risq = trouver(FICHIER_RISQUE, DOSSIER_ANALYSE)

    ind = pd.read_csv(f_ind)
    verifier(ind, COLONNES_INDICATEURS, f_ind.name)
    risq = pd.read_csv(f_risq)
    verifier(risq, COLONNES_RISQUE, f_risq.name)

    regions = ind[["region_code", "region_nom"]].drop_duplicates("region_code")

    BASE_SQLITE.unlink(missing_ok=True)       # on repart de zero : chargement reproductible
    with connexion() as con:
        con.executescript(SCHEMA)
        regions.to_sql("regions", con, if_exists="append", index=False)
        ind[COLONNES_INDICATEURS[:1] + COLONNES_INDICATEURS[2:]].to_sql(
            "indicateurs", con, if_exists="append", index=False)
        risq[COLONNES_RISQUE].to_sql("risque", con, if_exists="append", index=False)
        con.executemany("INSERT INTO meta VALUES (?, ?)",
                        [("source_indicateurs", src_ind), ("source_risque", src_risq)])

    print(f"Indicateurs : {len(ind)} lignes ({src_ind}) depuis {f_ind}")
    print(f"Risque      : {len(risq)} lignes ({src_risq}) depuis {f_risq}")
    print(f"Regions     : {len(regions)}  ->  {BASE_SQLITE.name}")


if __name__ == "__main__":
    main()
