"""Etape 05 - Graphiques de la documentation.

Produit six figures PNG a partir des CSV deja calcules par le pipeline.
Aucune valeur n'est saisie a la main : chaque figure lit son fichier
source, et le script REFUSE d'ecrire une figure dont les donnees ne
couvrent pas ce qui est annonce (un graphique faux est plus couteux
qu'un graphique manquant).

    python pipeline/graphiques.py

Entrees  : data/03_transformation/indicateurs.csv
           data/03_transformation/survie_cohortes_national.csv
           data/04_analyse/risque.csv
           data/04_analyse/metriques_modeles.csv
           data/04_analyse/importance_variables.csv
           data/04_analyse/sensibilite_poids.csv
Sortie   : data/05_interpretation/graphiques/*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

RACINE = Path(__file__).resolve().parent.parent
TRANSFORME = RACINE / "data" / "03_transformation"
ANALYSE = RACINE / "data" / "04_analyse"
SORTIE = RACINE / "data" / "05_interpretation" / "graphiques"

ANNEE_PREVISION = 2026
REGIONS_ATTENDUES = 13

# Palette reprise de l'interface, pour que documentation et application
# racontent la meme chose avec les memes couleurs.
VERT = "#4C9A72"
OCRE = "#E0A43A"
ROUGE = "#C2412D"
ENCRE = "#2B333B"
GRIS = "#8A939B"
BLEU = "#3C6E8F"

produits: list[tuple[str, int]] = []
refus: list[tuple[str, str]] = []


def style() -> None:
    """Style editorial commun : sobre, lisible en noir et blanc a l'impression."""
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": ENCRE,
        "axes.labelcolor": ENCRE,
        "axes.edgecolor": "#D4D8DC",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "text.color": ENCRE,
        "xtick.color": GRIS,
        "ytick.color": GRIS,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "grid.color": "#E8EBEE",
        "grid.linewidth": 0.8,
    })


def fr(valeur: float, decimales: int = 1) -> str:
    """Nombre au format francais : virgule decimale, espace insecable fin."""
    texte = f"{valeur:,.{decimales}f}".replace(",", "\u202f").replace(".", ",")
    return texte


def couleur_niveau(score: float) -> str:
    return VERT if score < 33 else (OCRE if score < 66 else ROUGE)


# Les CSV du pipeline sont ecrits sans accents (contrainte d'encodage amont).
# La documentation, elle, est lue par des humains : on retablit les libelles.
LIBELLES_MODELES = {
    "reference naive (score N+1 = score N)": "Référence naïve\n(score N+1 = score N)",
    "regression Ridge (alpha=0.1)": "Régression Ridge\n(alpha = 0,1)",
    "foret aleatoire (max_depth=3)": "Forêt aléatoire\n(profondeur 3)",
}

LIBELLES_VARIANTES = {
    "poids_egaux": "Poids égaux",
    "sans_ecart_admission_achevement": "Sans : écart admission / achèvement",
    "sans_faible_achevement": "Sans : faible achèvement",
    "sans_recul_effectifs": "Sans : recul des effectifs",
    "sans_fermeture_ecoles": "Sans : fermetures d'écoles",
    "sans_faible_scolarisation": "Sans : faible scolarisation",
    "sans_disparite_filles_garcons": "Sans : disparité filles / garçons",
}


def noms_regions() -> dict[str, str]:
    """Nom affichable de chaque region, LU dans les donnees.

    `code.title()` produirait « Boucle-Du-Mouhoun » : la casse d'un nom propre
    se lit a la source, elle ne se devine pas par une regle typographique.
    """
    colonnes = pd.read_csv(TRANSFORME / "indicateurs.csv",
                           usecols=["region_code", "region_nom"])
    return dict(colonnes.drop_duplicates().to_numpy())


