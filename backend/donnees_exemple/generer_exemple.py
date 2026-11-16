"""Genere des donnees FICTIVES au format du contrat, pour developper l'API et le frontend
avant que les vrais CSV du Membre 2 soient prets. NE PAS utiliser pour l'analyse.

Usage, depuis backend/ :   python donnees_exemple/generer_exemple.py
"""
import json
import random
from pathlib import Path

import pandas as pd

ICI = Path(__file__).resolve().parent
GEO = ICI.parents[1] / "data/03_transformation/regions13.geojson"
random.seed(42)

regions = [(f["properties"]["region_code"], f["properties"]["region_nom"])
           for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]]

ind, risq = [], []
for code, nom in regions:
    base = random.uniform(40, 75)
    for annee in range(2016, 2026):
        choc = 0.55 if annee == 2023 else 1.0          # imite une rupture type 2022/23
        for sexe, k in [("G", 1.0), ("F", 1.05), ("T", 1.02)]:
            ind.append((code, nom, annee, sexe, "taux_achevement", round(base * k * choc, 1)))
            ind.append((code, nom, annee, sexe, "taux_brut_scolarisation", round((base + 25) * k * choc, 1)))
        ind.append((code, nom, annee, "T", "nombre_ecoles", int(random.uniform(500, 1500) * choc)))
    for annee in range(2016, 2027):                      # 2026 = prevision
        score = round(min(100, max(0, 100 - base + random.uniform(-10, 10) + (30 if annee >= 2023 else 0))), 1)
        niveau = "Critique" if score >= 66 else "Modere" if score >= 33 else "Faible"
        risq.append((code, annee, score, niveau, "baisse_effectifs;fermeture_ecoles", int(annee == 2026)))

pd.DataFrame(ind, columns=["region_code", "region_nom", "annee", "sexe", "indicateur", "valeur"]) \
    .to_csv(ICI / "indicateurs.csv", index=False)
pd.DataFrame(risq, columns=["region_code", "annee", "score", "niveau", "facteurs", "est_prevision"]) \
    .to_csv(ICI / "risque.csv", index=False)
print(f"FICTIF : {len(ind)} indicateurs, {len(risq)} scores de risque, {len(regions)} regions")
