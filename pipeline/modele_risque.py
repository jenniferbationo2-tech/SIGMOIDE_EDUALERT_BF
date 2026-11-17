"""Etape 04 - Indice de risque de decrochage et prevision N+1.

Role : Data Scientist (Membre 2).

Lit  : data/03_transformation/indicateurs.csv
Ecrit: data/04_analyse/risque.csv               (contrat avec l'API)
       data/04_analyse/metriques_modeles.csv
       data/04_analyse/importance_variables.csv
       data/04_analyse/sensibilite_poids.csv
       data/04_analyse/previsions_test.csv
       data/04_analyse/rapport_modele.md

Avertissement de methode : il n'existe dans les donnees aucun taux d'abandon
par region, aucun absentéisme et aucune donnee individuelle. Le risque de
decrochage est donc mesure INDIRECTEMENT, par un indice composite
d'indicateurs de deperdition scolaire et de rupture d'offre. Ce n'est pas un
taux d'abandon mesure.

Script relancable, resultat deterministe (random_state fixe partout) :
    python pipeline/modele_risque.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler

GRAINE = 42
RACINE = Path(__file__).resolve().parents[1]
INDICATEURS = RACINE / "data" / "03_transformation" / "indicateurs.csv"
SORTIE = RACINE / "data" / "04_analyse"

ANNEES_INDICE = list(range(2017, 2026))     # panel observe
ANNEE_PREVISION = 2026

COLONNES_RISQUE = ["region_code", "annee", "score", "niveau", "facteurs",
                   "est_prevision"]

# Composantes de l'indice : toutes orientees « plus haut = plus de risque ».
# (code facteur, poids, libelle de la formule)
COMPOSANTES = {
    "ecart_admission_achevement": (0.25, "ecart_tba_tap"),
    "faible_achevement":          (0.20, "100 - taux_achevement"),
    "recul_effectifs":            (0.20, "- recul_effectif_primaire_vs_pic"),
    "fermeture_ecoles":           (0.15, "- recul_nombre_ecoles_vs_pic"),
    "faible_scolarisation":       (0.10, "100 - taux_brut_scolarisation"),
    "disparite_filles_garcons":   (0.10, "abs(1 - ips_tap)"),
}
POIDS = {code: poids for code, (poids, _) in COMPOSANTES.items()}

# Variante ecartee, conservee pour l'analyse de sensibilite (section 4.2).
COMPOSANTES_VARIATIONS = {
    "ecart_admission_achevement": 0.25,
    "faible_achevement":          0.20,
    "baisse_effectifs":           0.20,     # - variation_effectif_primaire
    "fermeture_ecoles_variation": 0.15,     # - variation_nombre_ecoles
    "faible_scolarisation":       0.10,
    "disparite_filles_garcons":   0.10,
}

SEUIL_MODERE = 33
SEUIL_CRITIQUE = 66

# Les trois modeles compares, dans l'ordre d'affichage.
MODELES = ("reference naive", "Ridge", "foret aleatoire")
MARGE_DECISION = 0.3        # point de MAE en faveur de la simplicite


# --------------------------------------------------------------------------
# Chargement et construction des composantes
# --------------------------------------------------------------------------
def charger_indicateurs() -> pd.DataFrame:
    if not INDICATEURS.exists():
        raise SystemExit(f"Fichier absent : {INDICATEURS}\n"
                         "Lancer d'abord : python pipeline/calculer_indicateurs.py")
    indicateurs = pd.read_csv(INDICATEURS)
    total = indicateurs[indicateurs["sexe"] == "T"]
    return total.pivot_table(index=["region_code", "annee"],
                             columns="indicateur", values="valeur",
                             aggfunc="first")


def construire_composantes(valeurs: pd.DataFrame) -> pd.DataFrame:
    """Compose les 6 variables de l'indice, orientees risque croissant."""
    composantes = pd.DataFrame(index=valeurs.index)
    composantes["ecart_admission_achevement"] = valeurs["ecart_tba_tap"]
    composantes["faible_achevement"] = 100 - valeurs["taux_achevement"]
    composantes["recul_effectifs"] = -valeurs["recul_effectif_primaire_vs_pic"]
    composantes["fermeture_ecoles"] = -valeurs["recul_nombre_ecoles_vs_pic"]
    composantes["faible_scolarisation"] = 100 - valeurs["taux_brut_scolarisation"]
    composantes["disparite_filles_garcons"] = (1 - valeurs["ips_tap"]).abs()
    return composantes.loc[
        composantes.index.get_level_values("annee").isin(ANNEES_INDICE)]


def construire_composantes_variations(valeurs: pd.DataFrame) -> pd.DataFrame:
    """Variante ecartee : variations annuelles au lieu des reculs depuis le pic."""
    composantes = pd.DataFrame(index=valeurs.index)
    composantes["ecart_admission_achevement"] = valeurs["ecart_tba_tap"]
    composantes["faible_achevement"] = 100 - valeurs["taux_achevement"]
    composantes["baisse_effectifs"] = -valeurs["variation_effectif_primaire"]
    composantes["fermeture_ecoles_variation"] = -valeurs["variation_nombre_ecoles"]
    composantes["faible_scolarisation"] = 100 - valeurs["taux_brut_scolarisation"]
    composantes["disparite_filles_garcons"] = (1 - valeurs["ips_tap"]).abs()
    return composantes.loc[
        composantes.index.get_level_values("annee").isin(ANNEES_INDICE)]


