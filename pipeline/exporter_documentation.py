"""Etape 05 - Export PDF de la documentation.

Convertit docs/documentation_EduAlertBF.md en PDF, mise en page pour
l'impression (A4, images a l'echelle, titres non orphelins).

    python pipeline/exporter_documentation.py

Le rendu HTML est fait par `markdown`, l'impression par le Chromium deja
installe pour les captures : pas de chaine LaTeX a installer.

Sortie : docs/documentation_EduAlertBF.pdf
"""
from __future__ import annotations

import base64
import mimetypes
import re
import subprocess
import sys
from pathlib import Path

import markdown

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "docs" / "documentation_EduAlertBF.md"
SORTIE = RACINE / "docs" / "documentation_EduAlertBF.pdf"
HTML = RACINE / "docs" / ".documentation.html"

MAX_PAGES = 15          # plafond du reglement
MIN_CARACTERES = 300    # sous ce seuil, une page sans image est quasi vide

FEUILLE = """
@page { size: A4; margin: 18mm 16mm 16mm 16mm; }
body { font-family: "DejaVu Sans", sans-serif; font-size: 10pt; line-height: 1.5;
       color: #2B333B; }
h1 { font-size: 17pt; margin: 22pt 0 9pt; padding-bottom: 5pt;
     border-bottom: 2px solid #2B333B; page-break-after: avoid; }
h1:first-of-type { margin-top: 0; }
h2 { font-size: 13pt; margin: 16pt 0 6pt; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 5pt; page-break-after: avoid; }
p { margin: 0 0 7pt; text-align: justify; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0 11pt;
        font-size: 8.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #D4D8DC; padding: 4pt 6pt; text-align: left;
         vertical-align: top; }
th { background: #F2F4F6; font-weight: bold; }
img { display: block; margin: 9pt auto; page-break-inside: avoid;
      /* Contraintes du reglement : au plus 75 % de la largeur utile et 9 cm
         de haut. `object-fit: contain` garde les proportions quand la hauteur
         est la contrainte active, sinon l'image serait etiree. */
      max-width: 75%; max-height: 9cm; width: auto; height: auto;
      object-fit: contain; border: 1px solid #E8EBEE; }
/* Aucun saut de page force avant une image, et pas d'image orpheline en
   haut de page : elle reste collee au paragraphe qui l'introduit. */
p + img, p + p > img { page-break-before: avoid; }
h1, h2, h3 { page-break-before: auto; }
blockquote { margin: 9pt 0; padding: 7pt 11pt; border-left: 3px solid #C2412D;
             background: #FAF6F5; }
blockquote p { margin: 0; }
code { background: #F2F4F6; padding: 1pt 3pt; font-size: 8.5pt; }
pre { background: #F2F4F6; padding: 7pt; font-size: 8pt; overflow: hidden;
      page-break-inside: avoid; }
ul, ol { margin: 0 0 7pt; padding-left: 16pt; }
li { margin-bottom: 3pt; }
hr { border: 0; border-top: 1px solid #D4D8DC; margin: 14pt 0; }
"""


def incorporer_images(html: str) -> tuple[str, int, list[str]]:
    """Remplace chaque src par l'image encodee en base64.

    Chromium imprime depuis un fichier : une image absente ne provoque
    aucune erreur, elle laisse un cadre vide dans le PDF. On incorpore
    donc les octets et on REFUSE d'exporter si l'un manque.
    """
    manquantes: list[str] = []
    compte = 0

    def remplacer(m: re.Match) -> str:
        nonlocal compte
        rel = m.group(1)
        chemin = (SOURCE.parent / rel).resolve()
        if not chemin.exists():
            manquantes.append(rel)
            return m.group(0)
        type_mime = mimetypes.guess_type(chemin.name)[0] or "image/png"
        donnees = base64.b64encode(chemin.read_bytes()).decode("ascii")
        compte += 1
        return f'src="data:{type_mime};base64,{donnees}"'

    return re.sub(r'src="([^"]+)"', remplacer, html), compte, manquantes


