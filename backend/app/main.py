"""API EduAlert BF : le 'serveur' entre la carte (frontend) et les donnees (SQLite).

Lancer, depuis backend/ :   uvicorn app.main:app --reload
Documentation interactive :  http://localhost:8000/docs
Application web :            http://localhost:8000/app/
"""
import csv
import json
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import (DOSSIER_ANALYSE, DOSSIER_FRONTEND, FICHIER_INCERTITUDE,
                     FICHIER_METRIQUES, GEOJSON_REGIONS, ORIGINES_FRONTEND)
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


@app.get("/risque/historique", tags=["Carte"])
def risque_historique():
    """Score de chaque region pour toutes les annees disponibles.

    Alimente les mini-courbes du classement : une seule requete, au lieu
    d'un appel par region.
    """
    return lignes("""SELECT r.region_code, r.annee, r.score, r.niveau, r.est_prevision
                      FROM risque r ORDER BY r.region_code, r.annee""")


RECOMMANDATIONS = {
    "Critique": ["Renforcer les cantines scolaires et kits scolaires",
                 "Suivi rapproché des écoles fermées ou délocalisées (zones à fort déplacement)",
                 "Déployer des enseignants et dispositifs d'éducation en situation d'urgence"],
    "Modere": ["Campagnes de sensibilisation des parents (scolarisation des filles)",
               "Suivi trimestriel des effectifs par la DPEPS"],
    "Faible": ["Maintenir le suivi annuel des indicateurs"],
}

# Pistes d'action associees a chaque facteur de risque (Membre 2).
# Ce sont des pistes generales, a adapter par les services deconcentres.
ACTIONS_PAR_FACTEUR = {
    "fermeture_ecoles": [
        "Réouverture ou relocalisation des écoles fermées",
        "Mise en place d'espaces temporaires d'apprentissage",
        "Dispositifs d'éducation en situation d'urgence",
    ],
    "recul_effectifs": [
        "Recensement des enfants déplacés non scolarisés",
        "Passerelles de réinsertion scolaire et cours de rattrapage",
    ],
    "ecart_admission_achevement": [
        "Suivi des cohortes du CP1 au CM2 (repérage précoce des abandons)",
        "Cantines scolaires et kits pour retenir les élèves jusqu'à la fin du cycle",
    ],
    "faible_achevement": [
        "Remédiation en lecture et en calcul",
        "Préparation renforcée au CEP",
    ],
    "faible_scolarisation": [
        "Campagnes d'inscription et sensibilisation des familles",
        "Appui à l'établissement des actes d'état civil",
        "Rapprochement de l'offre scolaire (écoles de proximité)",
    ],
    "disparite_filles_garcons": [
        "Actions ciblées sur le sexe le plus en retard dans la région",
    ],
}

LIBELLES_FACTEURS = {
    "ecart_admission_achevement": "Écart entre admission et achèvement",
    "faible_achevement": "Faible taux d'achèvement",
    "recul_effectifs": "Élèves perdus depuis le pic",
    "fermeture_ecoles": "Fermetures d'écoles",
    "faible_scolarisation": "Faible scolarisation",
    "disparite_filles_garcons": "Inégalité filles-garçons",
    "aucun_facteur_marquant": "Aucun facteur marquant",
}


def _lire_csv(chemin) -> list[dict]:
    """Lit un CSV de data/04_analyse en liste de dictionnaires."""
    with chemin.open(encoding="utf-8", newline="") as flux:
        return list(csv.DictReader(flux))


def _nombre(valeur):
    """Convertit une chaine de CSV en nombre, ou None si vide."""
    if valeur in (None, "", "-"):
        return None
    try:
        return float(valeur)
    except ValueError:
        return valeur


def actions_par_facteur(codes: str, ips_tap: float | None) -> list[dict]:
    """Pistes d'action pour chaque facteur cite, avec son libelle francais."""
    resultat = []
    for code in (codes or "").split(";"):
        code = code.strip()
        if not code or code == "aucun_facteur_marquant":
            continue
        pistes = list(ACTIONS_PAR_FACTEUR.get(code, []))
        if code == "disparite_filles_garcons" and ips_tap is not None:
            retard = "les filles" if ips_tap < 1 else "les garçons"
            pistes = [f"Actions ciblées sur {retard} : c'est le groupe le plus "
                      f"en retard dans cette région (indice de parité "
                      f"filles/garçons de l'achèvement = {ips_tap:.2f})"]
        if pistes:
            resultat.append({
                "facteur": code,
                "libelle": LIBELLES_FACTEURS.get(code, code.replace("_", " ")),
                "actions": pistes,
            })
    return resultat


