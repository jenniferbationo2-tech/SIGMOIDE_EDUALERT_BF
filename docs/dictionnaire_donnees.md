# EduAlert BF – Schéma et dictionnaire des données

Rôle : Data Architect (Membre 1). Version 1 – 16/11/2026.

## 1. Parcours des données

```
SOURCES (01_collecte)                 PREPARATION                       SERVICE
-----------------------               -----------                       -------
DGESS xlsx 2016-2025 ─┐
INSD population      ─┼─► nettoyage (Membre 2) ─► indicateurs.csv ─┐
OCHA PDI / incidents ─┘    02_nettoyage           03_transformation │
                                                                    ├─► charger.py ─► SQLite ─► API FastAPI ─► Carte Vue/Leaflet
                           modele (Membre 2) ──► risque.csv ───────┤                          │                └► Fiche PDF
                           04_analyse                               │                          │
OCHA COD-AB (17 regions) ─► geo_regions.py ─► regions13.geojson ───┘                          └► /docs (documentation)
                           (fusion 17 -> 13)   03_transformation
```

Principe : **une seule source de vérité par étape**. Le frontend ne lit jamais les fichiers :
il passe toujours par l'API. Toute la chaîne se relance avec `run.bat` (ou `run.sh`).

## 2. Clé commune : région × année × sexe

| Clé | Format | Règle |
|---|---|---|
| `region_code` | Texte majuscule sans accent ni espace, ex. `BOUCLE-DU-MOUHOUN` | 13 anciennes régions (découpage DGESS). Correspondance avec les 17 nouvelles : `correspondance_regions_17_13.csv` |
| `annee` | Entier | **Année de fin d'année scolaire** : 2024/25 → `2025`. Le CEP de la session 2025 → `2025` |
| `sexe` | `G`, `F`, `T` | Garçons, Filles, Total |

## 3. Tables

### `regions` (13 lignes)
| Colonne | Type | Description |
|---|---|---|
| `region_code` | TEXT, clé primaire | Code région (voir §2) |
| `region_nom` | TEXT | Nom officiel de l'ancienne région, ex. « Boucle du Mouhoun » |

### `indicateurs` (format « long » : une ligne = région × année × sexe × indicateur)
| Colonne | Type | Description |
|---|---|---|
| `region_code` | TEXT | → `regions` |
| `annee` | INTEGER | Voir §2 |
| `sexe` | TEXT | G / F / T |
| `indicateur` | TEXT | Nom de l'indicateur (liste §4) |
| `valeur` | REAL | Valeur ; vide si manquante |

Clé primaire : (`region_code`, `annee`, `sexe`, `indicateur`) → aucun doublon possible.

**Pourquoi le format long ?** Ajouter un indicateur = ajouter des lignes, sans changer la base ni l'API.

### `risque` (une ligne = région × année)
| Colonne | Type | Description |
|---|---|---|
| `region_code` | TEXT | → `regions` |
| `annee` | INTEGER | Année observée ou prévue |
| `score` | REAL | Score de risque de décrochage, 0 (faible) à 100 (maximal) |
| `niveau` | TEXT | `Faible` (< 33), `Modere` (33–66), `Critique` (≥ 66) |
| `facteurs` | TEXT | Principaux facteurs, séparés par `;` |
| `est_prevision` | INTEGER | 1 = prévision du modèle, 0 = calculé sur données observées |

### `meta`
Origine des données chargées (`reel` ou `FICTIF`), exposée par `GET /sante`.

## 4. Indicateurs (noms à utiliser dans `indicateurs.csv`)

| `indicateur` | Définition | Source DGESS | Unité |
|---|---|---|---|
| `effectif_prescolaire` | Élèves inscrits au préscolaire | onglet PRESCOLAIRE | élèves |
| `effectif_primaire` | Élèves inscrits au primaire | Feuil1 | élèves |
| `nouveaux_inscrits_cp1` | Nouveaux inscrits au CP1 | Feuil5 | élèves |
| `taux_brut_admission` | TBA : nouveaux inscrits CP1 / population de 6 ans | Feuil6 | % |
| `taux_brut_scolarisation` | TBS : effectif primaire / population 6-11 ans | Feuil7 | % |
| `taux_achevement` | TAP : admis en CM2 non redoublants / population de 11 ans | Feuil8 | % |
| `taux_reussite_cep` | Admis au CEP / présentés | Feuil9 | % |
| `ips_tbs` | Indice de parité F/G du TBS (recalculé) | Feuil11 | ratio |
| `nombre_ecoles` | Écoles primaires (public + privé) | Feuil13 | écoles |
| `variation_effectif_primaire` | (effectif N − effectif N−1) / effectif N−1 | calculé | % |
| `eleves_par_ecole` | effectif primaire / nombre d'écoles | calculé | élèves |

Les indicateurs du Data Pack (PDI, incidents, population INSD, enseignants) s'ajoutent avec la même règle :
nom en minuscules, sans accent, mots séparés par `_`, et une ligne dans ce tableau.

## 5. Règles de qualité appliquées au chargement

- Colonnes obligatoires vérifiées : le chargement s'arrête avec un message clair s'il en manque une.
- Clés primaires : un doublon région × année × sexe × indicateur fait échouer le chargement.
- La base est recréée à chaque chargement : le résultat ne dépend que des CSV (reproductibilité).
- Les données fictives de `backend/donnees_exemple/` ne sont utilisées que si les vrais CSV sont absents ;
  elles sont alors signalées dans `/sante` et sur la fiche PDF.

## 6. Sources

| Donnée | Producteur | Publication | Année |
|---|---|---|---|
| Statistiques préscolaire et primaire | DGESS / MENAPLN | Données statistiques 2016-2025 (Data Challenge) | 2025 |
| Limites administratives (admin1) | OCHA / IGB | COD-AB Burkina Faso (Data Pack) | 2026 |