def enregistrer(fig, ax, nom: str, legende: str) -> None:
    """Ecrit la figure et note sa taille.

    La legende est ancree SOUS le libelle d'axe, en decalage de points : posee
    sur la figure, elle se superposait au libelle une fois le cadre resserre.
    """
    ax.annotate(legende, xy=(0, 0), xycoords="axes fraction",
                xytext=(0, -52), textcoords="offset points",
                fontsize=7.5, color=GRIS, ha="left", va="top")
    SORTIE.mkdir(parents=True, exist_ok=True)
    chemin = SORTIE / nom
    fig.savefig(chemin, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    octets = chemin.stat().st_size
    if octets < 10_000:
        refus.append((nom, f"fichier de {octets} octets, probablement vide"))
        chemin.unlink()
        return
    produits.append((nom, octets))
    print(f"ok      {nom:42} {octets // 1024} Ko")


def refuser(nom: str, raison: str) -> None:
    refus.append((nom, raison))
    print(f"REFUSE  {nom:42} {raison}")


# --------------------------------------------------------------------------
# 1. Classement des regions par score de risque (derniere annee observee)
# --------------------------------------------------------------------------
def graphique_classement(risque: pd.DataFrame, noms: dict[str, str]) -> None:
    nom = "01-classement-regions.png"
    observe = risque[risque["est_prevision"] == 0]
    annee = int(observe["annee"].max())
    lignes = observe[observe["annee"] == annee].sort_values("score")
    if len(lignes) != REGIONS_ATTENDUES:
        return refuser(nom, f"{len(lignes)} regions au lieu de {REGIONS_ATTENDUES}")

    fig, ax = plt.subplots(figsize=(8, 5.2))
    couleurs = [couleur_niveau(s) for s in lignes["score"]]
    barres = ax.barh(lignes["region_code"].map(noms),
                     lignes["score"], color=couleurs, height=0.68)
    for barre, score in zip(barres, lignes["score"]):
        ax.text(score + 1.2, barre.get_y() + barre.get_height() / 2,
                fr(score), va="center", fontsize=9, color=ENCRE, fontweight="bold")
    for seuil, etiquette in ((33, "Modéré"), (66, "Critique")):
        ax.axvline(seuil, color=GRIS, linestyle=(0, (4, 3)), linewidth=1)
        ax.text(seuil, len(lignes) - 0.2, f"  {etiquette}", fontsize=8, color=GRIS)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Score de risque (0 à 100)")
    ax.set_title(f"Risque de déperdition scolaire par région — {annee}")
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    enregistrer(fig, ax, nom,
                "Indice composite (0 à 100) calculé sur les données DGESS/MENAPLN. "
                "Ce n'est pas un taux d'abandon mesuré.")


# --------------------------------------------------------------------------
# 2. Trajectoire du score : les trois regions les plus exposees
# --------------------------------------------------------------------------
def graphique_trajectoires(risque: pd.DataFrame, noms: dict[str, str]) -> None:
    nom = "02-trajectoires-regions.png"
    observe = risque[risque["est_prevision"] == 0]
    derniere = int(observe["annee"].max())
    tete = (observe[observe["annee"] == derniere]
            .nlargest(3, "score")["region_code"].tolist())
    queue = observe[observe["annee"] == derniere].nsmallest(1, "score")["region_code"].tolist()
    choisies = tete + queue
    annees = sorted(observe["annee"].unique())
    if len(annees) < 5:
        return refuser(nom, f"seulement {len(annees)} années observées")

    fig, ax = plt.subplots(figsize=(8, 4.6))
    for code in choisies:
        serie = observe[observe["region_code"] == code].sort_values("annee")
        final = serie["score"].iloc[-1]
        ax.plot(serie["annee"], serie["score"], marker="o", markersize=4,
                linewidth=2, color=couleur_niveau(final), label=noms[code])
        ax.annotate(f"  {noms[code]}", (serie["annee"].iloc[-1], final),
                    fontsize=9, color=couleur_niveau(final), va="center",
                    fontweight="bold", annotation_clip=False)
    ax.axhspan(66, 100, color=ROUGE, alpha=0.06)
    ax.axhline(66, color=ROUGE, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(annees[0], 67.5, "seuil critique", fontsize=8, color=ROUGE)
    ax.set_ylim(0, 100)
    ax.set_xlim(min(annees) - 0.3, max(annees) + 0.4)
    # la place des noms est prise HORS cadre (annotation_clip=False) : le
    # graphique garde toute sa largeur utile et rien n'est tronque.
    fig.subplots_adjust(right=0.74)
    ax.set_xticks(annees)
    ax.set_ylabel("Score de risque")
    ax.set_title("Trois régions les plus exposées et la moins exposée")
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    enregistrer(fig, ax, nom,
                f"Années {min(annees)} à {max(annees)} observées. "
                "L'année est l'année de fin d'année scolaire.")


# --------------------------------------------------------------------------
# 3. Prevision 2026 et son intervalle
# --------------------------------------------------------------------------
def graphique_prevision(incertitude: pd.DataFrame, noms: dict[str, str]) -> None:
    nom = "03-prevision-2026-incertitude.png"
    if len(incertitude) != REGIONS_ATTENDUES:
        return refuser(nom, f"{len(incertitude)} régions au lieu de {REGIONS_ATTENDUES}")
    if not (incertitude["score_bas"] <= incertitude["score"]).all():
        return refuser(nom, "une borne basse dépasse le score prévu")
    if not (incertitude["score"] <= incertitude["score_haut"]).all():
        return refuser(nom, "un score prévu dépasse sa borne haute")

    lignes = incertitude.sort_values("score")
    fig, ax = plt.subplots(figsize=(8, 5.2))
    y = range(len(lignes))
    ax.hlines(list(y), lignes["score_bas"], lignes["score_haut"],
              color=GRIS, linewidth=5, alpha=0.45)
    ax.scatter(lignes["score"], list(y),
               color=[couleur_niveau(s) for s in lignes["score"]], zorder=3, s=46)
    ax.set_yticks(list(y))
    ax.set_yticklabels([noms[c] for c in lignes["region_code"]])
    for i, (bas, haut) in enumerate(zip(lignes["score_bas"], lignes["score_haut"])):
        ax.text(haut + 1.2, i, f"{fr(bas)} – {fr(haut)}", va="center",
                fontsize=8, color=GRIS)
    ax.axvline(66, color=ROUGE, linestyle=(0, (4, 3)), linewidth=1)
    ax.set_xlim(0, 118)
    ax.set_xlabel(f"Score prévu pour {ANNEE_PREVISION} et intervalle probable")
    ax.set_title(f"Prévision {ANNEE_PREVISION} : un point, une fourchette")
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    enregistrer(fig, ax, nom,
                "La barre grise est l'intervalle probable, construit sur l'erreur "
                "du modèle en validation. Le point est la valeur centrale.")


# --------------------------------------------------------------------------
# 4. Comparaison des modeles en validation glissante
# --------------------------------------------------------------------------
def graphique_modeles(metriques: pd.DataFrame) -> None:
    nom = "04-comparaison-modeles.png"
    glissante = metriques[metriques["protocole"] == "glissante"]
    if glissante.empty:
        return refuser(nom, "aucune ligne de protocole glissant")
    moyennes = (glissante.groupby("modele")["mae"].mean().sort_values())
    if len(moyennes) < 2:
        return refuser(nom, f"{len(moyennes)} modèle(s) comparé(s)")

    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    retenu = moyennes.index[0]
    couleurs = [BLEU if m == retenu else "#C9CFD4" for m in moyennes.index]
    barres = ax.barh([LIBELLES_MODELES.get(m, m) for m in moyennes.index],
                     moyennes.to_numpy(), color=couleurs, height=0.6)
    for barre, valeur in zip(barres, moyennes.to_numpy()):
        ax.text(valeur + 0.12, barre.get_y() + barre.get_height() / 2,
                fr(valeur, 2), va="center", fontsize=9, fontweight="bold",
                color=ENCRE)
    ax.set_xlabel("Erreur absolue moyenne (points de score), plus bas = mieux")
    ax.set_title("Validation glissante : la méthode simple l'emporte")
    ax.set_xlim(0, moyennes.max() * 1.25)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    enregistrer(fig, ax, nom,
                f"Moyenne sur {glissante['pli'].nunique()} plis : apprendre sur tout le "
                "passé, prévoir l'année suivante. Modèle retenu : "
                f"{LIBELLES_MODELES.get(retenu, retenu).replace(chr(10), ' ')}.")


# --------------------------------------------------------------------------
# 5. Taux de survie apparent au primaire, par sexe
# --------------------------------------------------------------------------
def graphique_survie(survie: pd.DataFrame) -> None:
    nom = "05-survie-cohortes.png"
    pivot = survie.pivot(index="annee_cp1", columns="sexe",
                         values="taux_survie_apparent_pct")
    manquants = [s for s in ("F", "G", "T") if s not in pivot.columns]
    if manquants:
        return refuser(nom, f"sexes absents : {manquants}")
    if len(pivot) < 3:
        return refuser(nom, f"{len(pivot)} cohortes seulement")

    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    for sexe, libelle, couleur in (("F", "Filles", ROUGE), ("G", "Garçons", BLEU),
                                   ("T", "Ensemble", ENCRE)):
        style_ligne = "-" if sexe == "T" else (0, (5, 2))
        ax.plot(pivot.index, pivot[sexe], marker="o", markersize=5, linewidth=2,
                linestyle=style_ligne, color=couleur, label=libelle)
        ax.annotate(f" {fr(pivot[sexe].iloc[-1])} %",
                    (pivot.index[-1], pivot[sexe].iloc[-1]),
                    fontsize=9, color=couleur, va="center", fontweight="bold")
    ax.set_ylim(40, 95)
    ax.set_xlim(pivot.index.min() - 0.2, pivot.index.max() + 1.3)
    ax.set_xticks(list(pivot.index))
    ax.set_ylabel("Taux de survie apparent (%)")
    ax.set_xlabel("Année d'entrée au CP1")
    ax.set_title("Une cohorte sur deux n'atteint pas le CM2 — et l'écart se creuse")
    ax.legend(frameon=False, loc="lower left", fontsize=9)
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} %"))
    enregistrer(fig, ax, nom,
                "Effectif CM2 en N+5 rapporté à l'effectif CP1 en N, national. "
                "Indicateur apparent : il mêle abandons, redoublements et migrations.")


# --------------------------------------------------------------------------
# 6. Robustesse de l'indice : que se passe-t-il si on change les poids ?
# --------------------------------------------------------------------------
def graphique_sensibilite(sensibilite: pd.DataFrame) -> None:
    nom = "06-sensibilite-indice.png"
    lignes = sensibilite[~sensibilite["variante"].str.startswith("avec_")]
    if lignes.empty:
        return refuser(nom, "aucune variante exploitable")
    lignes = lignes.sort_values("spearman_classement")

    fig, ax = plt.subplots(figsize=(8, 4.2))
    etiquettes = lignes["variante"].map(
        lambda v: LIBELLES_VARIANTES.get(v, v.replace("_", " ")))
    couleurs = [ROUGE if v < 0.92 else (OCRE if v < 0.96 else VERT)
                for v in lignes["spearman_classement"]]
    barres = ax.barh(etiquettes, lignes["spearman_classement"], color=couleurs,
                     height=0.6)
    for barre, rho, part in zip(barres, lignes["spearman_classement"],
                                lignes["part_regions_changeant_de_niveau_pct"]):
        ax.text(rho + 0.004, barre.get_y() + barre.get_height() / 2,
                f"ρ = {fr(rho, 3)}  ·  {fr(part)} % changent de niveau",
                va="center", fontsize=8.5, color=ENCRE)
    ax.set_xlim(0.85, 1.07)
    ax.set_xlabel("Corrélation de rang (Spearman) avec le classement de référence")
    ax.set_title("Le classement résiste au retrait de chaque composante")
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    enregistrer(fig, ax, nom,
                f"Chaque variante est comparée au classement de référence sur "
                f"{int(lignes['observations_comparees'].iloc[0])} observations "
                "région × année.")


def main() -> int:
    style()
    risque = pd.read_csv(ANALYSE / "risque.csv")
    incertitude = pd.read_csv(ANALYSE / "prevision_2026_incertitude.csv")
    metriques = pd.read_csv(ANALYSE / "metriques_modeles.csv")
    sensibilite = pd.read_csv(ANALYSE / "sensibilite_poids.csv")
    survie = pd.read_csv(TRANSFORME / "survie_cohortes_national.csv", comment="#")
    noms = noms_regions()

    graphique_classement(risque, noms)
    graphique_trajectoires(risque, noms)
    graphique_prevision(incertitude, noms)
    graphique_modeles(metriques)
    graphique_survie(survie)
    graphique_sensibilite(sensibilite)

    attendus = 6
    print("\n--- bilan ---")
    print(f"produits : {len(produits)} / {attendus}")
    for nom, raison in refus:
        print(f"refuse   : {nom} — {raison}")
    if len(produits) != attendus:
        print("\nECHEC : au moins une figure a ete refusee.")
        return 1
    print(f"Figures ecrites dans {SORTIE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