@app.get("/modele", tags=["Modele"])
def modele():
    """Modele de prevision retenu, regle de decision, metriques et incertitude 2026.

    Lit les sorties de `pipeline/modele_risque.py` dans data/04_analyse/.
    """
    fichier_metriques = DOSSIER_ANALYSE / FICHIER_METRIQUES
    fichier_incertitude = DOSSIER_ANALYSE / FICHIER_INCERTITUDE
    manquants = [f.name for f in (fichier_metriques, fichier_incertitude)
                 if not f.exists()]
    if manquants:
        raise HTTPException(404, (
            f"Sorties du modele absentes : {', '.join(manquants)}. "
            "Lancer : python pipeline/modele_risque.py"))

    metriques = _lire_csv(fichier_metriques)
    for ligne in metriques:
        for colonne in ("mae", "rmse", "justesse_niveau", "f1_critique",
                        "lignes_entrainement", "lignes_test"):
            if colonne in ligne:
                ligne[colonne] = _nombre(ligne[colonne])

    retenu = next((l["modele"] for l in metriques
                   if l.get("retenu_pour_2026") == "oui"), None)
    glissantes = [l for l in metriques if l.get("protocole") == "glissante"]
    plis_retenu = [l["mae"] for l in glissantes
                   if l["modele"] == retenu and l["mae"] is not None]
    mae_moyenne = (round(sum(plis_retenu) / len(plis_retenu), 3)
                   if plis_retenu else None)

    incertitude = []
    for ligne in _lire_csv(fichier_incertitude):
        incertitude.append({
            "region_code": ligne["region_code"],
            "annee": int(ligne["annee"]),
            "score": _nombre(ligne["score"]),
            "score_bas": _nombre(ligne["score_bas"]),
            "score_haut": _nombre(ligne["score_haut"]),
            "proba_critique": _nombre(ligne["proba_critique"]),
        })

    return {
        "modele_retenu": retenu,
        "mae_moyenne_glissante": mae_moyenne,
        "regle_de_decision": (
            "Le modele retenu est celui qui obtient la plus faible erreur moyenne "
            "(MAE) sur trois validations glissantes : apprendre sur tout le passe "
            "disponible et prevoir l'annee suivante. Si l'avance d'un modele appris "
            "sur la reference naive est inferieure a 0,3 point de MAE, on garde la "
            "reference naive, plus simple. Cette regle a ete fixee avant de regarder "
            "les resultats."),
        "protocoles": {
            "fixe": [l for l in metriques if l.get("protocole") == "fixe"],
            "glissante": glissantes,
        },
        "incertitude_2026": incertitude,
        "seuils": {"modere": 33, "critique": 66},
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
    ips_tap = next((r["valeur"] for r in recents
                    if r["indicateur"] == "ips_tap" and r["sexe"] == "T"), None)
    incertitude = None
    if actuel and actuel["est_prevision"]:
        fichier = DOSSIER_ANALYSE / FICHIER_INCERTITUDE
        if fichier.exists():
            incertitude = next(
                ({"score_bas": _nombre(l["score_bas"]),
                  "score_haut": _nombre(l["score_haut"]),
                  "proba_critique": _nombre(l["proba_critique"])}
                 for l in _lire_csv(fichier) if l["region_code"] == code), None)
    return {
        "region_code": code,
        "region_nom": nom,
        "risque_actuel": actuel,
        "historique_risque": historique,
        "annee_indicateurs": derniere,
        "indicateurs": recents,
        "recommandations": RECOMMANDATIONS.get(actuel["niveau"], []) if actuel else [],
        "actions_par_facteur": (actions_par_facteur(actuel["facteurs"], ips_tap)
                                if actuel else []),
        "incertitude_prevision": incertitude,
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


# Application web (Membre 2) servie par l'API : http://localhost:8000/app/
# Monte en dernier pour ne masquer aucune route de l'API.
if DOSSIER_FRONTEND.is_dir():
    app.mount("/app", StaticFiles(directory=DOSSIER_FRONTEND, html=True),
              name="application")
