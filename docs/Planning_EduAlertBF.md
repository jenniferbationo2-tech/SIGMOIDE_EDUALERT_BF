---
title: "EduAlert BF – Planning de travail"
subtitle: "Data Challenge Burkina 2026 – Défi 1 – du 14 au 18 novembre"
---

# 1. Ce qu'on doit rendre le 18 novembre

1. **La solution** : application web (carte du risque + fiches régions), qui se relance facilement.
2. **La documentation** : 15 pages maximum, en PDF, selon le plan du règlement :
   défi (1 p.) · données (2 p.) · préparation (2-3 p.) · méthode (3 p.) · résultats (3 p.) · réponse au défi (1-2 p.) · reproduction (1 p.).
3. **Les dépôts à chaque étape** sur equation.africadataentry.com : `01_collecte`, `02_nettoyage`, `03_transformation`, `04_analyse`, `05_interpretation`.

> **Chaque dépôt rapporte des points.** On dépose au fil de l'eau, pas tout le dernier jour.

**Nommage obligatoire :** `EQUIPE_ETAPE_DEFI_ROLE_description_vN`
Exemple : `E07_02-nettoyage_D1_engineer_effectifs-primaire-propres_v2.csv`
Pas d'espace ni d'accent, versions numérotées (v1, v2…), un fichier LISEZ-MOI par dépôt.

# 2. Réajustements du protocole (à cause des données réelles)

| Le protocole disait | Les données disponibles | On fait plutôt |
|---|---|---|
| Absentéisme et notes du 1er trimestre | Aucune donnée par élève ou par trimestre | Prévoir le risque de l'année N+1 à partir des indicateurs de l'année N |
| Établissements et communes | Données DGESS par région | Région en base ; province si le Data Pack le permet |
| Primaire, post-primaire, secondaire | Préscolaire et primaire | Focus **primaire** |
| XGBoost avec un F1 supérieur à 80 % | Environ 13 régions × 10 ans ≈ 130 lignes | Indice composite + modèle simple, validation honnête |
| Laravel + MySQL + MongoDB | Trop lourd pour 4 jours | **FastAPI + SQLite + Vue + Leaflet** |

**Fait marquant à exploiter :** forte chute des effectifs et du nombre d'écoles en 2022/23 (fermetures liées à l'insécurité). À croiser avec les données PDI/OCHA du Data Pack.

# 3. Démarche

