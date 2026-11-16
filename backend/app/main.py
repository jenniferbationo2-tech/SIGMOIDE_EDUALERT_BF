"""API EduAlert BF : le 'serveur' entre la carte (frontend) et les donnees (SQLite).

Lancer, depuis backend/ :   uvicorn app.main:app --reload
Documentation interactive :  http://localhost:8000/docs
"""
import json
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import GEOJSON_REGIONS, ORIGINES_FRONTEND
from .db import lignes
from .fiche_pdf import generer_fiche

app = FastAPI(
    title="EduAlert BF",
    description="Cartographie et anticipation du risque de decrochage scolaire par region (Defi 1).",
    version="0.1.0",
)

# CORS : autorise le site Vue (autre adresse/port) a appeler cette API depuis le navigateur.
app.add_middleware(CORSMiddleware, allow_origins=ORIGINES_FRONTEND, allow_methods=["GET"], allow_headers=["*"])


def region_existe(code: str) -> str:
    code = code.upper()
    if not lignes("SELECT 1 FROM regions WHERE region_code = ?", (code,)):
        raise HTTPException(404, f"Region inconnue : {code}. Voir GET /regions")
    return code


@app.get("/", tags=["General"])
def accueil():
    return {"message": "Bienvenue sur EduAlert BF", "documentation": "/docs"}


@app.get("/equipe", tags=["General"])
def equipe():
    return {"equipe": [
        {"membre": 1, "role": "Data et Backend"},
        {"membre": 2, "role": "Data science, analyse et Frontend"},
    ]}


@app.get("/sante", tags=["General"])
def sante():
    """Etat du service et origine des donnees chargees (reel ou FICTIF)."""
    meta = {r["cle"]: r["valeur"] for r in lignes("SELECT cle, valeur FROM meta")}
    return {"statut": "ok", **meta}


@app.get("/regions", tags=["Referentiel"])
def liste_regions():
    """Les 13 regions (decoupage des donnees DGESS 2016-2025)."""
    return lignes("SELECT region_code, region_nom FROM regions ORDER BY region_nom")


@app.get("/annees", tags=["Referentiel"])
def liste_annees():
    """Annees disponibles (annee de fin d'annee scolaire : 2024/25 -> 2025)."""
    return [r["annee"] for r in lignes("SELECT DISTINCT annee FROM risque ORDER BY annee")]


@app.get("/geo/regions", tags=["Carte"])
def contours_regions():
    """Contours des 13 regions au format GeoJSON, a donner directement a Leaflet."""
    return json.loads(GEOJSON_REGIONS.read_text(encoding="utf-8"))


@app.get("/indicateurs", tags=["Donnees"])
def indicateurs(
    annee: int | None = None,
    region: str | None = None,
    indicateur: str | None = None,
    sexe: Literal["G", "F", "T"] | None = None,
):
    """Indicateurs filtres. Tous les filtres sont optionnels et se combinent."""
    sql = "SELECT * FROM indicateurs WHERE 1=1"
    params: list = []
    for colonne, valeur in [("annee", annee), ("region_code", region and region.upper()),
                            ("indicateur", indicateur), ("sexe", sexe)]:
        if valeur is not None:
            sql += f" AND {colonne} = ?"
            params.append(valeur)
    return lignes(sql + " ORDER BY region_code, annee, indicateur, sexe", tuple(params))


@app.get("/risque", tags=["Carte"])
def risque(annee: int = Query(..., description="Ex. 2025, ou 2026 pour la prevision")):
    """Score et niveau de risque de chaque region pour une annee : sert a colorer la carte."""
    res = lignes("""SELECT r.region_code, g.region_nom, r.annee, r.score, r.niveau,
                           r.facteurs, r.est_prevision
                    FROM risque r JOIN regions g USING(region_code)
                    WHERE r.annee = ? ORDER BY r.score DESC""", (annee,))
    if not res:
        raise HTTPException(404, f"Pas de score de risque pour {annee}. Voir GET /annees")
    return res


RECOMMANDATIONS = {
    "Critique": ["Renforcer les cantines scolaires et kits scolaires",
                 "Suivi rapproché des écoles fermées ou délocalisées (zones à fort déplacement)",
                 "Déployer des enseignants et dispositifs d'éducation en situation d'urgence"],
    "Modere": ["Campagnes de sensibilisation des parents (scolarisation des filles)",
               "Suivi trimestriel des effectifs par la DPEPS"],
    "Faible": ["Maintenir le suivi annuel des indicateurs"],
}


@app.get("/regions/{code}/fiche", tags=["Carte"])
def fiche_region(code: str):
    """Fiche d'une region : historique du risque, indicateurs recents, recommandations."""
    code = region_existe(code)
    nom = lignes("SELECT region_nom FROM regions WHERE region_code = ?", (code,))[0]["region_nom"]
    historique = lignes("SELECT annee, score, niveau, facteurs, est_prevision FROM risque "
                        "WHERE region_code = ? ORDER BY annee", (code,))
    derniere = max((h["annee"] for h in historique if not h["est_prevision"]), default=None)
    recents = lignes("SELECT indicateur, sexe, valeur FROM indicateurs "
                     "WHERE region_code = ? AND annee = ? ORDER BY indicateur, sexe", (code, derniere))
    actuel = historique[-1] if historique else None
    return {
        "region_code": code,
        "region_nom": nom,
        "risque_actuel": actuel,
        "historique_risque": historique,
        "annee_indicateurs": derniere,
        "indicateurs": recents,
        "recommandations": RECOMMANDATIONS.get(actuel["niveau"], []) if actuel else [],
    }


@app.get("/regions/{code}/fiche.pdf", tags=["Carte"], response_class=Response,
         responses={200: {"content": {"application/pdf": {}}}})
def fiche_region_pdf(code: str):
    """Fiche d'une page a telecharger pour le directeur regional (meme contenu que /fiche)."""
    fiche = fiche_region(code)
    source = lignes("SELECT valeur FROM meta WHERE cle = 'source_risque'")
    pdf = generer_fiche(fiche, source[0]["valeur"] if source else "FICTIF")
    nom = f"EduAlertBF_fiche_{fiche['region_code']}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nom}"'})
