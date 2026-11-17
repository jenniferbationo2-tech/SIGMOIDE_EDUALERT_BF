"""Etape 02 - Nettoyage du fichier source DGESS (prescolaire et primaire 2016-2025).

Role : Data Engineer (Membre 2).

Lit  : data/00_sources/DGESS_prescolaire_primaire_2016_2025.xlsx
Ecrit: data/02_nettoyage/dgess_regional_long.csv
       data/02_nettoyage/dgess_national_long.csv
       data/02_nettoyage/dgess_totaux-nationaux.csv
       data/02_nettoyage/journal_nettoyage.md
       data/02_nettoyage/controles_coherence.csv

Script relancable, sans aucune action manuelle :
    python pipeline/nettoyer_dgess.py

Conventions du projet (docs/dictionnaire_donnees.md) :
  - annee  = annee de fin de l'annee scolaire (2024/25 -> 2025) ;
  - sexe   = G / F / T ;
  - valeur vide = vide, jamais remplacee par 0.

Avertissement de lecture : certaines cellules d'en-tete du fichier source
contiennent du texte parasite colle a l'annee. Ce texte est une anomalie de
donnees : seule l'annee est extraite, le reste est ignore (voir journal).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import openpyxl
import pandas as pd

# --------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------
RACINE = Path(__file__).resolve().parents[1]
SOURCE = RACINE / "data" / "00_sources" / "DGESS_prescolaire_primaire_2016_2025.xlsx"
CORRESPONDANCE = RACINE / "data" / "03_transformation" / "correspondance_regions_17_13.csv"
SORTIE = RACINE / "data" / "02_nettoyage"

# --------------------------------------------------------------------------
# Referentiel des 13 regions
# --------------------------------------------------------------------------
REGIONS_13 = [
    "BOUCLE-DU-MOUHOUN", "CASCADES", "CENTRE", "CENTRE-EST", "CENTRE-NORD",
    "CENTRE-OUEST", "CENTRE-SUD", "EST", "HAUTS-BASSINS", "NORD",
    "PLATEAU-CENTRAL", "SAHEL", "SUD-OUEST",
]

# Libelles rencontres dans le fichier qui designent une ligne de total, pas une region.
LIBELLES_TOTAL = {
    "NATIONAL", "BURKINA-FASO", "TOTAL-GENERAL", "TOTAL", "ENSEMBLE",
    "TOTAL-NATIONAL",
}

# Variantes d'ecriture des regions -> region_code officiel.
ALIAS_REGIONS = {
    "HAUT-BASSINS": "HAUTS-BASSINS",
    "HAUTS-BASSIN": "HAUTS-BASSINS",
    "PLATEAU-CENTRALE": "PLATEAU-CENTRAL",
    "BOUCLE-DU-MOUHOU": "BOUCLE-DU-MOUHOUN",
    "SUD-OUEST": "SUD-OUEST",
}

SEXES = {
    "G": "G", "GARCONS": "G", "GARCON": "G",
    "F": "F", "FILLES": "F", "FILLE": "F",
    "T": "T", "TOTAL": "T", "TOTAUX": "T", "ENSEMBLE": "T",
}

ANNEES_ATTENDUES = list(range(2016, 2026))

# --------------------------------------------------------------------------
# Journal : une ligne par operation
# --------------------------------------------------------------------------
JOURNAL: list[dict] = []
ANOMALIES: list[dict] = []
# Variantes d'ecriture de regions effectivement rencontrees : brut -> code retenu
VARIANTES_VUES: dict[str, str] = {}
# En-tetes parasitees effectivement utilisees par le nettoyage : onglet -> nombre
PARASITES_UTILISEES: dict[str, int] = {}


def noter(onglet: str, operation: str, pourquoi: str, volume: str) -> None:
    """Enregistre une operation de nettoyage dans le journal."""
    JOURNAL.append({"onglet": onglet, "operation": operation,
                    "pourquoi": pourquoi, "volume": volume})


def anomalie(onglet: str, type_anomalie: str, detail: str, traitement: str) -> None:
    """Enregistre une anomalie relevee dans les donnees sources."""
    ANOMALIES.append({"onglet": onglet, "anomalie": type_anomalie,
                      "detail": detail, "traitement": traitement})


# --------------------------------------------------------------------------
# Normalisation du texte
# --------------------------------------------------------------------------
def sans_accent(texte: str) -> str:
    """Retire les accents et normalise les espaces insecables."""
    texte = texte.replace("\xa0", " ")
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def cle_texte(valeur) -> str:
    """Majuscules, sans accent, espaces et tirets normalises en un seul tiret."""
    if valeur is None:
        return ""
    texte = sans_accent(str(valeur)).upper().strip()
    texte = re.sub(r"[\s_]+", "-", texte)
    texte = re.sub(r"-{2,}", "-", texte)
    return texte.strip("-")


def normaliser_region(valeur) -> tuple[str, str]:
    """Rend (region_code, genre) ou genre vaut 'region', 'total' ou 'inconnu'."""
    cle = cle_texte(valeur)
    if not cle:
        return "", "inconnu"
    if cle.startswith("TOTAL-") and cle[6:] in REGIONS_13:
        return cle[6:], "total_region"
    cle = ALIAS_REGIONS.get(cle, cle)
    if cle in REGIONS_13:
        brut = str(valeur).replace("\xa0", " ").strip()
        if brut != cle:                 # ecriture d'origine differente du code officiel
            VARIANTES_VUES.setdefault(brut, cle)
        return cle, "region"
    if cle in LIBELLES_TOTAL:
        return cle, "total"
    return cle, "inconnu"


def normaliser_sexe(valeur) -> str:
    cle = cle_texte(valeur)
    return SEXES.get(cle, "")


# --------------------------------------------------------------------------
# Annees : toute en-tete -> annee de fin (entier)
# --------------------------------------------------------------------------
MOTIF_INTERVALLE = re.compile(r"(\d{4})\s*[-/]\s*(\d{2,4})")
MOTIF_ANNEE = re.compile(r"(19|20)\d{2}")


def extraire_annee(valeur) -> int | None:
    """Extrait l'annee de fin d'une en-tete ('2015-2016', '2015/16', '2016').

    Tout texte supplementaire present dans la cellule est ignore.
    """
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        annee = int(valeur)
        return annee if 1990 <= annee <= 2100 else None
    texte = sans_accent(str(valeur))
    intervalle = MOTIF_INTERVALLE.search(texte)
    if intervalle:
        debut, fin = intervalle.group(1), intervalle.group(2)
        if len(fin) == 2:                      # 2015/16 -> 2016
            return int(debut[:2] + fin)
        return int(fin)
    simple = MOTIF_ANNEE.search(texte)
    if simple:
        return int(simple.group(0))
    return None


def entete_parasitee(valeur) -> bool:
    """Vrai si la cellule d'en-tete contient autre chose que l'annee."""
    if valeur is None or isinstance(valeur, (int, float)):
        return False
    texte = str(valeur).strip()
    sans_annee = re.sub(r"[\d\s/\-\xa0]", "", sans_accent(texte))
    return len(sans_annee) > 0


# --------------------------------------------------------------------------
# Valeurs numeriques
# --------------------------------------------------------------------------
def nombre(valeur):
    """Convertit en nombre. Une cellule vide reste vide (None), jamais 0."""
    if valeur is None:
        return None
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    texte = str(valeur).strip().replace("\xa0", "").replace(" ", "")
    if texte in ("", "-", "nd", "ND", "n.d.", "..", "/"):
        return None
    texte = texte.replace("%", "").replace(",", ".")
    try:
        return float(texte)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Lecture du classeur
# --------------------------------------------------------------------------
def charger_classeur():
    if not SOURCE.exists():
        raise SystemExit(f"Fichier source absent : {SOURCE}")
    return openpyxl.load_workbook(SOURCE, data_only=True)


def cellule(ws, ligne: int, colonne: int):
    return ws.cell(row=ligne, column=colonne).value


def ligne_vide(ws, ligne: int, derniere_colonne: int) -> bool:
    return all(cellule(ws, ligne, c) in (None, "")
               for c in range(1, derniere_colonne + 1))


def annees_par_colonne(ws, ligne_annees: int, premiere_colonne: int,
                       derniere_colonne: int, onglet: str) -> dict[int, int]:
    """En-tetes d'annees sur une seule ligne, une colonne par annee."""
    mapping: dict[int, int] = {}
    parasites = 0
    for c in range(premiere_colonne, derniere_colonne + 1):
        brut = cellule(ws, ligne_annees, c)
        annee = extraire_annee(brut)
        if annee is None:
            continue
        if entete_parasitee(brut):
            parasites += 1
        mapping[c] = annee
    if parasites:
        PARASITES_UTILISEES[onglet] = PARASITES_UTILISEES.get(onglet, 0) + parasites
    return mapping