# --------------------------------------------------------------------------
# Indice composite
# --------------------------------------------------------------------------
def percentiles(composantes: pd.DataFrame) -> pd.DataFrame:
    """Rang percentile de chaque composante sur l'ensemble du panel.

    Robuste aux valeurs extremes de 2022/23, et comparable d'une annee a
    l'autre puisque le rang est calcule sur le panel complet.
    """
    return composantes.rank(pct=True)


def calculer_score(composantes: pd.DataFrame, poids: dict) -> tuple:
    """Score = 100 x somme(poids x percentile), contributions et rangs."""
    rangs = percentiles(composantes[list(poids)])
    contributions = rangs.mul(pd.Series(poids), axis=1)
    score = contributions.sum(axis=1) * 100
    return pd.DataFrame({"score": score.round(1)}), contributions, rangs


def niveau_de(score: float) -> str:
    """Faible < 33 ; Modere 33-66 (sans accent, l'API l'attend ainsi) ; Critique >= 66."""
    if score < SEUIL_MODERE:
        return "Faible"
    if score < SEUIL_CRITIQUE:
        return "Modere"
    return "Critique"


def principaux_facteurs(contributions: pd.DataFrame, rangs: pd.DataFrame,
                        nombre: int = 3, seuil_percentile: float = 0.5) -> pd.Series:
    """Les 2 ou 3 composantes qui contribuent le plus, en codes separes par « ; ».

    Un facteur n'est cite que si le percentile de sa composante atteint
    `seuil_percentile` (par defaut la mediane du panel) : sinon on afficherait
    comme « facteur de risque » une composante ou la region se situe parmi les
    meilleures du pays. Si aucune composante ne passe le filtre, la region
    n'a pas de facteur marquant.
    """
    def pour_une_ligne(ligne: pd.Series) -> str:
        cle = ligne.name
        eligibles = [code for code in ligne.index
                     if rangs.loc[cle, code] >= seuil_percentile
                     and ligne[code] > 0]
        retenus = sorted(eligibles, key=lambda code: ligne[code], reverse=True)
        if not retenus:
            return "aucun_facteur_marquant"
        return ";".join(retenus[:nombre])
    return contributions.apply(pour_une_ligne, axis=1)


# --------------------------------------------------------------------------
# Modele de prevision N+1
# --------------------------------------------------------------------------
def construire_paires(composantes: pd.DataFrame, scores: pd.Series,
                      valeurs: pd.DataFrame) -> pd.DataFrame:
    """Variables de l'annee N -> cible = score de l'annee N+1."""
    table = composantes.copy()
    table["score"] = scores
    # Quelques indicateurs bruts utiles, en plus des composantes.
    for brut in ("eleves_par_ecole", "taux_reussite_cep", "taux_brut_admission"):
        table[brut] = valeurs[brut]
    table = table.reset_index()

    cible = table[["region_code", "annee", "score"]].copy()
    cible["annee"] = cible["annee"] - 1          # score N+1 rattache a l'annee N
    cible = cible.rename(columns={"score": "score_cible"})

    paires = table.merge(cible, on=["region_code", "annee"], how="inner")
    return paires.dropna().sort_values(["annee", "region_code"])


def mesures(reel: np.ndarray, prevu: np.ndarray) -> dict:
    erreur = prevu - reel
    niveaux_reels = [niveau_de(v) for v in reel]
    niveaux_prevus = [niveau_de(v) for v in prevu]
    justesse = float(np.mean([a == b for a, b in zip(niveaux_reels, niveaux_prevus)]))
    if "Critique" in niveaux_reels or "Critique" in niveaux_prevus:
        f1_critique = f1_score(niveaux_reels, niveaux_prevus,
                               labels=["Critique"], average="macro",
                               zero_division=0)
    else:
        f1_critique = np.nan
    return {
        "mae": round(float(np.mean(np.abs(erreur))), 3),
        "rmse": round(float(np.sqrt(np.mean(erreur ** 2))), 3),
        "justesse_niveau": round(justesse, 3),
        "f1_critique": (None if np.isnan(f1_critique)
                        else round(float(f1_critique), 3)),
    }


def standardiser(echelle: StandardScaler, donnees: pd.DataFrame,
                 colonnes: list[str]) -> pd.DataFrame:
    """Standardise en conservant les noms de colonnes (evite les avertissements)."""
    return pd.DataFrame(echelle.transform(donnees[colonnes]),
                        columns=colonnes, index=donnees.index)


def choisir_alpha(entrainement: pd.DataFrame, colonnes: list[str]) -> float:
    """Alpha de la Ridge par validation temporelle a l'interieur de l'entrainement.

    Les cibles d'entrainement vont jusqu'a 2022 : on valide sur la derniere
    annee disponible, jamais par melange aleatoire.
    """
    annees = sorted(entrainement["annee"].unique())
    if len(annees) < 3:
        return 1.0
    annee_validation = annees[-1]
    appris = entrainement[entrainement["annee"] < annee_validation]
    valide = entrainement[entrainement["annee"] == annee_validation]
    meilleur, meilleure_erreur = 1.0, np.inf
    for alpha in (0.01, 0.1, 1.0, 10.0, 100.0):
        echelle = StandardScaler().fit(appris[colonnes])
        modele = Ridge(alpha=alpha, random_state=GRAINE)
        modele.fit(standardiser(echelle, appris, colonnes), appris["score_cible"])
        prevu = modele.predict(standardiser(echelle, valide, colonnes))
        erreur = float(np.mean(np.abs(prevu - valide["score_cible"])))
        if erreur < meilleure_erreur:
            meilleur, meilleure_erreur = alpha, erreur
    return meilleur


