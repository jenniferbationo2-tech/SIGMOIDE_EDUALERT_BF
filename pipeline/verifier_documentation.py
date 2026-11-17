"""Etape 05 - Controle des chiffres de la documentation.

Verifie que chaque nombre cite dans docs/documentation_EduAlertBF.md se
retrouve dans un fichier produit par le pipeline. Un document dont les
chiffres ont derive par rapport aux donnees est plus dangereux qu'un
document incomplet : il est credible et faux.

Controle aussi que chaque image citee existe, et signale les figures
produites mais jamais citees.

    python pipeline/verifier_documentation.py

Sortie : code 0 si tout concorde, 1 sinon (utilisable en controle avant
depot).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
DOC = RACINE / "docs" / "documentation_EduAlertBF.md"

resultats: list[bool] = []


def verifier(condition: bool, libelle: str) -> bool:
    """Enregistre un controle.

    Le libelle est TYPE : un appel aux arguments inverses leve, au lieu
    d'evaluer le libelle comme condition et de certifier n'importe quoi.
    """
    if not isinstance(libelle, str):
        raise TypeError("verifier(condition, libelle) : arguments inverses")
    etat = "OK   " if condition else "FAUX "
    print(f"  {etat} {libelle}")
    resultats.append(bool(condition))
    return bool(condition)


def fr(valeur: float, decimales: int = 1) -> str:
    """Ecriture francaise d'un nombre, telle qu'elle apparait dans le document."""
    return f"{valeur:.{decimales}f}".replace(".", ",")


def main() -> int:
    texte = DOC.read_text(encoding="utf-8")
    journal = (RACINE / "data/02_nettoyage/journal_nettoyage.md").read_text(encoding="utf-8")
    rapport = (RACINE / "data/04_analyse/rapport_modele.md").read_text(encoding="utf-8")

    risque = pd.read_csv(RACINE / "data/04_analyse/risque.csv")
    indicateurs = pd.read_csv(RACINE / "data/03_transformation/indicateurs.csv")
    metriques = pd.read_csv(RACINE / "data/04_analyse/metriques_modeles.csv")
    survie = pd.read_csv(RACINE / "data/03_transformation/survie_cohortes_national.csv",
                         comment="#")
    sensibilite = pd.read_csv(RACINE / "data/04_analyse/sensibilite_poids.csv")
    observe = risque[risque["est_prevision"] == 0]

    print("--- aucun encadre en attente ---")
    verifier("À COMPLÉTER" not in texte, "aucun encadre [A COMPLETER] restant")

    print("--- nettoyage (journal_nettoyage.md) ---")
    verifier("218 contrôles exécutés, 0 hors tolérance" in texte
             and "controles executes : 218" in journal,
             "218 controles de coherence, 0 hors tolerance")
    verifier("3 120 lignes" in texte and "dgess_regional_long.csv : 3120" in journal,
             "3 120 lignes regionales")
    verifier("840 lignes" in texte and "dgess_national_long.csv : 840" in journal,
             "840 lignes nationales")
    verifier("240 lignes" in texte and "dgess_totaux-nationaux.csv : 240" in journal,
             "240 lignes de total mises de cote")
    verifier("37 cellules" in texte and "37 cellule(s)" in journal,
             "37 cellules d'en-tete au texte parasite")
    verifier("0 valeur imputée" in texte and "non imputees) : 0" in journal,
             "aucune valeur imputee")

    print("--- indicateurs ---")
    verifier("4 615 lignes" in texte and len(indicateurs) == 4615,
             f"indicateurs.csv : {len(indicateurs)} lignes")
    verifier("20 indicateurs" in texte and indicateurs["indicateur"].nunique() == 20,
             f"{indicateurs['indicateur'].nunique()} indicateurs distincts")
    verifier(indicateurs["region_code"].nunique() == 13, "13 regions couvertes")

    print("--- cas du Sahel (justification du recul depuis le pic) ---")
    for code_indicateur, attendu in (("recul_effectif_primaire_vs_pic", 52.8),
                                     ("recul_nombre_ecoles_vs_pic", 82.0)):
        ligne = indicateurs[(indicateurs["region_code"] == "SAHEL")
                            & (indicateurs["annee"] == 2025)
                            & (indicateurs["indicateur"] == code_indicateur)]
        reel = abs(ligne["valeur"].iloc[0])
        verifier(round(reel, 1) == attendu and f"{fr(attendu)} %" in texte,
                 f"Sahel 2025, {code_indicateur} = {fr(reel)} %")

    print("--- classement 2025 ---")
    classement = observe[observe["annee"] == 2025]
    critiques = int((classement["niveau"] == "Critique").sum())
    verifier(f"**{critiques} régions sur 13 sont en niveau Critique**" in texte,
             f"{critiques} regions en niveau Critique")
    verifier(int((classement["niveau"] == "Faible").sum()) == 1,
             "une seule region en niveau Faible")
    for code, nom in (("CENTRE-NORD", "Centre-Nord"), ("BOUCLE-DU-MOUHOUN", "Boucle du Mouhoun"),
                      ("SAHEL", "Sahel"), ("EST", "Est"), ("CENTRE", "Centre")):
        score = classement[classement["region_code"] == code]["score"].iloc[0]
        verifier(f"| {nom} | {fr(score)} |" in texte, f"{nom} : {fr(score)} dans le tableau")

    print("--- bascules depuis 2022 ---")
    avant = observe[observe["annee"] == 2022].set_index("region_code")
    apres = observe[observe["annee"] == 2025].set_index("region_code")
    bascules = [c for c in apres.index
                if apres.loc[c, "niveau"] == "Critique" and avant.loc[c, "niveau"] != "Critique"]
    verifier(len(bascules) == 4 and "Quatre" in texte,
             f"{len(bascules)} regions basculees en Critique depuis 2022")

    print("--- modeles de prevision ---")
    glissante = metriques[metriques["protocole"] == "glissante"]
    moyennes = glissante.groupby("modele")["mae"].mean().sort_values()
    retenu = moyennes.index[0]
    verifier("naive" in retenu, f"modele retenu : {retenu}")
    verifier(f"**{fr(moyennes.iloc[0], 2)}**" in texte,
             f"MAE moyenne du modele retenu : {moyennes.iloc[0]:.4f}")
    justesse = glissante.groupby("modele")["justesse_niveau"].mean()[retenu] * 100
    verifier(f"{fr(justesse)} %" in texte, f"justesse de niveau : {fr(justesse)} %")
    plis = glissante[glissante["modele"] == retenu]["mae"]
    verifier(fr(plis.max(), 2) in texte, f"pli le plus difficile : {plis.max():.3f}")
    verifier(fr(plis.min(), 2) in texte, f"pli le plus recent : {plis.min():.3f}")
    verifier("117" in texte and "117" in rapport, "panel de 117 observations")
    verifier("104 paires" in texte and "104 observations" in rapport, "104 paires N -> N+1")

    print("--- survie des cohortes ---")
    for annee, sexe in ((2020, "T"), (2020, "F"), (2020, "G"), (2016, "T")):
        valeur = survie[(survie["annee_cp1"] == annee)
                        & (survie["sexe"] == sexe)]["taux_survie_apparent_pct"].iloc[0]
        verifier(f"{fr(valeur)} %" in texte, f"survie CP1 {annee} ({sexe}) : {fr(valeur)} %")

    print("--- sensibilite de l'indice ---")
    retenues = sensibilite[~sensibilite["variante"].str.startswith("avec_")]
    minimum = retenues["spearman_classement"].min()
    verifier(minimum > 0.90 and "supérieure à 0,90" in texte,
             f"correlation de rang minimale : {minimum:.4f}")
    verifier(fr(minimum, 3) in texte, f"valeur {fr(minimum, 3)} citee")
    pire = retenues.loc[retenues["spearman_classement"].idxmin()]
    verifier(f"{fr(pire['part_regions_changeant_de_niveau_pct'])} %" in texte,
             f"part changeant de niveau : {fr(pire['part_regions_changeant_de_niveau_pct'])} %")

    print("--- images citees ---")
    citees = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", texte)
    for relatif in citees:
        chemin = (DOC.parent / relatif).resolve()
        verifier(chemin.exists(), f"image presente : {relatif}")

    # Le reglement plafonne le document a 6 illustrations. L'assertion porte
    # sur la LISTE exacte, pas sur un minimum : un ajout non prevu doit rougir
    # au meme titre qu'une suppression.
    attendues = {
        "01-carte-2025-observe.png",       # la carte, resultat principal
        "03-fiche-haut-doc.png",           # la fiche, recadree pour le document
        "03-prevision-2026-incertitude.png",
        "04-comparaison-modeles.png",
        "05-survie-cohortes.png",
        "06-sensibilite-indice.png",
    }
    presentes = {Path(r).name for r in citees}
    verifier(presentes == attendues,
             f"{len(citees)} illustrations, conformes a la liste retenue"
             + ("" if presentes == attendues
                else f" (en trop : {sorted(presentes - attendues)}, "
                     f"manquantes : {sorted(attendues - presentes)})"))
    verifier(len(citees) <= 6, f"{len(citees)} illustrations (maximum 6)")

    # Les autres figures restent dans le depot et dans les depots 05 : leur
    # absence du document est voulue, ce n'est pas une anomalie.
    non_citees = []
    chemins_cites = {(DOC.parent / r).resolve() for r in citees}
    for dossier in ("graphiques", "captures"):
        for fichier in sorted((RACINE / "data/05_interpretation" / dossier).glob("*.png")):
            if fichier.resolve() not in chemins_cites:
                non_citees.append(fichier.name)
    print(f"  note  {len(non_citees)} figure(s) conservee(s) au depot sans etre "
          f"citee(s) dans le document (voulu)")

    total, reussis = len(resultats), sum(resultats)
    print(f"\n=== {reussis}/{total} controles OK ===")
    if reussis != total:
        print("ECHEC : au moins un chiffre du document ne correspond pas aux donnees.")
        return 1
    print("Tous les chiffres cites proviennent des fichiers du pipeline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
