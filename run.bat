@echo off
REM ==========================================================
REM  EduAlert BF - lancement en une commande (Windows)
REM  1) cree l'environnement Python si besoin
REM  2) installe les dependances
REM  3) construit les contours des regions (si Data Pack present)
REM  4) rejoue le pipeline de donnees (si le fichier source est present)
REM  5) charge les donnees dans SQLite
REM  6) demarre l'application sur http://localhost:8000/app/
REM ==========================================================
cd /d "%~dp0backend"

if not exist .venv (
    echo [1/6] Creation de l'environnement virtuel...
    python -m venv .venv || goto :erreur
)
echo [2/6] Installation des dependances...
.venv\Scripts\python -m pip install -q -r requirements.txt || goto :erreur

if exist "..\DataPack_DCB_2026" (
    echo [3/6] Construction des contours des 13 regions...
    .venv\Scripts\python ..\pipeline\geo_regions.py || goto :erreur
) else (
    echo [3/6] Data Pack absent : on garde data\03_transformation\regions13.geojson deja fourni.
)

if exist "..\data\00_sources\DGESS_prescolaire_primaire_2016_2025.xlsx" (
    echo [4/6] Preparation des donnees ^(nettoyage, indicateurs, risque^)...
    .venv\Scripts\python ..\pipeline\executer_pipeline.py || echo Pipeline non rejoue : on garde les CSV existants.
) else (
    echo [4/6] Fichier source absent : on garde les CSV deja presents dans data\.
)

echo [5/6] Chargement des donnees dans SQLite...
.venv\Scripts\python -m app.charger || goto :erreur

echo.
echo [6/6] Application demarree :
echo        Carte : http://localhost:8000/app/
echo        API   : http://localhost:8000/docs
echo        (Ctrl+C pour arreter)
echo.
.venv\Scripts\python -m uvicorn app.main:app --port 8000
goto :eof

:erreur
echo.
echo ERREUR : une etape a echoue. Lire le message ci-dessus.
pause
exit /b 1
