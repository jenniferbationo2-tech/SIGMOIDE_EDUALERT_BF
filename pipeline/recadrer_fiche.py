"""Etape 05 - Recadrage de la fiche pour la documentation.

La capture pleine page de la fiche fait plus de 4 000 px de haut : inseree
dans un document A4, elle occupe une page entiere et devient illisible.
La documentation n'a besoin que de sa partie haute (score, niveau,
facteurs, evolution du score).

    python pipeline/recadrer_fiche.py

Entree : data/05_interpretation/captures/03-fiche-region-critique.png
Sortie : data/05_interpretation/captures/03-fiche-haut-doc.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
CAPTURES = RACINE / "data" / "05_interpretation" / "captures"
SOURCE = CAPTURES / "03-fiche-region-critique.png"
SORTIE = CAPTURES / "03-fiche-haut-doc.png"

# La capture est prise a deviceScaleFactor=2 sur une fenetre de 1366 px :
# le panneau de la fiche occupe la colonne de droite. On ne garde que cette
# colonne, sur la hauteur qui va du titre a la fin du graphique d'evolution.
# Les bornes sont verifiees au rendu, pas deduites : le haut coupe le bandeau
# d'en-tete du site (badge « donnees reelles »), qui n'apporte rien dans un
# document deja titre, et le bas laisse respirer l'axe des annees.
PART_GAUCHE = 0.60      # debut de la colonne du panneau, en fraction de largeur
HAUT_UTILE = 190        # px : sous le bandeau d'en-tete
HAUTEUR_UTILE = 1560    # px de la capture d'origine (echelle 2x)


def main() -> int:
    if not SOURCE.exists():
        print(f"ECHEC : capture source absente : {SOURCE.relative_to(RACINE)}")
        return 1

    image = Image.open(SOURCE)
    largeur, hauteur = image.size
    gauche = int(largeur * PART_GAUCHE)
    bas = min(HAUTEUR_UTILE, hauteur)

    if bas < 600 or (largeur - gauche) < 400:
        print(f"ECHEC : decoupe aberrante sur une image de {largeur}x{hauteur}")
        return 1

    recadree = image.crop((gauche, HAUT_UTILE, largeur, bas))
    SORTIE.unlink(missing_ok=True)
    recadree.save(SORTIE, optimize=True)

    octets = SORTIE.stat().st_size
    if octets < 20_000:
        print(f"ECHEC : sortie de {octets} octets, probablement vide")
        SORTIE.unlink(missing_ok=True)
        return 1

    print(f"ok  {SORTIE.relative_to(RACINE)}  {recadree.size[0]}x{recadree.size[1]} px  "
          f"{octets // 1024} Ko  (source {largeur}x{hauteur})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