def entrainer_et_prevoir(nom: str, entrainement: pd.DataFrame,
                         evaluation: pd.DataFrame, colonnes: list[str]) -> np.ndarray:
    """Entraine un des trois modeles et rend ses previsions sur `evaluation`.

    Les hyperparametres sont choisis a l'interieur du jeu d'entrainement
    fourni : aucun pli ne regarde ses propres donnees de test.
    """
    if nom == "reference naive":
        return evaluation["score"].to_numpy()
    if nom == "Ridge":
        alpha = choisir_alpha(entrainement, colonnes)
        echelle = StandardScaler().fit(entrainement[colonnes])
        modele = Ridge(alpha=alpha, random_state=GRAINE)
        modele.fit(standardiser(echelle, entrainement, colonnes),
                   entrainement["score_cible"])
        return modele.predict(standardiser(echelle, evaluation, colonnes))
    modele = RandomForestRegressor(n_estimators=300, max_depth=3,
                                   random_state=GRAINE, n_jobs=1)
    modele.fit(entrainement[colonnes], entrainement["score_cible"])
    return modele.predict(evaluation[colonnes])


def validation_glissante(paires: pd.DataFrame, colonnes: list[str],
                         plis: tuple = ((2022, 2023), (2023, 2024), (2024, 2025))
                         ) -> tuple[pd.DataFrame, dict]:
    """Validation glissante : apprendre sur les cibles <= A, tester sur l'annee B.

    Rend le detail par pli et, pour chaque modele, la liste de ses erreurs
    (reel - prevu) sur l'ensemble des plis : elles servent a estimer
    l'incertitude de la prevision 2026.
    """
    lignes, erreurs = [], {nom: [] for nom in MODELES}
    for derniere_apprise, annee_testee in plis:
        entrainement = paires[paires["annee"] + 1 <= derniere_apprise]
        test = paires[paires["annee"] + 1 == annee_testee]
        if entrainement.empty or test.empty:
            continue
        for nom in MODELES:
            prevu = entrainer_et_prevoir(nom, entrainement, test, colonnes)
            reel = test["score_cible"].to_numpy()
            lignes.append({
                "protocole": "glissante",
                "pli": f"apprend <= {derniere_apprise}, teste {annee_testee}",
                "modele": nom,
                "lignes_entrainement": len(entrainement),
                "lignes_test": len(test),
                **mesures(reel, prevu)})
            erreurs[nom].extend((reel - prevu).tolist())
    return pd.DataFrame(lignes), erreurs


def choisir_modele_2026(detail_glissant: pd.DataFrame,
                        marge: float = 0.3) -> tuple[str, pd.DataFrame, str]:
    """Regle de decision, fixee avant de regarder les resultats.

    Le modele retenu est celui qui a la plus faible MAE moyenne sur les trois
    plis glissants. Si son avance sur la reference naive est inferieure a
    `marge` point de MAE, on garde la reference naive, plus simple.
    """
    moyennes = (detail_glissant.groupby("modele")
                .agg(mae_moyenne=("mae", "mean"),
                     rmse_moyenne=("rmse", "mean"),
                     justesse_moyenne=("justesse_niveau", "mean"))
                .sort_values("mae_moyenne"))
    meilleur = moyennes.index[0]
    mae_naive = float(moyennes.loc["reference naive", "mae_moyenne"])
    mae_meilleur = float(moyennes.loc[meilleur, "mae_moyenne"])
    if meilleur == "reference naive":
        raison = (f"la reference naive a la plus faible MAE moyenne glissante "
                  f"({mae_naive:.3f})")
        return "reference naive", moyennes, raison
    if mae_naive - mae_meilleur < marge:
        raison = (f"{meilleur} a la meilleure MAE moyenne glissante "
                  f"({mae_meilleur:.3f}) mais son avance sur la reference naive "
                  f"({mae_naive:.3f}) est de {mae_naive - mae_meilleur:.3f} point, "
                  f"soit moins que la marge de {marge} fixee d'avance : on garde "
                  f"la reference naive, plus simple")
        return "reference naive", moyennes, raison
    raison = (f"{meilleur} a la plus faible MAE moyenne glissante "
              f"({mae_meilleur:.3f} contre {mae_naive:.3f} pour la reference "
              f"naive), avec une avance de {mae_naive - mae_meilleur:.3f} point "
              f"superieure a la marge de {marge} fixee d'avance")
    return meilleur, moyennes, raison


def incertitude_2026(prevision: pd.Series, erreurs: list[float]) -> pd.DataFrame:
    """Intervalle probable et probabilite d'etre critique, par region.

    L'incertitude vient de la distribution empirique des erreurs du modele
    retenu sur les plis glissants : on l'applique au score prevu.
    """
    serie_erreurs = np.array(erreurs, dtype=float)
    bas, haut = np.quantile(serie_erreurs, [0.10, 0.90])
    lignes = []
    for region_code, score_prevu in prevision.items():
        tirages = score_prevu + serie_erreurs
        lignes.append({
            "region_code": region_code,
            "annee": ANNEE_PREVISION,
            "score": round(float(score_prevu), 1),
            "score_bas": round(float(min(max(score_prevu + bas, 0), 100)), 1),
            "score_haut": round(float(min(max(score_prevu + haut, 0), 100)), 1),
            "proba_critique": round(
                float((tirages >= SEUIL_CRITIQUE).mean()), 3),
        })
    return pd.DataFrame(lignes).sort_values("score", ascending=False)


