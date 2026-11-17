"""Etape 05 - Recadrage de la fiche pour la documentation.

La capture pleine page de la fiche depasse 5 000 px de haut : inseree dans
un document A4, elle occuperait une page entiere et serait illisible. La
documentation n'a besoin que du haut de la fiche (titre, score, phrase de
synthese, causes, evolution).

    python pipeline/recadrer_fiche.py

Les coordonnees de la decoupe sont MESUREES dans la page, jamais ecrites
en dur : la mise en page evolue, et un recadrage fige finit par montrer
autre chose que ce qu'annonce son nom — sans qu'aucune erreur ne le
signale.

Entree : l'application en fonctionnement sur le port 8000
Sortie : data/05_interpretation/captures/03-fiche-haut-doc.png
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "05_interpretation" / "captures" / "03-fiche-haut-doc.png"
NODE_MODULES = Path("/root/edualert/shots/node_modules")

# Script de mesure + capture : Playwright lit lui-meme la position du bloc
# de la fiche, puis photographie exactement cette zone.
SCRIPT = r"""
import { chromium } from 'playwright-core';

const CHROME = process.env.CHROME_BIN
  || '/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome';
const BASE = process.env.EDUALERT_URL || 'http://127.0.0.1:8000';
const SORTIE = process.argv[2];

const navigateur = await chromium.launch({
  executablePath: CHROME, args: ['--no-sandbox', '--font-render-hinting=none'],
});
const ctx = await navigateur.newContext({
  viewport: { width: 1366, height: 900 }, deviceScaleFactor: 2, locale: 'fr-FR',
});
const page = await ctx.newPage();

await page.goto(`${BASE}/app/`, { waitUntil: 'networkidle' });
await page.waitForFunction(
  () => document.querySelectorAll('.tableau-classement tbody tr').length === 13,
  null, { timeout: 20000 });

// Region la plus exposee : premiere ligne du classement.
await page.locator('.tableau-classement tbody tr').first().click();
await page.waitForFunction(
  () => (document.querySelector('.synthese')?.innerText || '').trim().length > 40,
  null, { timeout: 10000 });
await page.waitForTimeout(900);

// L'encadre d'aide est replie : il n'a rien a faire dans une capture de fiche.
await page.evaluate(() => {
  const b = document.querySelector('.aide__bouton');
  if (b && b.getAttribute('aria-expanded') === 'true') b.click();
});
await page.waitForTimeout(400);

// Mesure : du haut du panneau de la fiche jusqu'a la fin du graphique,
// en coordonnees ABSOLUES de page (et non du viewport).
const zone = await page.evaluate(() => {
  const panneau = document.querySelector('.colonne-panneau .bloc');
  const graphique = document.querySelector('.graphique');
  const note = document.querySelector('.note-graphique');
  if (!panneau || !graphique) return null;
  const haut = panneau.getBoundingClientRect().top + window.scrollY;
  const bas = (note || graphique).getBoundingClientRect().bottom + window.scrollY;
  const p = panneau.getBoundingClientRect();
  return {
    x: p.x + window.scrollX,
    y: haut,
    largeur: p.width,
    hauteur: bas - haut + 14,
  };
});

if (!zone) { console.log('ECHEC: bloc de la fiche introuvable'); process.exit(1); }

// `fullPage: true` est INDISPENSABLE avec `clip` : sans lui, le clip est
// interprete dans la fenetre visible, et toute zone situee plus bas que
// 900 px donne une capture decalee — nette, mais du mauvais contenu.
await page.screenshot({
  path: SORTIE,
  fullPage: true,
  clip: { x: zone.x, y: zone.y, width: zone.largeur, height: zone.hauteur },
});
console.log(JSON.stringify(zone));
await navigateur.close();
"""


def main() -> int:
    script = RACINE / "pipeline" / "_recadrage.mjs"
    lien = RACINE / "pipeline" / "node_modules"
    script.write_text(SCRIPT, encoding="utf-8")
    cree_lien = False
    # `exists()` suit le lien : il est FAUX pour un lien symbolique casse,
    # et `symlink_to` echoue alors sur un fichier qui existe bel et bien.
    if not lien.is_symlink() and not lien.exists():
        lien.symlink_to(NODE_MODULES)
        cree_lien = True

    SORTIE.unlink(missing_ok=True)   # jamais laisser passer une capture perimee
    try:
        res = subprocess.run(["node", str(script), str(SORTIE)],
                             cwd=RACINE / "pipeline",
                             capture_output=True, text=True, timeout=300)
    finally:
        script.unlink(missing_ok=True)
        if cree_lien:
            lien.unlink(missing_ok=True)

    if res.returncode != 0 or not SORTIE.exists():
        print("ECHEC : aucune capture produite.")
        print((res.stdout + res.stderr)[-700:])
        return 1

    try:
        zone = json.loads(res.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        zone = {}

    octets = SORTIE.stat().st_size
    if octets < 20_000:
        print(f"ECHEC : sortie de {octets} octets, probablement vide")
        SORTIE.unlink(missing_ok=True)
        return 1

    # Garde de forme : une zone plus large que haute, ou minuscule, signale
    # que la mesure a attrape le mauvais bloc.
    hauteur = zone.get("hauteur", 0)
    largeur = zone.get("largeur", 0)
    if hauteur < 400 or largeur < 300:
        print(f"ECHEC : zone mesuree aberrante ({largeur:.0f} x {hauteur:.0f} px)")
        SORTIE.unlink(missing_ok=True)
        return 1

    print(f"ok  {SORTIE.relative_to(RACINE)}  "
          f"zone mesuree {largeur:.0f} x {hauteur:.0f} px  {octets // 1024} Ko")
    return 0


if __name__ == "__main__":
    sys.exit(main())
