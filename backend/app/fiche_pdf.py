"""Fiche d'une page pour un directeur regional (DREPS) : etat du risque, tendance, actions.

Le PDF est dessine avec fpdf2 : on place du texte, des rectangles et des barres
a des coordonnees en millimetres sur une page A4 (210 x 297 mm).
"""
from datetime import date

from fpdf import FPDF

# Couleurs par niveau de risque (R, V, B)
COULEURS = {"Faible": (46, 160, 67), "Modere": (230, 145, 30), "Critique": (205, 45, 45)}
BLEU = (12, 74, 140)
GRIS = (110, 110, 110)

LIBELLES = {
    "taux_achevement": "Taux d'achèvement du primaire (%)",
    "taux_brut_scolarisation": "Taux brut de scolarisation (%)",
    "taux_brut_admission": "Taux brut d'admission (%)",
    "taux_reussite_cep": "Taux de réussite au CEP (%)",
    "nombre_ecoles": "Nombre d'écoles",
    "effectif_primaire": "Effectif du primaire",
    # Indicateurs ajoutes par le Membre 2 (etape 03)
    "effectif_prescolaire": "Effectif du préscolaire",
    "nouveaux_inscrits_cp1": "Nouveaux inscrits au CP1",
    "nombre_ecoles_public": "Nombre d'écoles publiques",
    "nombre_ecoles_prive": "Nombre d'écoles privées",
    "eleves_par_ecole": "Élèves par école",
    "ecart_tba_tap": "Écart admission - achèvement (points)",
    "recul_effectif_primaire_vs_pic": "Élèves perdus depuis le pic (%)",
    "recul_nombre_ecoles_vs_pic": "Écoles fermées depuis le pic (%)",
    "ips_tba": "Indice de parité F/G (TBA)",
    "ips_tbs": "Indice de parité F/G (TBS)",
    "ips_tap": "Indice de parité F/G (TAP)",
    "variation_effectif_primaire": "Variation des effectifs (%)",
    "variation_nombre_ecoles": "Variation du nombre d'écoles (%)",
    "variation_taux_achevement": "Variation du taux d'achèvement (points)",
}

# Libelles lisibles des codes facteurs de risque.
LIBELLES_FACTEURS = {
    "ecart_admission_achevement": "Écart entre admission et achèvement",
    "faible_achevement": "Faible taux d'achèvement",
    "recul_effectifs": "Élèves perdus depuis le pic",
    "fermeture_ecoles": "Fermetures d'écoles",
    "faible_scolarisation": "Faible scolarisation",
    "disparite_filles_garcons": "Inégalité filles-garçons",
    "aucun_facteur_marquant": "Aucun facteur marquant",
}
SEXES = {"G": "Garçons", "F": "Filles", "T": "Total"}


def _texte(s) -> str:
    """Les polices integrees du PDF ne gerent que l'alphabet latin-1 : on remplace le reste."""
    s = str(s).replace("’", "'").replace("–", "-")
    return s.encode("latin-1", "replace").decode("latin-1")


def _nombre(v) -> str:
    """1234.0 -> '1 234' ; 58.31 -> '58.3' ; None -> '-'."""
    if v is None:
        return "-"
    texte = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"
    return texte.replace(",", " ")


def _titre_section(pdf: FPDF, titre: str) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*BLEU)
    pdf.cell(0, 7, _texte(titre), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*BLEU)
    pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)


