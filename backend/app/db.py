"""Acces a la base SQLite (le 'magasin' du restaurant)."""
import sqlite3

from .config import BASE_SQLITE

SCHEMA = """
CREATE TABLE IF NOT EXISTS regions (
    region_code TEXT PRIMARY KEY,
    region_nom  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS indicateurs (
    region_code TEXT NOT NULL REFERENCES regions(region_code),
    annee       INTEGER NOT NULL,          -- annee de fin d'annee scolaire : 2024/25 -> 2025
    sexe        TEXT NOT NULL,             -- G, F ou T (total)
    indicateur  TEXT NOT NULL,             -- ex. taux_achevement, effectif_primaire
    valeur      REAL,
    PRIMARY KEY (region_code, annee, sexe, indicateur)
);
CREATE TABLE IF NOT EXISTS risque (
    region_code  TEXT NOT NULL REFERENCES regions(region_code),
    annee        INTEGER NOT NULL,
    score        REAL NOT NULL,            -- 0 (aucun risque) a 100 (risque maximal)
    niveau       TEXT NOT NULL,            -- Faible, Modere, Critique
    facteurs     TEXT,                     -- principaux facteurs, separes par ';'
    est_prevision INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (region_code, annee)
);
CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT);
"""


def connexion() -> sqlite3.Connection:
    con = sqlite3.connect(BASE_SQLITE)
    con.row_factory = sqlite3.Row   # chaque ligne se lit comme un dictionnaire : ligne["annee"]
    return con


def lignes(sql: str, params: tuple = ()) -> list[dict]:
    """Execute une requete SELECT et renvoie une liste de dictionnaires (pret pour le JSON)."""
    with connexion() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
