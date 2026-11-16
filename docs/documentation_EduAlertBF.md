---
title: "EduAlert BF"
subtitle: "Cartographier et anticiper le risque de décrochage scolaire par région au Burkina Faso"
author: "Équipe AB7C-938F-79BB – Data Challenge Burkina 2026, Édition Éducation – Défi 1"
date: "Novembre 2026"
lang: fr
---

> **Note de travail (à supprimer avant export)** – Cible : 15 pages maximum.
> Les encadrés `[À COMPLÉTER – Membre 2]` attendent les résultats du nettoyage et du modèle.
> Ne jamais inscrire un chiffre qui ne sort pas de nos scripts.

# 1. Le défi

**Défi choisi : Défi 1 – Cartographie et anticipation du risque de décrochage scolaire par région.**

**Notre question, avec nos mots :**
*Dans quelles régions du Burkina Faso les élèves du primaire risquent-ils le plus de quitter l'école l'an prochain,
pourquoi, et comment donner cette information à un directeur régional assez tôt pour qu'il agisse ?*

Aujourd'hui, le décrochage est constaté **après coup**, dans l'annuaire statistique de l'année suivante.
Entre 2016 et 2025, le système éducatif a connu une rupture brutale (fermetures d'écoles liées à l'insécurité,
déplacements de populations) qui a montré le coût de cette lecture tardive : quand l'annuaire paraît, les élèves sont déjà partis.

**Ce que propose EduAlert BF :**

1. un **score de risque de décrochage** par région et par année, de 0 à 100, classé en trois niveaux (Faible, Modéré, Critique) ;
2. une **prévision pour l'année scolaire suivante** ;
3. une **carte interactive** et une **fiche d'alerte d'une page** par région, pensée pour le directeur régional (DREPS).

**Pour qui :** le MENAPLN et la DGESS (pilotage national), les directions régionales et provinciales (DREPS, DPEPS) pour cibler
cantines, kits scolaires, enseignants et actions de sensibilisation.

**Périmètre retenu :** l'enseignement **primaire**, au niveau des **13 régions** du découpage de l'annuaire DGESS, de 2015/16 à 2024/25.
Notre note d'intention visait aussi le post-primaire, le secondaire et le niveau établissement ; les données publiques disponibles
(agrégées par région et par année) ne le permettent pas sans tomber dans l'approximation. Nous avons préféré un périmètre plus
étroit mais solide (voir section 6, limites).

# 2. Les données

## 2.1 Sources utilisées

| Donnée | Producteur | Publication | Année | Usage |
|---|---|---|---|---|
| Statistiques du préscolaire et du primaire 2016-2025 | DGESS / MENAPLN | Fichier fourni par le Data Challenge | 2025 | Effectifs, taux, écoles, CEP |
| Limites administratives (niveau régions) | OCHA / IGB – COD-AB | Data Pack DCB 2026 | 2026 | Contours de la carte |
| `[À COMPLÉTER – Membre 2]` ex. personnes déplacées internes | CONASUR / OCHA | Data Pack DCB 2026 | 2025 | Facteur de risque sécuritaire |
| `[À COMPLÉTER – Membre 2]` ex. population | INSD | RGPH 2019 / projections | 2019 | Dénominateurs |

L'inventaire complet est déposé : `AB7C-938F-79BB_01-collecte_D1_architect_inventaire-sources_v1.csv`.

## 2.2 Contenu du fichier DGESS

Le fichier comporte 14 tableaux, tous **par région** (13 anciennes régions) et **par année scolaire** de 2015/16 à 2024/25 :
effectifs du préscolaire et du primaire par sexe, par statut (public/privé) et par milieu (urbain/rural) ; effectifs par niveau
(CP1 à CM2, au niveau national) ; nouveaux inscrits au CP1 ; taux brut d'admission (TBA), taux brut de scolarisation (TBS)
et taux d'achèvement (TAP) par sexe ; taux de réussite au CEP ; indices de parité ; nombre d'écoles par statut.

## 2.3 Limites des données

- **Pas de donnée individuelle ni infra-annuelle** : pas d'absentéisme, pas de notes trimestrielles, pas de suivi d'élève.
  Le « décrochage » est donc mesuré **indirectement**, à l'échelle d'une région (voir 4.1).
- **Pas de taux d'abandon publié par région** dans le fichier : nous le reconstruisons à partir des indicateurs disponibles.
- **Granularité régionale** : 13 régions × 10 années = 130 observations. C'est peu pour un modèle d'apprentissage automatique ;
  cela guide nos choix de méthode (section 4).
