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

| `indicateur` | Définition | Source DGESS | Unité | Sexes |
|---|---|---|---|---|
| `effectif_prescolaire` | Élèves inscrits au préscolaire | onglet PRESCOLAIRE (Tableau 1) | élèves | G/F/T |
| `effectif_primaire` | Élèves inscrits au primaire | Feuil1 | élèves | G/F/T |
| `nouveaux_inscrits_cp1` | Nouveaux inscrits au CP1 | Feuil5 | élèves | G/F/T |
| `taux_brut_admission` | TBA : nouveaux inscrits CP1 / population de 6 ans | Feuil6 | % | G/F/T |
| `taux_brut_scolarisation` | TBS : effectif primaire / population 6-11 ans | Feuil7 | % | G/F/T |
| `taux_achevement` | TAP : admis en CM2 non redoublants / population de 11 ans | Feuil8 | % | G/F/T |
| `taux_reussite_cep` | Admis au CEP / présentés | Feuil9 | % | G/F/T |
| `ips_tba` | Indice de parité F/G du TBA : TBA des filles / TBA des garçons (recalculé depuis Feuil6, les formules de Feuil10 ne sont pas lues) | calculé (Feuil6) | ratio | T |
| `ips_tbs` | Indice de parité F/G du TBS : TBS des filles / TBS des garçons (recalculé depuis Feuil7, les formules de Feuil11 ne sont pas lues) | calculé (Feuil7) | ratio | T |
| `ips_tap` | Indice de parité F/G du TAP : TAP des filles / TAP des garçons (recalculé depuis Feuil8, les formules de Feuil12 ne sont pas lues) | calculé (Feuil8) | ratio | T |
| `nombre_ecoles` | Écoles primaires, tous statuts (public + privé) | Feuil13 | écoles | T |
| `nombre_ecoles_public` | Écoles primaires publiques | Feuil13 | écoles | T |
| `nombre_ecoles_prive` | Écoles primaires privées | Feuil13 | écoles | T |
| `variation_effectif_primaire` | (effectif N − effectif N−1) / effectif N−1 × 100. Une chute traduit des élèves sortis du système (fermetures, déplacements de population). Indicateur d'affichage : il n'entre pas dans l'indice de risque, car un rebond après effondrement donne une variation positive trompeuse | calculé (Feuil1) | % | G/F/T |
| `variation_nombre_ecoles` | (écoles N − écoles N−1) / écoles N−1 × 100. Mesure les fermetures d'écoles liées à l'insécurité. Indicateur d'affichage, hors indice de risque (même raison) | calculé (Feuil13) | % | T |
| `recul_effectif_primaire_vs_pic` | (effectif N / maximum des effectifs de 2016 à N − 1) × 100. Négatif ou nul. Mesure la part des élèves jamais revenus depuis le meilleur niveau atteint par la région. Entre dans l'indice de risque à la place de la variation annuelle | calculé (Feuil1) | % | T |
| `recul_nombre_ecoles_vs_pic` | (écoles N / maximum des écoles de 2016 à N − 1) × 100. Négatif ou nul. Mesure les écoles jamais réouvertes depuis le pic. Entre dans l'indice de risque | calculé (Feuil13) | % | T |
| `eleves_par_ecole` | effectif primaire / nombre d'écoles. Mesure la pression sur l'offre scolaire restante | calculé (Feuil1, Feuil13) | élèves par école | T |
| `ecart_tba_tap` | TBA − TAP, en points. Un écart large signale que beaucoup d'élèves entrent mais que peu achèvent : déperdition en cours de cycle | calculé (Feuil6, Feuil8) | points de % | T |
| `variation_taux_achevement` | TAP N − TAP N−1, en points. Mesure la dégradation de la rétention | calculé (Feuil8) | points de % | T |

Les indicateurs de variation n'existent pas pour 2016 (pas d'année N−1) : aucune ligne n'est écrite
pour cette année-là, plutôt qu'une ligne à valeur vide. Les deux indicateurs de recul existent dès
2016, où ils valent 0 par construction (l'année est son propre maximum).

**Pourquoi un recul depuis le pic en plus de la variation annuelle ?** La variation annuelle fait
baisser à tort le risque d'une région encore dévastée : en 2025 le Sahel gagne 10,5 % d'élèves et
10 % d'écoles, mais il lui manque toujours 52,8 % de ses élèves et 82,0 % de ses écoles par rapport
à son meilleur niveau. Le recul depuis le pic mesure ce qui n'a pas été reconstitué. Les deux
familles restent publiées : les variations pour la lecture année par année, les reculs pour l'indice.

Les valeurs sont écrites avec 4 décimales dans `indicateurs.csv`. En amont,
`data/02_nettoyage/` conserve les taux en pleine précision, car les IPS sont des rapports de taux.

Les indicateurs du Data Pack (PDI, incidents, population INSD, enseignants) s'ajoutent avec la même règle :
nom en minuscules, sans accent, mots séparés par `_`, et une ligne dans ce tableau.

### 4.1 Contexte national (hors `indicateurs.csv`)

| Fichier | Contenu | Formule | Source |
|---|---|---|---|
| `data/03_transformation/survie_cohortes_national.csv` | Taux de survie apparent du primaire, national, par sexe | effectif CM2 de l'année N+5 / effectif CP1 de l'année N × 100 | Feuil4 |

C'est le seul proxy d'abandon par cohorte disponible : il est *apparent* (il ne suit pas les élèves
un par un) et mêle abandons, redoublements et migrations. Il sert à la documentation, pas à la carte.

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