def titre_et_sous_titre(texte: str) -> tuple[str, str, str]:
    """Lit l'entete YAML du document plutot que de reecrire son titre."""
    bloc = re.match(r"^---\n(.*?)\n---\n", texte, re.S)
    champs = {}
    if bloc:
        for ligne in bloc.group(1).splitlines():
            if ":" in ligne:
                cle, valeur = ligne.split(":", 1)
                champs[cle.strip()] = valeur.strip().strip('"')
        texte = texte[bloc.end():]
    return (champs.get("title", "Documentation"),
            champs.get("subtitle", ""),
            texte)


def main() -> int:
    chrome = next((p for p in Path("/root/.cache/ms-playwright").glob(
        "chromium-*/chrome-linux64/chrome")), None)
    if chrome is None:
        print("ECHEC : Chromium introuvable.")
        return 1

    brut = SOURCE.read_text(encoding="utf-8")
    titre, sous_titre, corps = titre_et_sous_titre(brut)

    rendu = markdown.markdown(corps, extensions=["tables", "fenced_code", "toc"])
    rendu, images, manquantes = incorporer_images(rendu)
    if manquantes:
        print(f"ECHEC : {len(manquantes)} image(s) citee(s) mais absente(s) :")
        for rel in manquantes:
            print(f"  - {rel}")
        return 1

    page = (f"<!doctype html><html lang=fr><head><meta charset=utf-8>"
            f"<title>{titre}</title><style>{FEUILLE}</style></head><body>"
            f"<h1>{titre}</h1>"
            f"<p style='font-size:11pt;color:#8A939B;margin-bottom:16pt'>{sous_titre}</p>"
            f"{rendu}</body></html>")
    HTML.write_text(page, encoding="utf-8")

    SORTIE.unlink(missing_ok=True)   # jamais laisser passer un PDF perime
    resultat = subprocess.run(
        [str(chrome), "--headless", "--no-sandbox", "--disable-gpu",
         "--no-pdf-header-footer", f"--print-to-pdf={SORTIE}",
         f"file://{HTML}"],
        capture_output=True, text=True, timeout=180)
    HTML.unlink(missing_ok=True)

    if not SORTIE.exists():
        print("ECHEC : aucun PDF produit.")
        print(resultat.stderr[-600:])
        return 1

    octets = SORTIE.stat().st_size
    try:
        from pypdf import PdfReader
    except ImportError:
        print("ECHEC : pypdf manquant, impossible de verifier la pagination.")
        return 1

    lecture = PdfReader(SORTIE)
    pages = len(lecture.pages)
    print(f"ok  {SORTIE.relative_to(RACINE)}  {octets // 1024} Ko  "
          f"{images} images incorporees  {pages} pages")

    # --- Controle de pagination ---
    # Une page presque vide trahit un saut force ou une image orpheline. On
    # compte le texte ET les images : une page d'illustration est legitime.
    echecs = []
    print("\n  page  caracteres  images")
    for numero, page in enumerate(lecture.pages, start=1):
        texte = (page.extract_text() or "").strip()
        nb_images = len(getattr(page, "images", []) or [])
        marque = ""
        if len(texte) < MIN_CARACTERES and nb_images == 0:
            marque = "  <- PAGE PRESQUE VIDE"
            echecs.append(numero)
        print(f"  {numero:>4}  {len(texte):>10}  {nb_images:>6}{marque}")

    if pages > MAX_PAGES:
        print(f"\nECHEC : {pages} pages, maximum {MAX_PAGES}.")
        return 1
    if echecs:
        print(f"\nECHEC : page(s) presque vide(s) sans image : {echecs}")
        return 1
    if octets < 200_000:
        print("\nECHEC : taille faible pour un document illustre.")
        return 1
    print(f"\n{pages} pages (max {MAX_PAGES}), aucune page presque vide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