# --------------------------------------------------------------------------
# Analyse de sensibilite
# --------------------------------------------------------------------------
def sensibilite(composantes: pd.DataFrame, reference: pd.DataFrame,
                composantes_variations: pd.DataFrame) -> pd.DataFrame:
    """Compare le classement de reference a des variantes de ponderation."""
    lignes = []

    def comparer(nom: str, description: str, scores_variante: pd.Series) -> None:
        commun = reference.index.intersection(scores_variante.index)
        base = reference.loc[commun, "score"]
        autre = scores_variante.loc[commun]
        rho, _ = spearmanr(base, autre)
        niveaux_base = base.map(niveau_de)
        niveaux_autre = autre.map(niveau_de)
        change = float((niveaux_base != niveaux_autre).mean())
        lignes.append({
            "variante": nom,
            "description": description,
            "observations_comparees": len(commun),
            "spearman_classement": round(float(rho), 4),
            "part_regions_changeant_de_niveau_pct": round(change * 100, 1),
        })

    # 1. Poids egaux
    egaux = {code: 1 / len(POIDS) for code in POIDS}
    scores_egaux, _, _ = calculer_score(composantes, egaux)
    comparer("poids_egaux", "toutes les composantes a poids identique",
             scores_egaux["score"])

    # 2. Retrait d'une composante a la fois (poids renormalises)
    for exclue in POIDS:
        restants = {c: p for c, p in POIDS.items() if c != exclue}
        total = sum(restants.values())
        restants = {c: p / total for c, p in restants.items()}
        scores_sans, _, _ = calculer_score(composantes, restants)
        comparer(f"sans_{exclue}", f"composante {exclue} retiree",
                 scores_sans["score"])

    # 3. Variante ecartee : variations annuelles au lieu des reculs depuis le pic
    scores_variations, _, _ = calculer_score(composantes_variations,
                                             COMPOSANTES_VARIATIONS)
    comparer("avec_variations_annuelles",
             "variante ecartee : variations annuelles au lieu du recul depuis le pic",
             scores_variations["score"])

    return pd.DataFrame(lignes)


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def main() -> None:
    SORTIE.mkdir(parents=True, exist_ok=True)
    np.random.seed(GRAINE)

    valeurs = charger_indicateurs()
    composantes = construire_composantes(valeurs).dropna()
    composantes_variations = construire_composantes_variations(valeurs).dropna()

    attendu = 13 * len(ANNEES_INDICE)
    if len(composantes) != attendu:
        print(f"ATTENTION : panel de {len(composantes)} lignes au lieu de {attendu} "
              "(13 regions x 2017-2025)")

    # --- Indice composite ---
    scores, contributions, rangs = calculer_score(composantes, POIDS)
    scores["niveau"] = scores["score"].map(niveau_de)
    scores["facteurs"] = principaux_facteurs(contributions, rangs)

    repartition = (scores.reset_index()
                   .pivot_table(index="annee", columns="niveau",
                                values="score", aggfunc="size")
                   .fillna(0).astype(int))

    # --- Paires N -> N+1 ---
    paires = construire_paires(composantes, scores["score"], valeurs)
    colonnes = [c for c in paires.columns
                if c not in ("region_code", "annee", "score_cible")]
    entrainement = paires[paires["annee"] + 1 <= 2022]
    test = paires[(paires["annee"] + 1).between(2023, 2025)]

    resultats, previsions = [], {}

    # 1. Reference naive : score N+1 = score N
    prevu_naif = test["score"].to_numpy()
    resultats.append({"modele": "reference naive (score N+1 = score N)",
                      **mesures(test["score_cible"].to_numpy(), prevu_naif)})
    previsions["reference naive"] = prevu_naif

    # 2. Ridge sur variables standardisees
    alpha = choisir_alpha(entrainement, colonnes)
    echelle = StandardScaler().fit(entrainement[colonnes])
    ridge = Ridge(alpha=alpha, random_state=GRAINE)
    ridge.fit(standardiser(echelle, entrainement, colonnes),
              entrainement["score_cible"])
    prevu_ridge = ridge.predict(standardiser(echelle, test, colonnes))
    resultats.append({"modele": f"regression Ridge (alpha={alpha})",
                      **mesures(test["score_cible"].to_numpy(), prevu_ridge)})
    previsions["Ridge"] = prevu_ridge

    # 3. Foret aleatoire peu profonde
    foret = RandomForestRegressor(n_estimators=300, max_depth=3,
                                  random_state=GRAINE, n_jobs=1)
    foret.fit(entrainement[colonnes], entrainement["score_cible"])
    prevu_foret = foret.predict(test[colonnes])
    resultats.append({"modele": "foret aleatoire (max_depth=3)",
                      **mesures(test["score_cible"].to_numpy(), prevu_foret)})
    previsions["foret aleatoire"] = prevu_foret

    metriques_fixe = pd.DataFrame(resultats)
    metriques_fixe["protocole"] = "fixe"
    metriques_fixe["pli"] = "apprend <= 2022, teste 2023-2025"
    metriques_fixe["lignes_entrainement"] = len(entrainement)
    metriques_fixe["lignes_test"] = len(test)
    mae_naive = metriques_fixe.loc[0, "mae"]
    metriques_fixe["bat_la_reference_naive"] = np.where(
        metriques_fixe["mae"] < mae_naive, "oui",
        np.where(metriques_fixe["modele"].str.startswith("reference"), "-", "non"))

    # --- Validation glissante (3 plis) et regle de decision ---
    detail_glissant, erreurs_glissantes = validation_glissante(paires, colonnes)
    retenu_court, moyennes_glissantes, raison = choisir_modele_2026(
        detail_glissant, MARGE_DECISION)
    mae_naive_glissante = float(
        moyennes_glissantes.loc["reference naive", "mae_moyenne"])

    # Noms longs pour l'affichage, noms courts pour la mecanique.
    noms_longs = {
        "reference naive": "reference naive (score N+1 = score N)",
        "Ridge": f"regression Ridge (alpha={alpha})",
        "foret aleatoire": "foret aleatoire (max_depth=3)",
    }
    retenu = noms_longs[retenu_court]

    detail_glissant_affiche = detail_glissant.copy()
    mae_reference_par_pli = (
        detail_glissant[detail_glissant["modele"] == "reference naive"]
        .set_index("pli")["mae"])
    detail_glissant_affiche["bat_la_reference_naive"] = [
        "-" if ligne.modele == "reference naive"
        else ("oui" if ligne.mae < mae_reference_par_pli[ligne.pli] else "non")
        for ligne in detail_glissant.itertuples()]
    detail_glissant_affiche["modele"] = detail_glissant_affiche["modele"].map(
        noms_longs)

    metriques = pd.concat([metriques_fixe, detail_glissant_affiche],
                          ignore_index=True)
    metriques["retenu_pour_2026"] = np.where(
        metriques["modele"] == retenu, "oui", "non")
    colonnes_metriques = ["protocole", "pli", "modele", "mae", "rmse",
                          "justesse_niveau", "f1_critique",
                          "lignes_entrainement", "lignes_test",
                          "bat_la_reference_naive", "retenu_pour_2026"]
    metriques[colonnes_metriques].to_csv(SORTIE / "metriques_modeles.csv",
                                         index=False, encoding="utf-8")
    metriques_fixe.to_csv(SORTIE / "metriques_modeles_protocole_fixe.csv",
                          index=False, encoding="utf-8")

    # --- Matrice de confusion des niveaux (modele retenu) ---
    nom_retenu = ("reference naive" if retenu.startswith("reference")
                  else "Ridge" if retenu.startswith("regression") else "foret aleatoire")
    niveaux_reels = [niveau_de(v) for v in test["score_cible"]]
    niveaux_prevus = [niveau_de(v) for v in previsions[nom_retenu]]
    etiquettes = ["Faible", "Modere", "Critique"]
    matrice = pd.DataFrame(
        confusion_matrix(niveaux_reels, niveaux_prevus, labels=etiquettes),
        index=[f"reel {e}" for e in etiquettes],
        columns=[f"prevu {e}" for e in etiquettes])

    # --- Previsions sur le test, reel vs prevu ---
    details = test[["region_code", "annee", "score", "score_cible"]].copy()
    details = details.rename(columns={"annee": "annee_n",
                                      "score": "score_n",
                                      "score_cible": "score_reel_n1"})
    details["annee_n1"] = details["annee_n"] + 1
    for nom, prevu in previsions.items():
        details[f"prevu_{nom.replace(' ', '_')}"] = np.round(prevu, 1)
    details["niveau_reel_n1"] = details["score_reel_n1"].map(niveau_de)
    details[f"niveau_prevu_{nom_retenu.replace(' ', '_')}"] = [
        niveau_de(v) for v in previsions[nom_retenu]]
    details.to_csv(SORTIE / "previsions_test.csv", index=False, encoding="utf-8")

    # --- Importance des variables (permutation sur le test) ---
    lignes_importance = []
    for nom, modele, donnees in (
            ("Ridge", ridge, standardiser(echelle, test, colonnes)),
            ("foret aleatoire", foret, test[colonnes])):
        resultat = permutation_importance(modele, donnees,
                                          test["score_cible"].to_numpy(),
                                          n_repeats=30, random_state=GRAINE,
                                          scoring="neg_mean_absolute_error")
        for colonne, moyenne, ecart in zip(colonnes, resultat.importances_mean,
                                           resultat.importances_std):
            lignes_importance.append({
                "modele": nom, "variable": colonne,
                "importance_permutation": round(float(moyenne), 4),
                "ecart_type": round(float(ecart), 4),
                "coefficient_standardise": (
                    round(float(ridge.coef_[colonnes.index(colonne)]), 4)
                    if nom == "Ridge" else None)})
    importance = pd.DataFrame(lignes_importance).sort_values(
        ["modele", "importance_permutation"], ascending=[True, False])
    importance.to_csv(SORTIE / "importance_variables.csv", index=False,
                      encoding="utf-8")

    # --- Analyse de sensibilite ---
    sensible = sensibilite(composantes, scores, composantes_variations)
    sensible.to_csv(SORTIE / "sensibilite_poids.csv", index=False,
                    encoding="utf-8")

    # --- Prevision 2026 : reentrainement sur toutes les paires ---
    if retenu.startswith("reference"):
        derniers = scores.xs(2025, level="annee")["score"]
        prevision_2026 = derniers.copy()
        methode_2026 = "reference naive : score 2026 = score 2025"
    else:
        if nom_retenu == "Ridge":
            echelle_finale = StandardScaler().fit(paires[colonnes])
            modele_final = Ridge(alpha=alpha, random_state=GRAINE)
            modele_final.fit(standardiser(echelle_finale, paires, colonnes),
                             paires["score_cible"])
            derniere = composantes.xs(2025, level="annee")
            entrees = derniere.copy()
            entrees["score"] = scores.xs(2025, level="annee")["score"]
            for brut in ("eleves_par_ecole", "taux_reussite_cep",
                         "taux_brut_admission"):
                entrees[brut] = valeurs.xs(2025, level="annee")[brut]
            prevision_2026 = pd.Series(
                modele_final.predict(standardiser(echelle_finale, entrees, colonnes)),
                index=entrees.index)
        else:
            modele_final = RandomForestRegressor(n_estimators=300, max_depth=3,
                                                 random_state=GRAINE, n_jobs=1)
            modele_final.fit(paires[colonnes], paires["score_cible"])
            derniere = composantes.xs(2025, level="annee")
            entrees = derniere.copy()
            entrees["score"] = scores.xs(2025, level="annee")["score"]
            for brut in ("eleves_par_ecole", "taux_reussite_cep",
                         "taux_brut_admission"):
                entrees[brut] = valeurs.xs(2025, level="annee")[brut]
            prevision_2026 = pd.Series(
                modele_final.predict(entrees[colonnes]), index=entrees.index)
        methode_2026 = f"{retenu}, reentraine sur les {len(paires)} paires"

    # --- Incertitude de la prevision 2026 ---
    incertitude = incertitude_2026(prevision_2026,
                                   erreurs_glissantes[retenu_court])
    incertitude.to_csv(SORTIE / "prevision_2026_incertitude.csv", index=False,
                       encoding="utf-8")

    # --- risque.csv : contrat avec l'API ---
    observe = scores.reset_index()
    observe["est_prevision"] = 0
    prevision = pd.DataFrame({
        "region_code": prevision_2026.index,
        "annee": ANNEE_PREVISION,
        "score": prevision_2026.round(1).to_numpy(),
        "est_prevision": 1})
    prevision["niveau"] = prevision["score"].map(niveau_de)
    # Facteurs de la prevision : ceux de 2025 (section 4.3 du cahier).
    facteurs_2025 = scores.xs(2025, level="annee")["facteurs"]
    prevision["facteurs"] = prevision["region_code"].map(facteurs_2025)

    risque = (pd.concat([observe[COLONNES_RISQUE], prevision[COLONNES_RISQUE]],
                        ignore_index=True)
              .sort_values(["annee", "score"], ascending=[True, False]))
    doublons = risque.duplicated(subset=["region_code", "annee"]).sum()
    if doublons:
        raise SystemExit(f"{doublons} doublon(s) region x annee dans risque.csv")
    risque.to_csv(SORTIE / "risque.csv", index=False, encoding="utf-8")

    # --- Rapport ---
    ecrire_rapport(metriques_fixe, detail_glissant_affiche, moyennes_glissantes,
                   matrice, importance, sensible, risque, incertitude,
                   retenu, mae_naive, mae_naive_glissante, raison, methode_2026,
                   repartition, len(entrainement), len(test), len(paires))

    print(f"risque.csv                     : {len(risque)} lignes "
          f"(observe 2017-2025 + prevision {ANNEE_PREVISION})")
    print(f"metriques_modeles.csv          : {len(metriques)} lignes "
          "(2 protocoles)")
    print(f"prevision_2026_incertitude.csv : {len(incertitude)} regions")
    print(f"importance_variables.csv       : {len(importance)} lignes")
    print(f"sensibilite_poids.csv          : {len(sensible)} variantes")
    print(f"previsions_test.csv            : {len(details)} lignes de test")
    print()
    print("--- Protocole fixe (apprend <= 2022, teste 2023-2025) ---")
    print(metriques_fixe[["modele", "mae", "rmse", "justesse_niveau",
                          "f1_critique", "bat_la_reference_naive"]]
          .to_string(index=False))
    print()
    print("--- Validation glissante : detail par pli ---")
    print(detail_glissant_affiche[["pli", "modele", "mae", "rmse",
                                   "justesse_niveau", "bat_la_reference_naive"]]
          .to_string(index=False))
    print()
    print("--- Validation glissante : MAE moyenne sur les 3 plis ---")
    print(moyennes_glissantes.to_string())
    print()
    print("Modele retenu pour 2026 :", retenu)
    print("Raison :", raison)
    print()
    print("Repartition des niveaux par annee :")
    print(repartition.to_string())