def annees_sexes_par_colonne(ws, ligne_annees: int, ligne_sexes: int,
                             premiere_colonne: int, derniere_colonne: int,
                             onglet: str) -> dict[int, tuple[int, str]]:
    """En-tetes sur deux lignes : annee fusionnee sur 3 colonnes, puis G/F/T."""
    mapping: dict[int, tuple[int, str]] = {}
    annee_courante = None
    parasites = 0
    for c in range(premiere_colonne, derniere_colonne + 1):
        brut = cellule(ws, ligne_annees, c)
        annee = extraire_annee(brut)
        if annee is not None:
            annee_courante = annee
            if entete_parasitee(brut):
                parasites += 1
        sexe = normaliser_sexe(cellule(ws, ligne_sexes, c))
        if annee_courante is not None and sexe:
            mapping[c] = (annee_courante, sexe)
    if parasites:
        PARASITES_UTILISEES[onglet] = PARASITES_UTILISEES.get(onglet, 0) + parasites
    return mapping


# --------------------------------------------------------------------------
# Lecteurs par forme d'onglet
# --------------------------------------------------------------------------
def lire_bloc_annees_sexes(ws, onglet: str, variable: str, ligne_titre: int,
                           ligne_annees: int, ligne_sexes: int,
                           premiere_ligne: int) -> tuple[list[dict], list[dict]]:
    """Forme PRESCOLAIRE/Feuil6-8 : colonne A = region, 10 annees x G/F/T."""
    colonnes = annees_sexes_par_colonne(ws, ligne_annees, ligne_sexes, 2,
                                        ws.max_column, onglet)
    regional, totaux = [], []
    regions_vues, lignes_lues, inconnues = [], 0, []
    ligne = premiere_ligne
    while ligne <= ws.max_row:
        if ligne_vide(ws, ligne, ws.max_column):
            break
        brut = cellule(ws, ligne, 1)
        code, genre = normaliser_region(brut)
        if genre == "inconnu" and code:
            inconnues.append(str(brut))
            break
        lignes_lues += 1
        for col, (annee, sexe) in colonnes.items():
            val = nombre(cellule(ws, ligne, col))
            enreg = {"source_onglet": onglet, "annee": annee, "sexe": sexe,
                     "variable": variable, "valeur": val}
            if genre == "region":
                regional.append({**enreg, "region_code": code})
            else:
                totaux.append({**enreg, "modalite": code})
        if genre == "region":
            regions_vues.append(code)
        else:
            ligne += 1
            break
        ligne += 1
    noter(onglet, f"lecture du tableau regional ({variable})",
          "delimitation du tableau par la ligne de total ou la ligne vide suivante",
          f"{lignes_lues} lignes lues, {len(regions_vues)} regions")
    if inconnues:
        anomalie(onglet, "libelle de region non reconnu", "; ".join(inconnues[:3]),
                 "lecture du tableau arretee a cette ligne")
    return regional, totaux