- **Variable cible (indicateurs indirects du décrochage)** : évolution des effectifs, taux d'achèvement (TAP) et sa variation, écart TAP − TBA, baisse du nombre d'écoles. Si le Data Pack contient les effectifs par niveau et par région, on calcule de vrais taux d'abandon par cohorte.
- **Facteurs explicatifs** : élèves par école ou par enseignant, parité filles-garçons, part rural/public, réussite au CEP, préscolaire, population INSD, personnes déplacées (PDI) et incidents de sécurité.
- **Livrable analyse 1 : indice composite de risque**, réparti en 3 classes (Faible / Modéré / Critique).
- **Livrable analyse 2 : modèle de prévision N+1**, avec validation temporelle (entraînement jusqu'en 2022, test sur 2023-2025) et importance des variables.
- **Application** : carte des régions colorée selon le risque, curseur pour l'année, fiche par région (indicateurs, tendance, facteurs, recommandations), export PDF « fiche directeur régional ».

# 4. Répartition des rôles

| | Membre 1 – Data et Backend | Membre 2 – Data science, analyse, frontend |
|---|---|---|
| Rôles du challenge | Data Architect + Data Engineer (appui) | Data Engineer + Data Analyst + Data Scientist |
| Responsabilités | Schéma de données, dictionnaire des variables, base SQLite, API FastAPI, contours GeoJSON des régions, intégration du modèle dans l'API, script de lancement / Docker, README de reproduction | Nettoyage des données, journal de nettoyage, calcul des indicateurs, indice de risque, modèle de prévision, application Vue + Leaflet |

# 5. Planning jour par jour

| Jour | Membre 1 (Data et Backend) | Membre 2 (Data science et Frontend) | Dépôts |
|---|---|---|---|
| **Ven. 14** | Initialisation du dépôt git ✅, squelette FastAPI, extraction des contours GeoJSON (Data Pack, COD-AB) | Inventaire des sources du Data Pack ; script de nettoyage de l'Excel DGESS vers des CSV « longs » (région, année, sexe, variable, valeur) ; table de correspondance des noms de régions | **01_collecte** (données brutes + sources + LISEZ-MOI) |
| **Sam. 15** | Schéma de données + dictionnaire des variables ; chargement des CSV propres dans SQLite ; endpoints `/regions`, `/indicateurs` | Fin du nettoyage + journal de nettoyage ; contrôle des totaux par rapport à l'annuaire ; calcul des indicateurs (taux, ratios, variations) | **02_nettoyage**, **03_transformation** |
| **Dim. 16** | Endpoint `/risque?annee=` relié au modèle ; endpoint de génération de la fiche PDF | Indice composite, modèle de prévision, validation, importance des variables ; premières maquettes Vue + Leaflet | **04_analyse** (code du modèle, métriques, prévisions) |
| **Lun. 17** | Script de lancement en une commande (ou Docker) ; tests ; mise en ligne (Vercel) | Carte interactive, fiches régions, graphiques ; **rédaction de la documentation à deux** | **05_interpretation** (carte, fiches) |
| **Mar. 18** | Gel du code le matin ; README de reproduction ; zip du code | Finalisation de la documentation (PDF, 15 pages max) ; captures d'écran | **Code**, **Documentation**, versions finales |

> **Objectif : tout déposé avant midi le 18.** Vérifier l'heure exacte de clôture sur la plateforme.

# 6. Contrat entre backend et frontend (à valider ensemble)

Le frontend ne lit jamais les fichiers directement : il passe toujours par l'API.

| Endpoint | Rôle |
|---|---|
| `GET /regions` | Liste des régions (code, nom) |
| `GET /geo/regions` | Contours des régions au format GeoJSON (pour Leaflet) |
| `GET /indicateurs?region=&annee=` | Indicateurs d'une région pour une année |
| `GET /risque?annee=` | Score et niveau de risque de toutes les régions (pour colorer la carte) |
| `GET /regions/{code}/fiche` | Fiche détaillée d'une région (tendance, facteurs, recommandations) |

**Format des CSV propres attendus du Membre 2** (dans `data/03_transformation/`) : une ligne = une région × une année × un indicateur. Colonnes : `region_code, region_nom, annee, sexe, indicateur, valeur`.
L'année est notée par l'année de fin de l'année scolaire (2024/25 → 2025), à appliquer partout.

# 7. Organisation du dépôt git

```
EDUALERTBF/
├─ data/00_sources/        fichier DGESS d'origine
├─ data/01_collecte/ … 05_interpretation/
├─ pipeline/               scripts de traitement relançables (Membre 2)
├─ backend/                API FastAPI (Membre 1)
├─ frontend/               Vue + Leaflet (Membre 2)
└─ docs/                   documentation, dictionnaire, journal de nettoyage
```

- Le Data Pack (869 Mo) **n'est pas dans git** : chacun le télécharge depuis le Drive du challenge et le place à la racine sous `DataPack_DCB_2026/`.
- Branches : `backend` (Membre 1), `frontend` et `data` (Membre 2). On fusionne dans `main` quand une étape fonctionne.

# 8. Règles d'or du challenge

- Ne pas envoyer les données sensibles à un outil d'IA. Faire le nettoyage soi-même. Déclarer dans la documentation l'usage éventuel de l'IA (ce qu'on lui a demandé, ce qu'on a retenu).
- Citer la source de chaque donnée (producteur, publication, année).
- Vérifier les totaux par rapport aux publications d'origine.
- Pièges : anciennes (13) et nouvelles (17) régions ; orthographes multiples des provinces ; année scolaire différente de l'année civile.

# 9. À faire tout de suite

- [ ] Récupérer le numéro d'équipe (E??) pour nommer les fichiers
- [ ] Vérifier l'heure de clôture du 18
- [ ] Membre 2 : télécharger le Data Pack et cloner le dépôt git
- [ ] Valider ensemble le contrat d'API (section 6) et le format des CSV