- **Rupture de 2022/23** : chute brutale des effectifs et du nombre d'écoles dans plusieurs régions. C'est à la fois le signal
  que nous voulons détecter et une difficulté pour la prévision (changement de régime).
- **Deux découpages administratifs** : les données DGESS suivent les 13 anciennes régions ; les cartes récentes suivent les
  17 nouvelles régions (voir 3.1).

# 3. La préparation

## 3.1 Réconcilier deux cartes du pays : 17 régions → 13 régions

**Le problème.** Les limites administratives du Data Pack (OCHA COD-AB, 2026) découpent le Burkina Faso en **17 nouvelles régions**
(Bankui, Djôrô, Goulmou, Guiriko, Kadiogo, Koulsé, Liptako, Nakambé, Nando, Nazinon, Oubri, Sirba, Soum, Sourou, Tannounyan,
Tapoa, Yaadga). Les statistiques DGESS 2016-2025 sont publiées selon les **13 anciennes régions**. Les deux découpages
ne se recoupent pas un à un : on ne peut pas poser directement les chiffres sur la carte.

**Notre solution.** Chaque polygone du fichier COD-AB conserve le nom et le code de son ancienne région
(`adm1_name_old`, `adm1_pcode_old`). Le script `pipeline/geo_regions.py` :

1. regroupe les 17 polygones par ancienne région ;
2. **fusionne** les géométries de chaque groupe (union géométrique) : par exemple *Bankui + Sourou → Boucle du Mouhoun*,
   *Goulmou + Sirba + Tapoa → Est*, *Liptako + Soum → Sahel* ;
3. **simplifie** les contours (tolérance d'environ 1 km) : le fichier passe d'environ **10 Mo à 59 Ko**, ce qui permet un
   affichage instantané dans le navigateur sans perte visible à l'échelle nationale ;
4. produit une **table de correspondance** 17 ↔ 13 (`correspondance_regions_17_13.csv`), réutilisable pour rattacher
   toute donnée publiée selon le nouveau découpage (déplacés, population récente).

**Contrôle :** 17 polygones en entrée, 13 régions en sortie, chaque nouvelle région rattachée à exactement une ancienne.

## 3.2 Une clé commune pour toutes les données

Pour que toutes les sources se croisent, chaque valeur est rangée selon la même clé :

| Clé | Règle |
|---|---|
| `region_code` | Nom de l'ancienne région en majuscules, sans accent ni espace (`BOUCLE-DU-MOUHOUN`) : une seule orthographe, quelle que soit la source |
| `annee` | **Année de fin d'année scolaire** : 2024/25 → 2025. Évite la confusion année scolaire / année civile |
| `sexe` | `G`, `F` ou `T` (total) |

Les indicateurs sont stockés au **format long** (une ligne = région × année × sexe × indicateur) : ajouter une nouvelle source
revient à ajouter des lignes, sans modifier la base ni l'application. Le schéma complet et le dictionnaire des variables sont
déposés : `AB7C-938F-79BB_03-transformation_D1_architect_schema-dictionnaire-donnees_v1.md`.

## 3.3 Nettoyage du fichier DGESS

`[À COMPLÉTER – Membre 2]` Décrire, avec le journal de nettoyage :

- en-têtes sur deux lignes (année puis G/F/T) et cellules fusionnées → mise au format long ;
- suppression des lignes de total (Burkina Faso) ;
- caractères accentués mal encodés ;
- harmonisation des noms de régions ;
- indices de parité stockés sous forme de **formules Excel** → recalculés ;
- incohérences relevées et traitement des valeurs manquantes ;
- **vérification des totaux** par rapport à l'annuaire publié (règle d'or du challenge) : écarts constatés.

## 3.4 Variables construites

`[À COMPLÉTER – Membre 2]` Ex. variation annuelle des effectifs, élèves par école, écart TAP − TBA, évolution du nombre
d'écoles, indice de parité. Formule et justification de chacune.

# 4. La méthode

## 4.1 Mesurer le décrochage sans donnée individuelle

`[À COMPLÉTER – Membre 2]` Définition retenue de la variable cible (indicateur indirect du décrochage) et justification.

## 4.2 Score de risque et prévision

`[À COMPLÉTER – Membre 2]`