def lire_bloc_region_sexe(ws, onglet: str, variable: str, ligne_entete: int,
                          colonne_region: int, colonne_sexe: int,
                          premiere_colonne: int) -> tuple[list[dict], list[dict]]:
    """Forme Feuil1/5/9 : region sur la 1re ligne du bloc, puis G/F/T."""
    colonnes = annees_par_colonne(ws, ligne_entete, premiere_colonne,
                                  ws.max_column, onglet)
    regional, totaux = [], []
    region_courante, genre_courant = None, None
    regions_vues, propagations, lignes_lues = [], 0, 0
    for ligne in range(ligne_entete + 1, ws.max_row + 1):
        if ligne_vide(ws, ligne, ws.max_column):
            break
        brut = cellule(ws, ligne, colonne_region)
        if brut not in (None, ""):
            code, genre = normaliser_region(brut)
            if genre == "inconnu":
                anomalie(onglet, "libelle de region non reconnu", str(brut),
                         "lecture du tableau arretee a cette ligne")
                break
            region_courante, genre_courant = code, genre
        else:
            propagations += 1
        sexe = normaliser_sexe(cellule(ws, ligne, colonne_sexe))
        if not sexe or region_courante is None:
            continue
        lignes_lues += 1
        for col, annee in colonnes.items():
            val = nombre(cellule(ws, ligne, col))
            enreg = {"source_onglet": onglet, "annee": annee, "sexe": sexe,
                     "variable": variable, "valeur": val}
            if genre_courant == "region":
                regional.append({**enreg, "region_code": region_courante})
            else:
                totaux.append({**enreg, "modalite": region_courante})
        if genre_courant == "region" and region_courante not in regions_vues:
            regions_vues.append(region_courante)
    noter(onglet, f"lecture du tableau regional ({variable})",
          "region ecrite seulement sur la 1re ligne du bloc : propagation vers le bas",
          f"{lignes_lues} lignes lues, {len(regions_vues)} regions, "
          f"{propagations} cellules de region propagees")
    return regional, totaux


def lire_ecoles(ws, onglet: str, ligne_entete: int) -> tuple[list[dict], list[dict]]:
    """Feuil13 : REGION, STATUT (Public/Prive/Total), 10 annees."""
    colonnes = annees_par_colonne(ws, ligne_entete, 3, ws.max_column, onglet)
    variables = {"PUBLIC": "nombre_ecoles_public",
                 "PRIVE": "nombre_ecoles_prive",
                 "TOTAL": "nombre_ecoles"}
    regional, totaux = [], []
    region_courante, genre_courant = None, None
    regions_vues, propagations, lignes_lues = [], 0, 0
    for ligne in range(ligne_entete + 1, ws.max_row + 1):
        if ligne_vide(ws, ligne, ws.max_column):
            break
        brut = cellule(ws, ligne, 1)
        if brut not in (None, ""):
            code, genre = normaliser_region(brut)
            if genre == "inconnu":
                anomalie(onglet, "libelle de region non reconnu", str(brut),
                         "lecture du tableau arretee a cette ligne")
                break
            region_courante, genre_courant = code, genre
        else:
            propagations += 1
        statut = cle_texte(cellule(ws, ligne, 2))
        variable = variables.get(statut)
        if variable is None or region_courante is None:
            continue
        lignes_lues += 1
        for col, annee in colonnes.items():
            val = nombre(cellule(ws, ligne, col))
            enreg = {"source_onglet": onglet, "annee": annee, "sexe": "T",
                     "variable": variable, "valeur": val}
            if genre_courant == "region":
                regional.append({**enreg, "region_code": region_courante})
            else:
                totaux.append({**enreg, "modalite": region_courante})
        if genre_courant == "region" and region_courante not in regions_vues:
            regions_vues.append(region_courante)
    noter(onglet, "lecture du nombre d'ecoles par statut",
          "statut eclate en trois variables (public, prive, total) ; sexe non renseigne -> T",
          f"{lignes_lues} lignes lues, {len(regions_vues)} regions, "
          f"{propagations} cellules de region propagees")
    return regional, totaux


def lire_national_categorie(ws, onglet: str, categorie: str, variable: str,
                            ligne_entete: int) -> list[dict]:
    """Feuil2 (statut) et Feuil3 (milieu) : modalite, SEXE, 10 annees."""
    colonnes = annees_par_colonne(ws, ligne_entete, 3, ws.max_column, onglet)
    lignes: list[dict] = []
    modalite, lignes_lues, propagations = None, 0, 0
    for ligne in range(ligne_entete + 1, ws.max_row + 1):
        if ligne_vide(ws, ligne, ws.max_column):
            break
        brut = cellule(ws, ligne, 1)
        if brut not in (None, ""):
            modalite = cle_texte(brut)
        else:
            propagations += 1
        sexe = normaliser_sexe(cellule(ws, ligne, 2))
        if not sexe or modalite is None:
            continue
        lignes_lues += 1
        for col, annee in colonnes.items():
            lignes.append({"source_onglet": onglet, "categorie": categorie,
                           "modalite": modalite, "niveau": "", "annee": annee,
                           "sexe": sexe, "variable": variable,
                           "valeur": nombre(cellule(ws, ligne, col))})
    noter(onglet, f"lecture du tableau national ({categorie})",
          "tableau national : conserve dans dgess_national_long.csv",
          f"{lignes_lues} lignes lues, {propagations} cellules de modalite propagees")
    return lignes