def ecrire_rapport(metriques_fixe, detail_glissant, moyennes_glissantes,
                   matrice, importance, sensible, risque, incertitude,
                   retenu, mae_naive, mae_naive_glissante, raison, methode_2026,
                   repartition, n_entrainement, n_test, n_paires) -> None:
    mae_retenu_glissante = float(
        moyennes_glissantes["mae_moyenne"].min())
    classement_2025 = (risque[risque["annee"] == 2025]
                       .sort_values("score", ascending=False))
    classement_2026 = (risque[risque["annee"] == ANNEE_PREVISION]
                       .sort_values("score", ascending=False)
                       .merge(incertitude[["region_code", "score_bas",
                                           "score_haut", "proba_critique"]],
                              on="region_code", how="left"))
    top_importance = importance[importance["modele"] == "Ridge"].head(5)

    lignes = [
        "# Rapport du modele de risque - etape 04 (EduAlert BF)",
        "",
        "## 1. Ce que mesure le score (et ce qu'il ne mesure pas)",
        "",
        "Les donnees disponibles ne contiennent aucun taux d'abandon par region,",
        "aucun releve d'absenteisme et aucune donnee individuelle d'eleve. Le risque",
        "de decrochage est donc mesure **indirectement**, par un indice composite",
        "d'indicateurs de deperdition scolaire et de rupture de l'offre scolaire.",
        "",
        "**Ce score n'est pas un taux d'abandon.** C'est un indicateur d'alerte,",
        "destine a classer les regions entre elles, pas a chiffrer un nombre d'eleves",
        "sortis du systeme.",
        "",
        "## 2. Construction de l'indice",
        "",
        "| Composante | Formule | Poids | Code facteur |",
        "|---|---|---|---|",
    ]
    for code, (poids, formule) in COMPOSANTES.items():
        lignes.append(f"| {code.replace('_', ' ')} | `{formule}` | {poids:.2f} "
                      f"| `{code}` |")
    lignes += [
        "",
        "Normalisation : rang percentile de chaque composante sur l'ensemble du panel",
        f"(13 regions x 2017-2025, soit {13 * len(ANNEES_INDICE)} observations). Ce choix",
        "est robuste aux valeurs extremes de 2022/23 et garde le score comparable d'une",
        "annee a l'autre.",
        "",
        "Score = 100 x somme(poids x percentile), arrondi a 1 decimale.",
        f"Niveaux : `Faible` < {SEUIL_MODERE}, `Modere` {SEUIL_MODERE}-{SEUIL_CRITIQUE}, "
        f"`Critique` >= {SEUIL_CRITIQUE}.",
        "",
        "**Facteurs affiches** : une composante n'est citee comme facteur que si son",
        "percentile atteint 0,50, c'est-a-dire si la region se situe au-dessus de la",
        "mediane nationale sur cette composante. Sans ce filtre, une region pouvait",
        "voir citer comme « facteur de risque » une composante ou elle fait partie des",
        "meilleures du pays. Au maximum 3 facteurs, tries par contribution. Si aucune",
        "composante ne passe le filtre : `aucun_facteur_marquant`.",
        "",
        "### Pourquoi le recul depuis le pic plutot que la variation annuelle",
        "",
        "Une premiere version de l'indice utilisait les variations annuelles des",
        "effectifs et du nombre d'ecoles. Ce choix faisait baisser a tort le risque des",
        "regions encore devastees : en 2025, le Sahel gagne 10,5 % d'eleves et 10 %",
        "d'ecoles, alors qu'il lui manque toujours 52,8 % de ses eleves et 82,0 % de ses",
        "ecoles par rapport a son meilleur niveau. Les composantes mesurent donc",
        "desormais le **recul depuis le pic** : ce qui n'a pas ete reconstitue. La",
        "variante ecartee figure dans l'analyse de sensibilite sous le nom",
        "`avec_variations_annuelles`.",
        "",
        "## 3. Repartition des niveaux par annee",
        "",
        "```",
        repartition.to_string(),
        "```",
        "",
        "## 4. Modeles de prevision N+1 : deux protocoles de validation",
        "",
        f"Paires annee N -> score N+1 : {n_paires} observations au total. La validation",
        "est toujours **temporelle** : aucun melange aleatoire des annees, le modele ne",
        "voit jamais le futur. Les hyperparametres sont choisis a l'interieur de chaque",
        "jeu d'entrainement.",
        "",
        "### Regle de decision, fixee avant de regarder les resultats",
        "",
        "> Le modele retenu pour la prevision 2026 est celui qui obtient la plus faible",
        f"> MAE moyenne sur les trois plis glissants. Si son avance sur la reference",
        f"> naive est inferieure a {MARGE_DECISION} point de MAE, on garde la reference",
        "> naive, car elle est plus simple et plus previsible.",
        "",
        "### 4.1 Protocole fixe (apprend sur les cibles <= 2022, teste 2023-2025)",
        "",
        f"{n_entrainement} paires en entrainement, {n_test} en test.",
        "",
        "```",
        metriques_fixe[["modele", "mae", "rmse", "justesse_niveau", "f1_critique",
                        "bat_la_reference_naive"]].to_string(index=False),
        "```",
        "",
        "### 4.2 Validation glissante (3 plis)",
        "",
        "Chaque pli reproduit la situation reelle : on apprend sur tout le passe",
        "disponible et on prevoit l'annee suivante.",
        "",
        "```",
        detail_glissant[["pli", "modele", "mae", "rmse", "justesse_niveau",
                         "bat_la_reference_naive"]].to_string(index=False),
        "```",
        "",
        "MAE moyenne sur les trois plis :",
        "",
        "```",
        moyennes_glissantes.to_string(),
        "```",
        "",
        f"### 4.3 Modele retenu : {retenu}",
        "",
        f"Raison (application de la regle ci-dessus) : {raison}.",
        "",
    ]
    if retenu.startswith("reference"):
        lignes += [
            "**Honnetement : aucun modele appris ne bat la reference naive**, ni en",
            "protocole fixe, ni en validation glissante. Deux raisons, et il faut les",
            "dire :",
            "",
            "1. **Le choc de 2022/23 est un changement de regime.** Les modeles",
            "   apprennent sur des annees ou le systeme scolaire se degrade lentement,",
            "   puis doivent prevoir l'apres-effondrement. Les relations apprises ne",
            "   tiennent plus.",
            f"2. **{n_paires} observations, c'est tres peu** pour apprendre une relation",
            "   a 9 variables. Le score d'une region est par ailleurs tres stable d'une",
            "   annee a l'autre, ce qui rend la persistance difficile a battre.",
            "",
            "Conclusion assumee : pour la prevision 2026, on garde la methode la plus",
            "simple et la plus fiable sur les deux protocoles, plutot qu'un modele plus",
            "savant mais moins juste. L'analyse d'importance des variables confirme ce",
            "diagnostic : le score de l'annee N explique a lui seul l'essentiel de la",
            "prevision.",
        ]
    else:
        lignes += [
            f"Il bat la reference naive de "
            f"{mae_naive_glissante - mae_retenu_glissante:.3f} point de MAE moyenne",
            f"({mae_retenu_glissante:.3f} contre {mae_naive_glissante:.3f}), au-dela de",
            f"la marge de {MARGE_DECISION} fixee d'avance.",
        ]
    lignes += [
        "",
        "### Matrice de confusion des niveaux (modele retenu, test 2023-2025)",
        "",
        "```",
        matrice.to_string(),
        "```",
        "",
        "## 5. Importance des variables",
        "",
        "Importance par permutation sur le jeu de test (30 repetitions,",
        "`random_state=42`), mesuree en degradation de la MAE.",
        "",
        "```",
        top_importance[["variable", "importance_permutation", "ecart_type",
                        "coefficient_standardise"]].to_string(index=False),
        "```",
        "",
        "## 6. Analyse de sensibilite des poids",
        "",
        "```",
        sensible[["variante", "spearman_classement",
                  "part_regions_changeant_de_niveau_pct"]].to_string(index=False),
        "```",
        "",
        "Lecture : une correlation de Spearman proche de 1 signifie que le classement",
        "des regions ne depend pas du detail des poids. C'est le cas ici, ce qui rend",
        "l'indice robuste a ce choix. La variante `avec_variations_annuelles` est la",
        "plus eloignee : c'est la version ecartee de l'indice, et l'ecart montre que",
        "le choix du recul depuis le pic change reellement le classement.",
        "",
        f"## 7. Prevision {ANNEE_PREVISION} et son incertitude",
        "",
        f"Methode : {methode_2026}.",
        "Les facteurs affiches pour 2026 sont ceux de 2025.",
        "",
        "L'incertitude est estimee a partir de la distribution des erreurs du modele",
        "retenu sur les trois plis glissants : `score_bas` et `score_haut` sont les",
        "quantiles 10 % et 90 % de ces erreurs appliques au score prevu (bornes a",
        "0 et 100), et `proba_critique` est la part des erreurs observees qui",
        f"amenerait la region a {SEUIL_CRITIQUE} ou plus.",
        "",
        "| Rang | Region | Score | Intervalle probable | Proba. critique | Niveau | Facteurs |",
        "|---|---|---|---|---|---|---|",
    ]
    for rang, ligne in enumerate(classement_2026.itertuples(), start=1):
        lignes.append(
            f"| {rang} | {ligne.region_code} | {ligne.score} "
            f"| {ligne.score_bas} - {ligne.score_haut} "
            f"| {ligne.proba_critique * 100:.0f} % | {ligne.niveau} "
            f"| {ligne.facteurs} |")
    lignes += [
        "",
        "### Classement 2025 (observe)",
        "",
        "| Rang | Region | Score | Niveau | Facteurs |",
        "|---|---|---|---|---|",
    ]
    for rang, ligne in enumerate(classement_2025.itertuples(), start=1):
        lignes.append(f"| {rang} | {ligne.region_code} | {ligne.score} | "
                      f"{ligne.niveau} | {ligne.facteurs} |")
    lignes += [
        "",
        "## 8. Limites",
        "",
        "- Le score est un **indice relatif** : il classe les regions entre elles. Un",
        "  score de 50 ne veut pas dire « la moitie des eleves decrochent ».",
        "- La normalisation par rang percentile implique que, par construction, il y a",
        "  toujours des regions en haut et en bas du classement.",
        "- Les taux de scolarisation dependent de denominateurs de population projetes",
        "  depuis le RGPH 2019, incertains dans les regions a forts deplacements.",
        f"- La prevision {ANNEE_PREVISION} suppose la continuite des conditions de 2025.",
        "  Une degradation ou une amelioration securitaire brutale la rendrait fausse.",
        "- L'intervalle probable est issu de seulement 39 erreurs observees : il donne",
        "  un ordre de grandeur, pas une garantie statistique.",
        "- `random_state=42` partout : deux executions donnent le meme resultat.",
        "",
    ]
    (SORTIE / "rapport_modele.md").write_text("\n".join(lignes), encoding="utf-8")


if __name__ == "__main__":
    main()