- construction de l'indice composite (normalisation, pondération) et seuils Faible / Modéré / Critique (< 33, 33-66, ≥ 66) ;
- modèle de prévision de l'année N+1 et pourquoi ce choix plutôt qu'un modèle plus complexe (130 observations) ;
- validation **temporelle** : entraînement sur les années anciennes, test sur les plus récentes (jamais de « triche » avec le futur) ;
- mesure de fiabilité et importance des variables.

## 4.3 Architecture de la solution

La solution suit le parcours des données du challenge, de la collecte à la visualisation :

```
DGESS, INSD, OCHA ──► nettoyage ──► indicateurs.csv ─┐
                                                    ├─► chargement ─► base SQLite ─► API FastAPI ─┬─► carte interactive (Vue + Leaflet)
          modèle de risque ──► risque.csv ──────────┤                                            ├─► fiche PDF par région
OCHA COD-AB ─► fusion 17→13 ─► regions13.geojson ───┘                                            └─► documentation /docs
```

**Choix techniques et raisons :**

| Composant | Choix | Pourquoi |
|---|---|---|
| Langage | Python | Même langage pour les données, le modèle et l'API : le modèle s'intègre sans traduction |
| API | FastAPI | Peu de code, validation automatique des paramètres, **documentation interactive générée** (`/docs`) |
| Base | SQLite | Un seul fichier, aucune installation de serveur : la solution se relance sur n'importe quel poste. Suffisant pour quelques milliers de lignes |
| Carte | Leaflet + GeoJSON | Bibliothèque libre, légère, fonctionne sans clé d'accès payante |
| Fiche PDF | fpdf2 | Génération en Python pur, sans logiciel externe |

Nous avons volontairement écarté l'architecture plus lourde envisagée dans la note d'intention (Laravel, MySQL, MongoDB) :
pour 13 régions et quelques milliers de valeurs, elle ajoutait de l'installation et des risques de panne sans bénéfice.
**Une solution simple est une solution qu'un service déconcentré peut réellement faire tourner.**

**Principes de conception :**

- **Une seule porte d'entrée** : la carte et les fiches ne lisent jamais les fichiers, elles interrogent l'API. Changer une source
  ne casse pas l'interface.
- **Reproductibilité** : la base est reconstruite entièrement à chaque chargement à partir des CSV ; même entrée → même résultat.
- **Contrôles au chargement** : colonnes obligatoires vérifiées, doublons interdits par clé primaire.
- **Traçabilité** : l'API indique l'origine des données servies (`GET /sante`) ; chaque fiche PDF cite ses sources.

**Services de l'API :**

| Service | Rôle pour l'utilisateur |
|---|---|
| `GET /risque?annee=` | Couleur de chaque région sur la carte pour l'année choisie |
| `GET /geo/regions` | Contours des 13 régions |
| `GET /regions/{code}/fiche` | Détail d'une région : historique du risque, indicateurs, recommandations |
| `GET /regions/{code}/fiche.pdf` | Fiche d'alerte d'une page à imprimer ou à transmettre |
| `GET /indicateurs` | Indicateurs filtrables par région, année, sexe |
| `GET /regions`, `GET /annees`, `GET /sante` | Référentiels et état du service |

# 5. Les résultats

## 5.1 La carte du risque

`[À COMPLÉTER – Membres 1 et 2]` Capture de la carte pour la dernière année observée et pour l'année prévue. Lecture : quelles
régions sont en niveau critique, lesquelles ont basculé depuis 2022.

## 5.2 Les régions prioritaires

`[À COMPLÉTER – Membre 2]` Classement des régions, principaux facteurs par région, évolution 2016-2025.

## 5.3 Fiabilité de la prévision