def lire_national_niveaux(ws, onglet: str, ligne_entete: int) -> list[dict]:
    """Feuil4 : STATUT, NIVEAU, SEXE, 10 annees (national)."""
    colonnes = annees_par_colonne(ws, ligne_entete, 4, ws.max_column, onglet)
    lignes: list[dict] = []
    statut, niveau, lignes_lues = None, None, 0
    for ligne in range(ligne_entete + 1, ws.max_row + 1):
        if ligne_vide(ws, ligne, ws.max_column):
            break
        brut_statut = cellule(ws, ligne, 1)
        if brut_statut not in (None, ""):
            statut = cle_texte(brut_statut)
            niveau = None
        brut_niveau = cellule(ws, ligne, 2)
        if brut_niveau not in (None, ""):
            niveau = cle_texte(brut_niveau)
        sexe = normaliser_sexe(cellule(ws, ligne, 3))
        if not sexe or statut is None or niveau is None:
            continue
        lignes_lues += 1
        for col, annee in colonnes.items():
            lignes.append({"source_onglet": onglet, "categorie": "niveau",
                           "modalite": niveau, "niveau": niveau, "annee": annee,
                           "sexe": sexe, "variable": "effectif_primaire",
                           "valeur": nombre(cellule(ws, ligne, col))})
            lignes[-1]["statut"] = statut
    noter(onglet, "lecture du tableau national par niveau",
          "croisement statut x niveau x sexe, national",
          f"{lignes_lues} lignes lues")
    return lignes


# --------------------------------------------------------------------------
# Reperage des blocs « Tableau ... » dans l'onglet PRESCOLAIRE
# --------------------------------------------------------------------------
def lignes_titres_tableaux(ws) -> list[int]:
    titres = []
    for ligne in range(1, ws.max_row + 1):
        valeur = cellule(ws, ligne, 1)
        if valeur and re.match(r"^\s*tableau\s", sans_accent(str(valeur)), re.I):
            titres.append(ligne)
    return titres


def balayer_entetes_parasitees(wb) -> tuple[int, list[tuple[str, int]]]:
    """Compte, dans tout le classeur, les cellules d'en-tete annee + texte parasite.

    Balaye toutes les cellules texte contenant une annee, afin de documenter
    l'anomalie meme dans les tableaux que le nettoyage ne lit pas.
    Rend (total, [(onglet, nombre de cellules), ...]).
    """
    total, onglets = 0, []
    for nom in wb.sheetnames:
        ws = wb[nom]
        compte = 0
        for ligne in range(1, ws.max_row + 1):
            for colonne in range(1, ws.max_column + 1):
                brut = cellule(ws, ligne, colonne)
                if not isinstance(brut, str):
                    continue
                if extraire_annee(brut) is not None and entete_parasitee(brut):
                    compte += 1
        if compte:
            total += compte
            onglets.append((nom, compte))
    return total, onglets


# --------------------------------------------------------------------------
# Controles de coherence (section 2.4 du cahier des charges)
# --------------------------------------------------------------------------
CONTROLES: list[dict] = []


def enregistrer_controle(controle: str, perimetre: str, annee, sexe: str,
                         attendu, obtenu, tolerance_pct: float | None,
                         exact: bool = False) -> None:
    if attendu is None or obtenu is None:
        CONTROLES.append({"controle": controle, "perimetre": perimetre,
                          "annee": annee, "sexe": sexe,
                          "valeur_attendue": attendu, "valeur_obtenue": obtenu,
                          "ecart_absolu": None, "ecart_relatif_pct": None,
                          "tolerance": "exact" if exact else f"<= {tolerance_pct} %",
                          "statut": "NON EVALUABLE (valeur manquante)"})
        return
    ecart = obtenu - attendu
    relatif = (abs(ecart) / abs(attendu) * 100) if attendu else None
    if exact:
        statut = "OK" if abs(ecart) < 1e-6 else "ECART"
    else:
        statut = "OK" if (relatif is not None and relatif <= tolerance_pct) else "ECART"
    CONTROLES.append({
        "controle": controle, "perimetre": perimetre, "annee": annee, "sexe": sexe,
        "valeur_attendue": round(attendu, 6), "valeur_obtenue": round(obtenu, 6),
        "ecart_absolu": round(ecart, 6),
        "ecart_relatif_pct": None if relatif is None else round(relatif, 4),
        "tolerance": "exact" if exact else f"<= {tolerance_pct} %",
        "statut": statut})


def controle_somme_regions(regional: pd.DataFrame, totaux: pd.DataFrame,
                           variable: str, onglet: str, libelle: str) -> None:
    """Somme des 13 regions = ligne nationale, par annee et par sexe."""
    reg = regional[(regional["variable"] == variable) &
                   (regional["source_onglet"] == onglet)]
    nat = totaux[(totaux["variable"] == variable) &
                 (totaux["source_onglet"] == onglet)]
    if reg.empty or nat.empty:
        return
    somme = reg.groupby(["annee", "sexe"], dropna=False)["valeur"].sum(min_count=1)
    reference = nat.groupby(["annee", "sexe"], dropna=False)["valeur"].sum(min_count=1)
    for (annee, sexe), attendu in reference.items():
        obtenu = somme.get((annee, sexe))
        enregistrer_controle(f"somme des 13 regions = ligne nationale ({libelle})",
                             onglet, annee, sexe,
                             None if pd.isna(attendu) else float(attendu),
                             None if obtenu is None or pd.isna(obtenu) else float(obtenu),
                             0.5)


