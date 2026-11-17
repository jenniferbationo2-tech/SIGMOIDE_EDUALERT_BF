# EduAlert BF

Plateforme prédictive et cartographie des risques de décrochage scolaire au Burkina Faso.
Data Challenge Burkina 2026 – Édition Éducation – **Défi 1**.

## Structure

```
data/        01_collecte → 05_interpretation (une étape = un dossier)
pipeline/    scripts de traitement relançables
backend/     API FastAPI (Membre 1)
frontend/    application Vue + Leaflet (Membre 2)
docs/        documentation, dictionnaire des variables, journal de nettoyage
```

## Équipe

- Membre 1 : data et backend (API, intégration cartographique, base de données)
- Membre 2 : data science, analyse, frontend

## Reproduction

**Prérequis :** Python 3.11 ou plus récent.

**Lancement en une commande :**

| Système | Commande (à la racine du projet) |
|---|---|
| Windows | double-clic sur `run.bat` (ou `run.bat` dans un terminal) |
| Linux / macOS | `sh run.sh` |

Puis ouvrir **http://localhost:8000/docs**.

Le script enchaîne : création de l'environnement Python → installation des dépendances →
contours des régions (si le Data Pack est présent) → chargement des données dans SQLite → démarrage de l'API.

**Étapes manuelles (équivalent) :**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
python ../pipeline/geo_regions.py # optionnel : seulement si DataPack_DCB_2026/ est présent
python -m app.charger             # CSV -> SQLite (prend les vrais CSV, sinon les données d'exemple)
uvicorn app.main:app --reload
```

**Ordre de la chaîne de données :**
1. `pipeline/geo_regions.py` : 17 nouvelles régions COD-AB → 13 anciennes régions (`data/03_transformation/regions13.geojson`)
2. Nettoyage et indicateurs (Membre 2) → `data/03_transformation/indicateurs.csv`
3. Modèle de risque (Membre 2) → `data/04_analyse/risque.csv`
4. `backend/app/charger.py` → base `backend/edualert.sqlite`
5. API `backend/app/main.py` → carte (frontend) et fiches PDF

Tant que les CSV des étapes 2 et 3 sont absents, l'API sert des **données fictives**
(`backend/donnees_exemple/`), signalées par `GET /sante` et sur les fiches PDF.

## API

| Endpoint | Rôle |
|---|---|
| `GET /regions` | Liste des 13 régions |
| `GET /annees` | Années disponibles |
| `GET /geo/regions` | Contours GeoJSON (Leaflet) |
| `GET /indicateurs?annee=&region=&indicateur=&sexe=` | Indicateurs filtrés |
| `GET /risque?annee=` | Score et niveau de risque par région (couleurs de la carte) |
| `GET /regions/{code}/fiche` | Fiche détaillée d'une région (JSON) |
| `GET /regions/{code}/fiche.pdf` | Fiche d'une page pour le directeur régional |
| `GET /sante` | État du service et origine des données |

Détails des données : [docs/dictionnaire_donnees.md](docs/dictionnaire_donnees.md).

## Scripts de livrables

Ces scripts produisent les livrables à partir de la chaîne déjà calculée. Chacun
**refuse de produire une sortie** dont les données ne correspondent pas à ce qui est
annoncé, plutôt que d'écrire un fichier plausible et faux.

| Script | Produit | Prérequis |
|---|---|---|
| `pipeline/exporter_fiches.py` | Les 13 fiches PDF régionales | Aucun (pas de serveur à démarrer) |
| `pipeline/graphiques.py` | Les 6 figures de la documentation | — |
| `pipeline/captures.mjs` | Les 5 captures de l'application (`node`) | L'application doit tourner sur le port 8000 |
| `pipeline/recadrer_fiche.py` | Le recadrage de la fiche pour le document | La capture 03 doit exister |
| `pipeline/exporter_documentation.py` | `docs/documentation_EduAlertBF.pdf` | — |
| `pipeline/verifier_documentation.py` | Contrôle : chaque chiffre cité contre son fichier source | — |

## Dépôts sur la plateforme

`backend/.venv/Scripts/python pipeline/preparer_depots.py --version 1` crée le dossier `depots/`
avec les fichiers nommés selon le règlement (`AB7C-938F-79BB_ETAPE_D1_ROLE_description_vN`).