`[À COMPLÉTER – Membre 2]` Métriques sur la période de test, comparaison avec une prévision naïve (« l'an prochain = cette année »).

## 5.4 La fiche d'alerte du directeur régional

Chaque région dispose d'une fiche d'une page, générée à la demande par l'application. Elle contient :

- le **niveau de risque** (code couleur) et le score, en précisant s'il s'agit d'une valeur observée ou d'une prévision ;
- les **principaux facteurs** de risque ;
- l'**évolution du score** depuis 2016 (barres pleines : observé ; barre vide : prévision) ;
- les **indicateurs clés** de la dernière année, par sexe ;
- des **actions recommandées** adaptées au niveau de risque ;
- les **sources** et la date de génération.

`[À COMPLÉTER]` Insérer la capture d'une fiche (avec données réelles).

# 6. La réponse au défi

## 6.1 Comment la solution aide un décideur

| Avant | Avec EduAlert BF |
|---|---|
| Lecture d'un annuaire de plusieurs centaines de pages, tableau par tableau | Une carte : les régions critiques ressortent en rouge en quelques secondes |
| Le décrochage est constaté après coup | Une prévision pour l'année scolaire suivante, avant la rentrée |
| Chaque direction fait ses propres calculs | Un indicateur commun, calculé de la même manière pour toutes les régions |
| Rapport à rédiger pour alerter | Fiche d'une page prête à transmettre |

**Exemple d'usage :** en juillet, à la publication des statistiques, la DGESS met à jour les données et relance la chaîne
(une commande). Le directeur régional ouvre la carte, voit sa région passer en « Critique », télécharge sa fiche et l'utilise
pour justifier une demande de renforcement des cantines ou d'enseignants avant la rentrée d'octobre.

## 6.2 Limites

- Analyse **régionale** : une région « modérée » peut cacher des provinces ou des communes critiques.
- Indicateurs **indirects** du décrochage, faute de taux d'abandon publié par région.
- Peu d'années d'historique et rupture de 2022/23 : la prévision doit être lue comme une **alerte**, pas comme un chiffre exact.
- Les recommandations sont des **pistes génériques** par niveau de risque, à valider par les services techniques.

## 6.3 La suite possible

1. **Descendre au niveau province puis commune** dès que la DGESS rend ces données disponibles ; la table de correspondance et
   le format long le permettent sans refonte.
2. **Intégrer les données de vie scolaire** (absentéisme, résultats trimestriels) remontées par les établissements, pour une alerte
   infra-annuelle.
3. **Basculer sur le découpage en 17 régions** grâce à la table de correspondance.
4. **Mise à jour automatique** à chaque nouvel annuaire et hébergement par le ministère.

# 7. La reproduction

**Prérequis :** Python 3.11 ou plus récent. Aucune base de données à installer.

**Lancer la solution :**

| Système | Commande, à la racine du projet |
|---|---|
| Windows | `run.bat` (ou double-clic) |
| Linux / macOS | `sh run.sh` |

Puis ouvrir `http://localhost:8000/docs` (API) `[À COMPLÉTER : adresse de la carte]`.

**Ce que fait le script, dans l'ordre :**

1. crée l'environnement Python du projet et installe les dépendances (`backend/requirements.txt`) ;
2. reconstruit les contours des 13 régions à partir du Data Pack s'il est présent (`pipeline/geo_regions.py`) ;
3. charge les indicateurs et les scores de risque dans la base SQLite (`backend/app/charger.py`) ;
4. démarre l'API (`backend/app/main.py`).

**Ordre complet de la chaîne de données :**

| Étape | Script | Produit |
|---|---|---|
| 1. Collecte | `[À COMPLÉTER – Membre 2]` | `data/01_collecte/` |
| 2. Nettoyage | `[À COMPLÉTER – Membre 2]` | `data/02_nettoyage/` |
| 3. Transformation | `[À COMPLÉTER – Membre 2]`, `pipeline/geo_regions.py` | `indicateurs.csv`, `regions13.geojson` |
| 4. Analyse | `[À COMPLÉTER – Membre 2]` | `risque.csv` |
| 5. Visualisation | `run.bat` | API, carte, fiches PDF |

Le code est déposé sous `AB7C-938F-79BB_05-interpretation_D1_architect_code-api-backend-pipeline_vN.zip` ;
le fichier `README.md` reprend ces instructions.

# Annexe – Usage de l'intelligence artificielle

Conformément aux règles du challenge, nous déclarons notre usage d'outils d'IA.

| Ce que nous avons demandé | Ce que nous avons retenu |
|---|---|
| Analyse du document du challenge et proposition d'un plan de travail | Le planning et la répartition des rôles, après adaptation par l'équipe |
| Aide à l'écriture du code de l'API, du script de fusion des régions, de la fiche PDF et des scripts de lancement | Le code, relu, testé et compris par l'équipe |
| Aide à la structuration de cette documentation | La structure ; les contenus d'analyse et les chiffres proviennent exclusivement de nos scripts |

L'outil a consulté la **structure** du fichier DGESS (noms des tableaux, en-têtes et premières lignes) pour proposer une démarche.
Le nettoyage et le traitement des données complètes ont été réalisés par l'équipe sur ses propres postes.
`[À COMPLÉTER – Membre 2 : son propre usage éventuel de l'IA]`