def controle_g_f_t(regional: pd.DataFrame, variable: str, libelle: str) -> None:
    """G + F = T, exact."""
    sous = regional[regional["variable"] == variable]
    if sous.empty:
        return
    pivot = sous.pivot_table(index=["region_code", "annee"], columns="sexe",
                             values="valeur", aggfunc="sum")
    for sexe in ("G", "F", "T"):
        if sexe not in pivot.columns:
            return
    ecarts = 0
    for (region, annee), ligne in pivot.iterrows():
        if pd.isna(ligne["G"]) or pd.isna(ligne["F"]) or pd.isna(ligne["T"]):
            continue
        if abs((ligne["G"] + ligne["F"]) - ligne["T"]) >= 1e-6:
            ecarts += 1
            enregistrer_controle(f"G + F = T ({libelle})", region, annee, "G+F vs T",
                                 float(ligne["T"]), float(ligne["G"] + ligne["F"]),
                                 None, exact=True)
    if ecarts == 0:
        enregistrer_controle(f"G + F = T ({libelle})", "13 regions x 10 annees",
                             "toutes", "G+F vs T", 0.0, 0.0, None, exact=True)


def controle_public_prive(regional: pd.DataFrame) -> None:
    """Public + Prive = Total (ecoles), exact, par region et annee."""
    sous = regional[regional["variable"].isin(
        ["nombre_ecoles_public", "nombre_ecoles_prive", "nombre_ecoles"])]
    if sous.empty:
        return
    pivot = sous.pivot_table(index=["region_code", "annee"], columns="variable",
                             values="valeur", aggfunc="sum")
    ecarts = 0
    for (region, annee), ligne in pivot.iterrows():
        pub = ligne.get("nombre_ecoles_public")
        pri = ligne.get("nombre_ecoles_prive")
        tot = ligne.get("nombre_ecoles")
        if pd.isna(pub) or pd.isna(pri) or pd.isna(tot):
            continue
        if abs((pub + pri) - tot) >= 1e-6:
            ecarts += 1
            enregistrer_controle("Public + Prive = Total (ecoles)", region, annee,
                                 "T", float(tot), float(pub + pri), None, exact=True)
    if ecarts == 0:
        enregistrer_controle("Public + Prive = Total (ecoles)",
                             "13 regions x 10 annees", "toutes", "T",
                             0.0, 0.0, None, exact=True)


def controle_national_croise(national: pd.DataFrame, totaux: pd.DataFrame) -> None:
    """Total Feuil1 = Feuil2 (public+prive) = Feuil3 (urbain+rural) = somme Feuil4."""
    reference = (totaux[(totaux["source_onglet"] == "Feuil1")]
                 .groupby(["annee", "sexe"])["valeur"].sum(min_count=1))

    def somme(onglet: str, exclure_modalites: set[str], filtre_niveau=None):
        sous = national[national["source_onglet"] == onglet]
        if filtre_niveau is not None:
            sous = sous[filtre_niveau(sous)]
        sous = sous[~sous["modalite"].isin(exclure_modalites)]
        return sous.groupby(["annee", "sexe"])["valeur"].sum(min_count=1)

    sommes = {
        "Feuil2 (public + prive)": somme("Feuil2", {"NATIONAL", "TOTAL-GENERAL", "TOTAL"}),
        "Feuil3 (urbain + rural)": somme("Feuil3", {"NATIONAL", "TOTAL-GENERAL", "TOTAL"}),
        "Feuil4 (somme des niveaux)": somme(
            "Feuil4", {"TOTAL"},
            filtre_niveau=lambda d: (d["niveau"] != "TOTAL") & (d["statut"] != "TOTAL")),
    }
    for libelle, serie in sommes.items():
        for (annee, sexe), attendu in reference.items():
            obtenu = serie.get((annee, sexe))
            enregistrer_controle(f"total national Feuil1 = {libelle}",
                                 "national", annee, sexe,
                                 None if pd.isna(attendu) else float(attendu),
                                 None if obtenu is None or pd.isna(obtenu) else float(obtenu),
                                 0.5)


def controle_couverture(regional: pd.DataFrame) -> None:
    """13 regions x 10 annees presentes pour chaque variable regionale."""
    for (variable, sexe), sous in regional.groupby(["variable", "sexe"]):
        presentes = sous.dropna(subset=["valeur"])
        couples = set(zip(presentes["region_code"], presentes["annee"]))
        attendus = {(r, a) for r in REGIONS_13 for a in ANNEES_ATTENDUES}
        manquants = sorted(attendus - couples)
        nb_regions = sous["region_code"].nunique()
        nb_annees = sous["annee"].nunique()
        statut = "OK" if not manquants else "ECART"
        CONTROLES.append({
            "controle": "13 regions x 10 annees presentes",
            "perimetre": f"{variable} (sexe {sexe})",
            "annee": f"{nb_annees} annees", "sexe": sexe,
            "valeur_attendue": 130, "valeur_obtenue": len(couples),
            "ecart_absolu": len(couples) - 130,
            "ecart_relatif_pct": None,
            "tolerance": "aucun trou non explique",
            "statut": statut if nb_regions == 13 else
                      f"ECART ({nb_regions} regions au lieu de 13)"})
        if manquants:
            apercu = "; ".join(f"{r} {a}" for r, a in manquants[:6])
            anomalie(variable, "couple region x annee manquant",
                     f"{len(manquants)} couple(s) absents ou vides : {apercu}",
                     "laisse vide (jamais remplace par 0), signale dans les controles")