def generer_fiche(fiche: dict, source_donnees: str) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(15, 12, 15)
    pdf.add_page()

    # --- Bandeau
    pdf.set_fill_color(*BLEU)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, 7)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 8, "EduAlert BF", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _texte("Fiche d'alerte décrochage scolaire - Direction régionale"))
    pdf.set_text_color(0, 0, 0)

    # --- Region + badge de risque
    actuel = fiche["risque_actuel"] or {}
    niveau = actuel.get("niveau", "-")
    pdf.set_xy(15, 34)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(110, 10, _texte(f"Région : {fiche['region_nom']}"))
    couleur = COULEURS.get(niveau, GRIS)
    pdf.set_fill_color(*couleur)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(135, 32)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(60, 9, _texte(f"Risque {niveau.upper()}"), align="C", fill=True, new_x="LEFT", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    type_annee = "prévision" if actuel.get("est_prevision") else "observé"
    pdf.cell(60, 6, _texte(f"Score {actuel.get('score', '-')}/100 - {actuel.get('annee', '')} ({type_annee})"),
             align="C", fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(50)

    if actuel.get("facteurs"):
        pdf.set_font("Helvetica", "I", 10)
        facteurs = ", ".join(
            LIBELLES_FACTEURS.get(f, f.replace("_", " "))
            for f in actuel["facteurs"].split(";"))
        pdf.multi_cell(0, 5, _texte(f"Principaux facteurs : {facteurs}"), new_x="LMARGIN", new_y="NEXT")

    # Intervalle de confiance, uniquement pour une annee prevue.
    incertitude = fiche.get("incertitude_prevision")
    if actuel.get("est_prevision") and incertitude:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _texte(
            f"Intervalle probable : {_nombre(incertitude['score_bas'])} a "
            f"{_nombre(incertitude['score_haut'])} - probabilite d'etre critique : "
            f"{incertitude['proba_critique'] * 100:.0f} %"),
            new_x="LMARGIN", new_y="NEXT")

    # --- Evolution du score (histogramme)
    _titre_section(pdf, "Évolution du score de risque")
    hist = fiche["historique_risque"]
    if hist:
        x0, y_base, haut_max = 20, pdf.get_y() + 48, 42
        larg = min(14, 170 / len(hist))
        for i, h in enumerate(hist):
            x = x0 + i * larg
            hauteur = haut_max * h["score"] / 100
            pdf.set_fill_color(*COULEURS.get(h["niveau"], GRIS))
            style = "D" if h["est_prevision"] else "F"   # prevision = barre vide (contour)
            pdf.set_draw_color(*COULEURS.get(h["niveau"], GRIS))
            pdf.rect(x + 1, y_base - hauteur, larg - 2, hauteur, style=style)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_xy(x, y_base - hauteur - 4)
            pdf.cell(larg, 4, f"{h['score']:.0f}", align="C")
            pdf.set_xy(x, y_base + 1)
            pdf.cell(larg, 4, str(h["annee"]), align="C")
        pdf.set_draw_color(*GRIS)
        pdf.line(x0, y_base, x0 + len(hist) * larg, y_base)
        pdf.set_xy(15, y_base + 6)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*GRIS)
        pdf.cell(0, 4, _texte("Barre pleine : observé. Barre vide : prévision. "
                              "Vert : faible, orange : modéré, rouge : critique."),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    # --- Tableau des indicateurs
    _titre_section(pdf, f"Indicateurs clés ({fiche['annee_indicateurs']})")
    table: dict[str, dict] = {}
    for r in fiche["indicateurs"]:
        table.setdefault(r["indicateur"], {})[r["sexe"]] = r["valeur"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(225, 234, 245)
    pdf.cell(90, 7, "Indicateur", border=1, fill=True)
    for s in ("G", "F", "T"):
        pdf.cell(30, 7, SEXES[s], border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for ind, valeurs in table.items():
        pdf.cell(90, 6, _texte(LIBELLES.get(ind, ind.replace("_", " "))), border=1)
        for s in ("G", "F", "T"):
            v = valeurs.get(s)
            pdf.cell(30, 6, _nombre(v),
                     border=1, align="C")
        pdf.ln()

    # --- Recommandations
    _titre_section(pdf, "Actions recommandées")
    pdf.set_font("Helvetica", "", 10)
    for reco in fiche["recommandations"]:
        pdf.multi_cell(0, 6, _texte(f"-  {reco}"), new_x="LMARGIN", new_y="NEXT")

    # --- Pistes par facteur de risque (Membre 2)
    par_facteur = fiche.get("actions_par_facteur") or []
    if par_facteur and pdf.get_y() < 248:
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, _texte("Pistes selon les facteurs de la région :"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for bloc in par_facteur:
            if pdf.get_y() > 258:
                break
            pdf.multi_cell(0, 4.5, _texte(
                f"{bloc['libelle']} : {' ; '.join(bloc['actions'])}"),
                new_x="LMARGIN", new_y="NEXT")

    # --- Pied de page : sources et avertissement
    pdf.set_y(272)
    pdf.set_draw_color(*GRIS)
    pdf.line(15, 271, 195, 271)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*GRIS)
    pdf.multi_cell(0, 4, _texte(
        "Sources : DGESS/MENAPLN, statistiques préscolaire et primaire 2016-2025 ; "
        "OCHA COD-AB (limites administratives). Année = année de fin d'année scolaire (2024/25 -> 2025). "
        f"Fiche générée le {date.today():%d/%m/%Y} par EduAlert BF - Data Challenge Burkina 2026."), new_x="LMARGIN", new_y="NEXT")
    if source_donnees != "reel":
        pdf.set_text_color(205, 45, 45)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 4, _texte("ATTENTION : données FICTIVES de démonstration."))

    return bytes(pdf.output())
