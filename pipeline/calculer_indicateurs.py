"""Etape 03 - Calcul des indicateurs par region, annee et sexe.

Roles : Data Engineer + Data Analyst (Membre 2).

Lit  : data/02_nettoyage/dgess_regional_long.csv
       data/02_nettoyage/dgess_national_long.csv
Ecrit: data/03_transformation/indicateurs.csv            (contrat avec l'API)
       data/03_transformation/survie_cohortes_national.csv

Contrat impose par backend/app/charger.py :
    region_code,region_nom,annee,sexe,indicateur,valeur
    aucun doublon sur (region_code, annee, sexe, indicateur).

Script relancable :
    python pipeline/calculer_indicateurs.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
NETTOYAGE = RACINE / "data" / "02_nettoyage"
SORTIE = RACINE / "data" / "03_transformation"

COLONNES_CONTRAT = ["region_code", "region_nom", "annee", "sexe",
                    "indicateur", "valeur"]

# Indicateurs de base repris tels quels du nettoyage.
INDICATEURS_BASE = [
    "effectif_prescolaire", "effectif_primaire", "nouveaux_inscrits_cp1",
    "taux_brut_admission", "taux_brut_scolarisation", "taux_achevement",
    "taux_reussite_cep", "nombre_ecoles", "nombre_ecoles_public",
    "nombre_ecoles_prive",
]

# Niveaux du primaire, dans l'ordre du cycle (pour la survie des cohortes).
CYCLE_PRIMAIRE = ["CP1", "CP2", "CE1", "CE2", "CM1", "CM2"]


def charger_nettoyage() -> tuple[pd.DataFrame, pd.DataFrame]:
    regional = NETTOYAGE / "dgess_regional_long.csv"
    national = NETTOYAGE / "dgess_national_long.csv"
    for fichier in (regional, national):
        if not fichier.exists():
            raise SystemExit(f"Fichier absent : {fichier}\n"
                             "Lancer d'abord : python pipeline/nettoyer_dgess.py")
    return pd.read_csv(regional), pd.read_csv(national)


def table_valeurs(regional: pd.DataFrame) -> pd.DataFrame:
    """Table pivot (region_code, annee, sexe) x variable, pour les calculs."""
    return regional.pivot_table(index=["region_code", "annee", "sexe"],
                                columns="variable", values="valeur",
                                aggfunc="first")


def variation_annuelle(serie: pd.Series) -> pd.Series:
    """(valeur N - valeur N-1) / valeur N-1 x 100, par region et sexe."""
    return (serie.groupby(level=["region_code", "sexe"], group_keys=False)
            .apply(lambda s: s.sort_index(level="annee").pct_change() * 100))


def difference_annuelle(serie: pd.Series) -> pd.Series:
    """valeur N - valeur N-1 en points, par region et sexe."""
    return (serie.groupby(level=["region_code", "sexe"], group_keys=False)
            .apply(lambda s: s.sort_index(level="annee").diff()))


def recul_depuis_pic(serie: pd.Series) -> pd.Series:
    """(valeur N / maximum observe jusqu'a N - 1) x 100, par region et sexe.

    Negatif ou nul. Ne regarde que les annees <= N (maximum glissant), pour ne
    jamais utiliser une information future.

    Pourquoi cet indicateur : la variation annuelle fait baisser a tort le
    risque d'une region encore devastee. Une region qui a perdu la moitie de
    ses eleves en 2023 et en regagne 10 % en 2025 affiche une variation
    annuelle positive, alors qu'il lui manque toujours la moitie de ses eleves.
    Le recul depuis le pic mesure ce qui n'a pas ete reconstitue.
    """
    def calculer(valeurs: pd.Series) -> pd.Series:
        ordonnees = valeurs.sort_index(level="annee")
        pic_glissant = ordonnees.cummax()
        return (ordonnees / pic_glissant.where(pic_glissant != 0) - 1) * 100
    return (serie.groupby(level=["region_code", "sexe"], group_keys=False)
            .apply(calculer))


def ips(valeurs: pd.DataFrame, variable: str) -> pd.Series:
    """Indice de parite : taux des filles / taux des garcons, recalcule.

    Les onglets Feuil10-12 contiennent des formules Excel : ils ne sont pas lus.
    L'IPS est recalcule depuis les taux nettoyes (Feuil6, Feuil7, Feuil8).
    """
    taux = valeurs[variable].unstack("sexe")
    if "F" not in taux.columns or "G" not in taux.columns:
        return pd.Series(dtype="float64")
    rapport = taux["F"] / taux["G"].where(taux["G"] != 0)
    return rapport.dropna()


def ajouter(lignes: list[pd.DataFrame], serie: pd.Series, nom: str,
            sexe_force: str | None = None) -> None:
    """Ajoute une serie indexee (region_code, annee[, sexe]) au format long."""
    if serie.empty:
        return
    cadre = serie.rename("valeur").reset_index()
    if "sexe" not in cadre.columns:
        cadre["sexe"] = sexe_force or "T"
    elif sexe_force is not None:
        cadre["sexe"] = sexe_force
    cadre["indicateur"] = nom
    # Une valeur absente n'est jamais ecrite : pas de ligne du tout.
    cadre = cadre.dropna(subset=["valeur"])
    lignes.append(cadre[["region_code", "annee", "sexe", "indicateur", "valeur"]])


def calculer_survie(national: pd.DataFrame) -> pd.DataFrame:
    """Taux de survie apparent : CM2 de l'annee N+5 / CP1 de l'annee N.

    Seul proxy d'abandon par cohorte disponible (aucune donnee individuelle).
    Calcule au niveau national, par sexe, tous statuts confondus.
    """
    niveaux = national[(national["source_onglet"] == "Feuil4")
                       & (national["niveau"].isin(CYCLE_PRIMAIRE))]
    # Tous statuts confondus : on exclut les lignes de total de statut.
    niveaux = niveaux[~niveaux["statut"].isin(["TOTAL"])]
    effectifs = (niveaux.groupby(["niveau", "annee", "sexe"])["valeur"]
                 .sum(min_count=1).reset_index())
    cp1 = effectifs[effectifs["niveau"] == "CP1"].set_index(["annee", "sexe"])["valeur"]
    cm2 = effectifs[effectifs["niveau"] == "CM2"].set_index(["annee", "sexe"])["valeur"]

    lignes = []
    for (annee_cp1, sexe), effectif_cp1 in cp1.items():
        annee_cm2 = annee_cp1 + 5
        effectif_cm2 = cm2.get((annee_cm2, sexe))
        if effectif_cm2 is None or pd.isna(effectif_cp1) or effectif_cp1 == 0:
            continue
        lignes.append({
            "annee_cp1": int(annee_cp1),
            "annee_cm2": int(annee_cm2),
            "sexe": sexe,
            "effectif_cp1": float(effectif_cp1),
            "effectif_cm2": float(effectif_cm2),
            "taux_survie_apparent_pct": round(
                float(effectif_cm2) / float(effectif_cp1) * 100, 2),
        })
    return pd.DataFrame(lignes).sort_values(["annee_cp1", "sexe"])


def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    regional, national = charger_nettoyage()
    noms = (regional[["region_code", "region_nom"]]
            .drop_duplicates("region_code"))
    valeurs = table_valeurs(regional)

    lignes: list[pd.DataFrame] = []

    # --- 3.1 Indicateurs de base, tels quels ---
    base = regional[regional["variable"].isin(INDICATEURS_BASE)].copy()
    base = base.rename(columns={"variable": "indicateur"})
    lignes.append(base[["region_code", "annee", "sexe", "indicateur", "valeur"]])

    # --- 3.2 Indicateurs calcules ---
    # Variations d'effectif : T, puis G et F (decrochage differencie).
    ajouter(lignes, variation_annuelle(valeurs["effectif_primaire"].dropna()),
            "variation_effectif_primaire")

    # Nombre d'ecoles : sexe T uniquement.
    ecoles = valeurs["nombre_ecoles"].dropna()
    ecoles_t = ecoles[ecoles.index.get_level_values("sexe") == "T"]
    ajouter(lignes, variation_annuelle(ecoles_t), "variation_nombre_ecoles")

    # Eleves par ecole : effectif primaire (T) / nombre d'ecoles (T).
    effectif_t = valeurs["effectif_primaire"].xs("T", level="sexe")
    ecoles_total = valeurs["nombre_ecoles"].xs("T", level="sexe")
    eleves_par_ecole = (effectif_t / ecoles_total.where(ecoles_total != 0)).dropna()
    ajouter(lignes, eleves_par_ecole, "eleves_par_ecole", sexe_force="T")

    # Ecart entre admission et achevement, en points (T).
    tba_t = valeurs["taux_brut_admission"].xs("T", level="sexe")
    tap_t = valeurs["taux_achevement"].xs("T", level="sexe")
    ajouter(lignes, (tba_t - tap_t).dropna(), "ecart_tba_tap", sexe_force="T")

    # Variation du taux d'achevement, en points (T).
    tap = valeurs["taux_achevement"].dropna()
    tap_total = tap[tap.index.get_level_values("sexe") == "T"]
    ajouter(lignes, difference_annuelle(tap_total), "variation_taux_achevement")

    # Reculs depuis le pic observe (sexe T) : ce qui n'a pas ete reconstitue.
    effectif_t_serie = valeurs["effectif_primaire"].dropna()
    effectif_t_serie = effectif_t_serie[
        effectif_t_serie.index.get_level_values("sexe") == "T"]
    ajouter(lignes, recul_depuis_pic(effectif_t_serie),
            "recul_effectif_primaire_vs_pic")
    ajouter(lignes, recul_depuis_pic(ecoles_t), "recul_nombre_ecoles_vs_pic")

    # IPS recalcules (sexe T).
    ajouter(lignes, ips(valeurs, "taux_brut_admission"), "ips_tba", sexe_force="T")
    ajouter(lignes, ips(valeurs, "taux_brut_scolarisation"), "ips_tbs", sexe_force="T")
    ajouter(lignes, ips(valeurs, "taux_achevement"), "ips_tap", sexe_force="T")

    # --- Assemblage, contrat et controles ---
    indicateurs = pd.concat(lignes, ignore_index=True)
    indicateurs = indicateurs.merge(noms, on="region_code", how="left")
    indicateurs["annee"] = indicateurs["annee"].astype(int)
    indicateurs["valeur"] = indicateurs["valeur"].round(4)

    doublons = indicateurs.duplicated(
        subset=["region_code", "annee", "sexe", "indicateur"]).sum()
    if doublons:
        raise SystemExit(f"{doublons} doublon(s) sur "
                         "(region_code, annee, sexe, indicateur) : le chargement "
                         "de l'API echouerait.")
    if indicateurs["region_nom"].isna().any():
        raise SystemExit("region_nom manquant pour au moins une region.")
    if indicateurs["valeur"].isna().any():
        raise SystemExit("valeur vide ecrite : contraire a la regle "
                         "« pas de ligne si la valeur n'existe pas ».")

    indicateurs = (indicateurs[COLONNES_CONTRAT]
                   .sort_values(["indicateur", "region_code", "annee", "sexe"]))
    indicateurs.to_csv(SORTIE / "indicateurs.csv", index=False, encoding="utf-8")

    # --- 3.3 Contexte national : survie apparente des cohortes ---
    survie = calculer_survie(national)
    entete = ("# Taux de survie apparent du primaire, national, par sexe\n"
              "# Formule : taux_survie_apparent_pct = effectif CM2 de l'annee "
              "(N+5) / effectif CP1 de l'annee N x 100\n"
              "# Lecture : proportion apparente d'une cohorte entree au CP1 en "
              "annee N encore scolarisee au CM2 cinq ans plus tard.\n"
              "# Limite : indicateur apparent (ne suit pas les eleves un par un) ; "
              "il melange abandons, redoublements et migrations.\n"
              "# Source : DGESS/MENAPLN, onglet Feuil4 (effectifs nationaux par "
              "niveau, statut et sexe), 2016-2025.\n")
    chemin_survie = SORTIE / "survie_cohortes_national.csv"
    with chemin_survie.open("w", encoding="utf-8", newline="") as flux:
        flux.write(entete)
        survie.to_csv(flux, index=False)

    # --- Rapport console ---
    print(f"indicateurs.csv               : {len(indicateurs)} lignes, "
          f"{indicateurs['indicateur'].nunique()} indicateurs, "
          f"0 doublon")
    print(f"survie_cohortes_national.csv  : {len(survie)} lignes "
          f"({survie['annee_cp1'].min()}-{survie['annee_cp1'].max()} "
          f"-> {survie['annee_cm2'].min()}-{survie['annee_cm2'].max()})")
    print()
    recap = (indicateurs.groupby("indicateur")
             .agg(lignes=("valeur", "size"),
                  sexes=("sexe", lambda s: "/".join(sorted(s.unique()))),
                  annees=("annee", lambda s: f"{s.min()}-{s.max()}"),
                  minimum=("valeur", "min"),
                  mediane=("valeur", "median"),
                  maximum=("valeur", "max")))
    print(recap.to_string())


if __name__ == "__main__":
    main()