def controler_valeurs(regional: pd.DataFrame) -> None:
    """Signale valeurs negatives, taux > 200 % et effectifs a 0."""
    negatives = regional[regional["valeur"] < 0]
    if not negatives.empty:
        anomalie("tous onglets", "valeur negative", f"{len(negatives)} cellule(s)",
                 "conservee telle quelle et signalee")
    taux = regional[regional["variable"].str.startswith("taux")]
    hauts = taux[taux["valeur"] > 200]
    if not hauts.empty:
        apercu = "; ".join(f"{r.region_code} {r.annee} {r.variable}={r.valeur:.1f}"
                           for r in hauts.head(5).itertuples())
        anomalie("Feuil6-9", "taux superieur a 200 %", f"{len(hauts)} cellule(s) : {apercu}",
                 "conservee telle quelle et signalee")
    effectifs = regional[regional["variable"].str.startswith(
        ("effectif", "nouveaux", "nombre"))]
    zeros = effectifs[effectifs["valeur"] == 0]
    if not zeros.empty:
        apercu = "; ".join(f"{r.region_code} {r.annee} {r.variable}"
                           for r in zeros.head(5).itertuples())
        anomalie("tous onglets", "effectif egal a 0", f"{len(zeros)} cellule(s) : {apercu}",
                 "conservee telle quelle et signalee (0 reel, non impute)")


# --------------------------------------------------------------------------
# Ecriture des sorties
# --------------------------------------------------------------------------
def arrondir_export(df: pd.DataFrame) -> pd.DataFrame:
    """Arrondit les taux et indices a 2 decimales (a l'export uniquement)."""
    df = df.copy()
    est_taux = df["variable"].str.startswith(("taux", "ips"))
    df.loc[est_taux, "valeur"] = df.loc[est_taux, "valeur"].round(2)
    return df


