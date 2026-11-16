@echo off
REM ==========================================================
REM  EduAlert BF - lancement en une commande (Windows)
REM  1) cree l'environnement Python si besoin
REM  2) installe les dependances
REM  3) construit les contours des regions (si Data Pack present)
REM  4) charge les donnees dans SQLite
REM  5) demarre l'API sur http://localhost:8000/docs
REM ==========================================================
cd /d "%~dp0backend"

if not exist .venv (
    echo [1/5] Creation de l'environnement virtuel...
    python -m venv .venv || goto :erreur
)
echo [2/5] Installation des dependances...
.venv\Scripts\python -m pip install -q -r requirements.txt || goto :erreur

if exist "..\DataPack_DCB_2026" (
    echo [3/5] Construction des contours des 13 regions...
    .venv\Scripts\python ..\pipeline\geo_regions.py || goto :erreur
) else (
    echo [3/5] Data Pack absent : on garde data\03_transformation\regions13.geojson deja fourni.
)

echo [4/5] Chargement des donnees dans SQLite...
.venv\Scripts\python -m app.charger || goto :erreur

echo [5/5] API demarree : http://localhost:8000/docs  (Ctrl+C pour arreter)
.venv\Scripts\python -m uvicorn app.main:app --port 8000
goto :eof

:erreur
echo.
echo ERREUR : une etape a echoue. Lire le message ci-dessus.
pause
exit /b 1
