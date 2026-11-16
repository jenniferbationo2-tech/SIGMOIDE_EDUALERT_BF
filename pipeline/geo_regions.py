"""Construit les contours des 13 anciennes regions a partir des 17 nouvelles (COD-AB, OCHA).

Pourquoi : les donnees DGESS 2016-2025 sont publiees par ancienne region (13),
alors que les limites COD-AB sont decoupees selon les 17 nouvelles regions.
Chaque polygone porte son ancienne region (adm1_name_old) : on fusionne par ce champ.

Usage (depuis la racine du projet) :
    backend/.venv/Scripts/python pipeline/geo_regions.py
"""
import csv
import json
import zipfile
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

RACINE = Path(__file__).resolve().parents[1]
SOURCE_ZIP = RACINE / "DataPack_DCB_2026/04_Cartographie_SIG/COD-AB_limites_administratives/bfa_admin_boundaries.geojson.zip"
SORTIE = RACINE / "data/03_transformation"

# Simplification : ~0.01 degre (~1 km). Le fichier passe de ~10 Mo a quelques centaines de Ko,
# suffisant pour une carte nationale et rapide a charger dans le navigateur.
TOLERANCE = 0.01


def slug(nom: str) -> str:
    """'Boucle du Mouhoun' -> 'BOUCLE-DU-MOUHOUN' : cle stable, sans accent ni espace."""
    return nom.upper().replace(" ", "-")


def main() -> None:
    with zipfile.ZipFile(SOURCE_ZIP) as z:
        admin1 = json.loads(z.read("bfa_admin1.geojson").decode("utf-8"))

    groupes: dict[str, dict] = {}
    correspondance = []
    for f in admin1["features"]:
        p = f["properties"]
        ancien = p["adm1_name_old"]
        g = groupes.setdefault(ancien, {"pcode_old": p["adm1_pcode_old"], "geoms": [], "nouvelles": []})
        g["geoms"].append(shape(f["geometry"]))
        g["nouvelles"].append(p["adm1_name"])
        correspondance.append({
            "region_code": slug(ancien), "region_nom": ancien, "pcode_ancien": p["adm1_pcode_old"],
            "nouvelle_region": p["adm1_name"], "pcode_nouveau": p["adm1_pcode"],
        })

    features = []
    for ancien, g in sorted(groupes.items()):
        geom = unary_union(g["geoms"]).simplify(TOLERANCE, preserve_topology=True)
        features.append({
            "type": "Feature",
            "properties": {
                "region_code": slug(ancien), "region_nom": ancien, "pcode": g["pcode_old"],
                "nouvelles_regions": ", ".join(sorted(g["nouvelles"])),
            },
            "geometry": mapping(geom),
        })

    SORTIE.mkdir(parents=True, exist_ok=True)
    geo_out = SORTIE / "regions13.geojson"
    geo_out.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")

    csv_out = SORTIE / "correspondance_regions_17_13.csv"
    with csv_out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(correspondance[0]))
        w.writeheader()
        w.writerows(sorted(correspondance, key=lambda r: r["region_code"]))

    print(f"{len(features)} regions -> {geo_out.name} ({geo_out.stat().st_size // 1024} Ko)")
    print(f"{len(correspondance)} lignes -> {csv_out.name}")


if __name__ == "__main__":
    main()