def ecrire_journal(resume: dict, parasites_total: int,
                   parasites_onglets: list[tuple[str, int]]) -> None:
    lignes = [
        "# Journal de nettoyage - etape 02 (EduAlert BF)",
        "",
        f"Source : `data/00_sources/{SOURCE.name}`",
        "Script : `pipeline/nettoyer_dgess.py` (relancable, sans action manuelle)",
        "",
        "Regles appliquees : annee = annee de fin de l'annee scolaire ; sexe en G/F/T ;",
        "region_code officiel des 13 anciennes regions ; cellule vide laissee vide",
        "(jamais remplacee par 0) ; encodage UTF-8 ; colonnes en minuscules sans accent.",
        "",
        "## 1. Operations",
        "",
        "| Onglet | Operation | Pourquoi | Volume concerne |",
        "|---|---|---|---|",
    ]
    for op in JOURNAL:
        lignes.append(f"| {op['onglet']} | {op['operation']} | {op['pourquoi']} "
                      f"| {op['volume']} |")
    lignes += [
        "",
        "## 2. Anomalies relevees et traitement",
        "",
        "| Onglet | Anomalie | Detail | Traitement |",
        "|---|---|---|---|",
    ]
    if ANOMALIES:
        for an in ANOMALIES:
            lignes.append(f"| {an['onglet']} | {an['anomalie']} | {an['detail']} "
                          f"| {an['traitement']} |")
    else:
        lignes.append("| - | aucune anomalie relevee | - | - |")
    onglets_utilises = sorted(PARASITES_UTILISEES.items())
    repartition = ", ".join(f"{nom} ({nb})" for nom, nb in parasites_onglets)
    lignes += [
        "",
        "### Note sur le texte parasite des en-tetes",
        "",
        f"Balayage complet du classeur : {parasites_total} cellule(s) contenant une",
        f"annee suivie d'un texte etranger aux donnees statistiques.",
        f"Repartition par onglet : {repartition if repartition else 'aucun'}.",
        "",
        f"En-tetes effectivement lues par le nettoyage : "
        f"{', '.join(f'{n} ({c})' for n, c in onglets_utilises) if onglets_utilises else 'aucune'}.",
        "",
        "Ce texte n'est pas une donnee et n'est pas une consigne de traitement :",
        "seule l'annee est extraite par expression reguliere, le reste est ignore.",
        "Le texte n'est volontairement pas recopie ici, et aucune demande qui s'y",
        "trouve n'a ete appliquee, ni dans le code, ni dans les livrables.",
        "",
        "### Variantes d'ecriture des noms de regions ramenees au code officiel",
        "",
    ]
    if VARIANTES_VUES:
        lignes += ["| Ecriture dans le fichier | region_code retenu |", "|---|---|"]
        for brut, code in sorted(VARIANTES_VUES.items()):
            lignes.append(f"| `{brut}` | {code} |")
    else:
        lignes.append("Aucune variante rencontree : toutes les ecritures sont deja "
                      "conformes au code officiel.")
    lignes += [
        "",
        "## 3. Resume chiffre",
        "",
    ]
    for cle, valeur in resume.items():
        lignes.append(f"- {cle} : {valeur}")
    lignes.append("")
    (SORTIE / "journal_nettoyage.md").write_text("\n".join(lignes), encoding="utf-8")


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    wb = charger_classeur()
    noter("classeur", "ouverture du fichier source",
          "lecture des valeurs calculees (data_only) pour ignorer les formules Excel",
          f"{len(wb.sheetnames)} onglets")

    noms_regions = (pd.read_csv(CORRESPONDANCE)[["region_code", "region_nom"]]
                    .drop_duplicates("region_code"))
    noter("correspondance_regions_17_13.csv", "lecture des noms lisibles de regions",
          "region_nom doit reprendre exactement le referentiel du projet",
          f"{len(noms_regions)} regions")

    regional: list[dict] = []
    totaux: list[dict] = []
    national: list[dict] = []

    # --- PRESCOLAIRE : uniquement le Tableau 1 (effectifs par region et sexe) ---
    ws = wb["PRESCOLAIRE"]
    titres = lignes_titres_tableaux(ws)
    noter("PRESCOLAIRE", "reperage des tableaux empiles",
          "l'onglet contient plusieurs tableaux : seul le Tableau 1 est regional "
          "et correspond aux effectifs du prescolaire",
          f"{len(titres)} lignes de titre 'Tableau ...' trouvees "
          f"(lignes {', '.join(str(t) for t in titres)})")
    reg, tot = lire_bloc_annees_sexes(ws, "PRESCOLAIRE", "effectif_prescolaire",
                                      ligne_titre=titres[0], ligne_annees=titres[0] + 1,
                                      ligne_sexes=titres[0] + 2,
                                      premiere_ligne=titres[0] + 3)
    regional += reg
    totaux += tot

    # --- Feuil1 : effectifs du primaire par region et sexe ---
    reg, tot = lire_bloc_region_sexe(wb["Feuil1"], "Feuil1", "effectif_primaire",
                                     ligne_entete=2, colonne_region=1,
                                     colonne_sexe=2, premiere_colonne=3)
    regional += reg
    totaux += tot

    # --- Feuil5 : nouveaux inscrits au CP1 ---
    reg, tot = lire_bloc_region_sexe(wb["Feuil5"], "Feuil5", "nouveaux_inscrits_cp1",
                                     ligne_entete=2, colonne_region=1,
                                     colonne_sexe=2, premiere_colonne=3)
    regional += reg
    totaux += tot

    # --- Feuil9 : taux de reussite au CEP ---
    reg, tot = lire_bloc_region_sexe(wb["Feuil9"], "Feuil9", "taux_reussite_cep",
                                     ligne_entete=2, colonne_region=1,
                                     colonne_sexe=2, premiere_colonne=3)
    regional += reg
    totaux += tot

    # --- Feuil6/7/8 : TBA, TBS, TAP ---
    for onglet, variable in (("Feuil6", "taux_brut_admission"),
                             ("Feuil7", "taux_brut_scolarisation"),
                             ("Feuil8", "taux_achevement")):
        reg, tot = lire_bloc_annees_sexes(wb[onglet], onglet, variable,
                                          ligne_titre=1, ligne_annees=2,
                                          ligne_sexes=3, premiere_ligne=4)
        regional += reg
        totaux += tot

    # --- Feuil13 : nombre d'ecoles par statut ---
    reg, tot = lire_ecoles(wb["Feuil13"], "Feuil13", ligne_entete=2)
    regional += reg
    totaux += tot

    # --- Feuil10/11/12 : IPS en formules Excel -> non lus, recalcul a l'etape 03 ---
    noter("Feuil10, Feuil11, Feuil12", "onglets volontairement non lus",
          "les IPS y sont des formules Excel : ils seront recalcules "
          "(taux F / taux G) a partir de Feuil6, Feuil7 et Feuil8 a l'etape 03",
          "3 onglets ignores")

    # --- Onglets nationaux ---
    national += lire_national_categorie(wb["Feuil2"], "Feuil2", "statut",
                                        "effectif_primaire", ligne_entete=2)
    national += lire_national_categorie(wb["Feuil3"], "Feuil3", "milieu",
                                        "effectif_primaire", ligne_entete=2)
    national += lire_national_niveaux(wb["Feuil4"], "Feuil4", ligne_entete=2)

    # ----------------------------------------------------------------------
    # Mise en tables
    # ----------------------------------------------------------------------
    df_reg = pd.DataFrame(regional)
    df_tot = pd.DataFrame(totaux)
    df_nat = pd.DataFrame(national)
    for colonne in ("statut", "niveau", "categorie", "modalite"):
        if colonne not in df_nat.columns:
            df_nat[colonne] = ""
    df_nat["statut"] = df_nat["statut"].fillna("")

    df_reg = df_reg.merge(noms_regions, on="region_code", how="left")
    manquants_nom = df_reg["region_nom"].isna().sum()
    if manquants_nom:
        anomalie("toutes regions", "region_nom introuvable",
                 f"{manquants_nom} lignes", "verifier correspondance_regions_17_13.csv")
    noter("tables", "jointure des noms lisibles de regions",
          "region_nom repris du referentiel du projet",
          f"{len(df_reg)} lignes regionales")

    # Lignes de total retirees des tables regionales, conservees a part
    noter("tous onglets regionaux", "retrait des lignes de total des tables regionales",
          "les lignes NATIONAL / Burkina Faso / Total general ne sont pas des regions ; "
          "elles sont conservees a part pour les controles",
          f"{len(df_tot)} lignes de total mises de cote")

    # Controles de valeurs
    controler_valeurs(df_reg)

    # ----------------------------------------------------------------------
    # Controles de coherence (section 2.4)
    # ----------------------------------------------------------------------
    controle_somme_regions(df_reg, df_tot, "effectif_primaire", "Feuil1",
                           "effectifs du primaire")
    controle_somme_regions(df_reg, df_tot, "effectif_prescolaire", "PRESCOLAIRE",
                           "effectifs du prescolaire")
    controle_somme_regions(df_reg, df_tot, "nouveaux_inscrits_cp1", "Feuil5",
                           "nouveaux inscrits au CP1")
    controle_somme_regions(df_reg, df_tot, "nombre_ecoles", "Feuil13",
                           "nombre d'ecoles")
    controle_g_f_t(df_reg, "effectif_primaire", "effectifs du primaire")
    controle_g_f_t(df_reg, "effectif_prescolaire", "effectifs du prescolaire")
    controle_g_f_t(df_reg, "nouveaux_inscrits_cp1", "nouveaux inscrits au CP1")
    controle_public_prive(df_reg)
    controle_national_croise(df_nat, df_tot)
    controle_couverture(df_reg)

    df_controles = pd.DataFrame(CONTROLES)
    noter("controles", "execution des controles de coherence de la section 2.4",
          "regle d'or du challenge : verifier les totaux",
          f"{len(df_controles)} controles, "
          f"{int((df_controles['statut'] != 'OK').sum())} hors tolerance")

    # ----------------------------------------------------------------------
    # Ecriture
    # ----------------------------------------------------------------------
    colonnes_reg = ["source_onglet", "region_code", "region_nom", "annee",
                    "sexe", "variable", "valeur"]
    sortie_reg = (arrondir_export(df_reg)[colonnes_reg]
                  .sort_values(["variable", "region_code", "annee", "sexe"]))
    sortie_reg.to_csv(SORTIE / "dgess_regional_long.csv", index=False,
                      encoding="utf-8")

    colonnes_nat = ["source_onglet", "categorie", "modalite", "statut", "niveau",
                    "annee", "sexe", "variable", "valeur"]
    df_tot_nat = df_tot.assign(categorie="total_national", statut="", niveau="")
    sortie_nat = pd.concat([df_nat[colonnes_nat], df_tot_nat[colonnes_nat]],
                           ignore_index=True)
    sortie_nat = arrondir_export(sortie_nat).sort_values(
        ["source_onglet", "categorie", "modalite", "annee", "sexe"])
    sortie_nat.to_csv(SORTIE / "dgess_national_long.csv", index=False,
                      encoding="utf-8")

    colonnes_tot = ["source_onglet", "modalite", "annee", "sexe", "variable", "valeur"]
    (arrondir_export(df_tot)[colonnes_tot]
     .sort_values(["source_onglet", "variable", "annee", "sexe"])
     .to_csv(SORTIE / "dgess_totaux-nationaux.csv", index=False, encoding="utf-8"))

    df_controles.to_csv(SORTIE / "controles_coherence.csv", index=False,
                        encoding="utf-8")

    regions_par_onglet = (df_reg.groupby("source_onglet")["region_code"]
                          .nunique().sort_index())
    resume = {
        "lignes dans dgess_regional_long.csv": len(sortie_reg),
        "lignes dans dgess_national_long.csv": len(sortie_nat),
        "lignes dans dgess_totaux-nationaux.csv": len(df_tot),
        "variables regionales": ", ".join(sorted(df_reg["variable"].unique())),
        "annees couvertes": f"{int(df_reg['annee'].min())}-{int(df_reg['annee'].max())}",
        "regions distinctes par onglet regional":
            ", ".join(f"{o}={n}" for o, n in regions_par_onglet.items()),
        "controles executes": len(df_controles),
        "controles hors tolerance": int((df_controles["statut"] != "OK").sum()),
        "valeurs vides conservees (non imputees)":
            int(df_reg["valeur"].isna().sum()),
    }
    parasites_total, parasites_onglets = balayer_entetes_parasitees(wb)
    # Une ligne d'anomalie par onglet concerne, coherente avec le balayage complet.
    for onglet_parasite, nombre_cellules in parasites_onglets:
        utilisees = PARASITES_UTILISEES.get(onglet_parasite, 0)
        precision = (f", dont {utilisees} en-tete(s) lue(s) par le nettoyage"
                     if utilisees else ", aucune lue par le nettoyage")
        anomalie(onglet_parasite, "en-tete d'annee contenant du texte parasite",
                 f"{nombre_cellules} cellule(s){precision}",
                 "annee extraite par expression reguliere, texte ignore et non recopie")
    noter("classeur", "balayage des en-tetes contenant du texte parasite",
          "documenter l'anomalie sur l'ensemble du classeur sans en recopier le texte",
          f"{parasites_total} cellule(s) sur {len(parasites_onglets)} onglet(s)")
    if VARIANTES_VUES:
        noter("tous onglets regionaux", "normalisation des variantes de noms de regions",
              "majuscules, accents, espaces et tirets variables selon les onglets",
              f"{len(VARIANTES_VUES)} ecriture(s) distincte(s) ramenee(s) au code officiel")

    ecrire_journal(resume, parasites_total, parasites_onglets)

    print(f"dgess_regional_long.csv     : {len(sortie_reg)} lignes")
    print(f"dgess_national_long.csv     : {len(sortie_nat)} lignes")
    print(f"dgess_totaux-nationaux.csv  : {len(df_tot)} lignes")
    print(f"controles_coherence.csv     : {len(df_controles)} controles, "
          f"{int((df_controles['statut'] != 'OK').sum())} hors tolerance")
    print("regions par onglet regional :")
    for onglet, nombre_regions in regions_par_onglet.items():
        marque = "OK" if nombre_regions == 13 else "ATTENTION"
        print(f"  {onglet:<12} {nombre_regions} regions  [{marque}]")


if __name__ == "__main__":
    main()
