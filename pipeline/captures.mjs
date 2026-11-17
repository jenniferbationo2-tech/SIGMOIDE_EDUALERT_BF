/**
 * Captures d'ecran de l'application EduAlert BF, pour la documentation.
 *
 * Chaque capture passe des GARDES avant d'etre ecrite sur le disque :
 * un fichier manquant se voit, une image fausse passe inapercue.
 *
 *   node pipeline/captures.mjs
 *
 * Prerequis : l'application tourne sur http://127.0.0.1:8000/app/
 * Sortie    : data/05_interpretation/captures/
 */
import { chromium } from 'playwright-core';
import { mkdirSync, statSync } from 'node:fs';

const CHROME = process.env.CHROME_BIN
  || '/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome';
const BASE = process.env.EDUALERT_URL || 'http://127.0.0.1:8000';
const URL_APP = `${BASE}/app/`;
const OUT = new URL('../data/05_interpretation/captures/', import.meta.url).pathname;

const TAILLE_MIN = 20_000;   // en octets : sous ce seuil, l'image est vide
const produites = [];
const refusees = [];

mkdirSync(OUT, { recursive: true });

const navigateur = await chromium.launch({
  executablePath: CHROME,
  args: ['--no-sandbox', '--font-render-hinting=none'],
});

/** Etat de la page, lu en un seul passage pour eviter deux lectures desynchronisees. */
const lireEtat = (page) => page.evaluate(() => ({
  largeurCss: document.documentElement.clientWidth,
  debordement: Math.max(
    0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
  texte: document.body.innerText,
  polygones: document.querySelectorAll('#carte path').length,
  // On compte les elements que l'ecran porte REELLEMENT. La vue carte est
  // sobre a dessein (un curseur, un tableau, deux liens) : un seuil global
  // sur « button,input,a » la refuserait alors qu'elle est parfaitement juste.
  interactifs: document.querySelectorAll(
    'input,button,select,a,.ligne-cliquable,#carte path').length,
  lignesClassement: document.querySelectorAll('.tableau-classement tbody tr').length,
  pointilles: Array.from(document.querySelectorAll('#carte path'))
    .filter((p) => (p.getAttribute('stroke-dasharray') || '').trim() !== '').length,
  chargement: document.querySelectorAll('.etat-chargement').length,
}));

/**
 * Capture un ecran. `temoins` sont des chaines que SEUL cet ecran affiche ;
 * `controle` recoit l'etat lu et rend une raison de refus, ou null.
 */
async function capturer({ fichier, largeur, hauteur, preparer, temoins = [],
                          controle, pleinePage = true }) {
  const ctx = await navigateur.newContext({
    viewport: { width: largeur, height: hauteur },
    deviceScaleFactor: 2,
    locale: 'fr-FR',
    timezoneId: 'Africa/Ouagadougou',
  });
  const page = await ctx.newPage();
  const erreursConsole = [];
  page.on('console', (m) => { if (m.type() === 'error') erreursConsole.push(m.text()); });

  const refuser = async (raison) => {
    refusees.push({ fichier, raison });
    console.log(`REFUSE  ${fichier.padEnd(34)} ${raison}`);
    await ctx.close();
    return false;
  };

  const reponse = await page.goto(URL_APP, { waitUntil: 'networkidle' });

  // Garde 1 : on a bien atterri sur l'ecran demande (une redirection repond 200)
  if (reponse.status() !== 200) return refuser(`code HTTP ${reponse.status()}`);
  if (new URL(page.url()).pathname !== '/app/') {
    return refuser(`redirige vers ${new URL(page.url()).pathname}`);
  }

  // Garde 2 : la carte est reellement dessinee (13 regions), pas un squelette
  await page.waitForSelector('#carte path', { state: 'attached', timeout: 20_000 });
  await page.waitForFunction(
    () => document.querySelectorAll('#carte path').length >= 13, null, { timeout: 20_000 });
  await page.waitForFunction(
    () => document.querySelectorAll('.etat-chargement').length === 0,
    null, { timeout: 20_000 });

  if (preparer) await preparer(page);

  const etat = await lireEtat(page);

  // Garde 3 : la mise en page a suivi l'emulation (sinon : bureau comprime)
  if (Math.abs(etat.largeurCss - largeur) > 20) {
    return refuser(`largeur CSS ${etat.largeurCss} au lieu de ${largeur}`);
  }
  // Garde 4 : ecran peuple et interactif, pas une page d'erreur
  if (etat.interactifs < 5) return refuser(`seulement ${etat.interactifs} elements interactifs`);
  if (etat.chargement > 0) return refuser('un etat de chargement est encore affiche');
  if (/Erreur|impossible de charger/i.test(etat.texte.slice(0, 400))) {
    return refuser('message d erreur en haut de page');
  }
  // Garde 5 : temoins propres a cet ecran, comparaison INSENSIBLE A LA CASSE
  for (const t of temoins) {
    if (!etat.texte.toLowerCase().includes(t.toLowerCase())) {
      return refuser(`temoin absent : « ${t} »`);
    }
  }
  // Garde 6 : controle specifique a l'ecran
  const raison = controle ? controle(etat) : null;
  if (raison) return refuser(raison);

  const chemin = `${OUT}${fichier}`;
  await page.screenshot({ path: chemin, fullPage: pleinePage });

  // Garde 7 : taille plausible, lue APRES ecriture
  const octets = statSync(chemin).size;
  if (octets < TAILLE_MIN) return refuser(`fichier de ${octets} octets, trop petit`);

  produites.push({ fichier, octets, largeur, debordement: etat.debordement });
  const alerte = erreursConsole.length ? ` [console: ${erreursConsole.length}]` : '';
  console.log(`ok      ${fichier.padEnd(34)} ${(octets / 1024).toFixed(0)} Ko  `
    + `largeur CSS ${etat.largeurCss}  debordement ${etat.debordement} px${alerte}`);
  await ctx.close();
  return true;
}

/** Deplace le curseur d'annee et attend que l'interface ait suivi. */
const choisirAnnee = (annee) => async (page) => {
  await page.locator('#curseur-annee').evaluate((el, a) => {
    el.value = String(a);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }, annee);
  await page.waitForFunction(
    (a) => (document.querySelector('.valeur-annee')?.innerText || '').includes(String(a)),
    annee, { timeout: 10_000 });
  await page.waitForTimeout(900);   // laisse la carte se recolorer
};

/** Ouvre la fiche d'une region en cliquant sa ligne dans le classement. */
const ouvrirFiche = (rang) => async (page) => {
  const ligne = page.locator('.tableau-classement tbody tr').nth(rang);
  await ligne.click();
  await page.waitForSelector('.bouton-retour', { state: 'visible', timeout: 10_000 });
  await page.waitForFunction(
    () => (document.querySelector('.score-grand')?.innerText || '').trim().length > 0,
    null, { timeout: 10_000 });
  await page.waitForTimeout(700);
};

const ECRANS = [
  {
    fichier: '01-carte-2025-observe.png',
    largeur: 1366, hauteur: 900,
    preparer: choisirAnnee(2025),
    temoins: ['EduAlert BF', 'Classement 2025', 'Niveau de risque'],
    controle: (e) => (e.polygones < 13 ? `${e.polygones} polygones` : null)
      || (e.lignesClassement !== 13 ? `${e.lignesClassement} lignes de classement` : null)
      || (e.pointilles > 0 ? `${e.pointilles} contours en pointilles sur une annee observee` : null)
      || (/prévision du modèle/i.test(e.texte) ? 'mention de prevision sur 2025' : null),
  },
  {
    fichier: '02-carte-2026-prevision.png',
    largeur: 1366, hauteur: 900,
    preparer: choisirAnnee(2026),
    temoins: ['Classement 2026', 'Prévision du modèle', 'Fiabilité de la prévision'],
    // Sur 2026, les 13 contours doivent etre en pointilles : c'est le seul
    // marqueur visuel, le modele retenu reprenant les scores de 2025.
    controle: (e) => (e.pointilles < 13
      ? `seulement ${e.pointilles} contours en pointilles sur 13` : null),
  },
  {
    fichier: '03-fiche-region-critique.png',
    largeur: 1366, hauteur: 900,
    preparer: async (page) => { await choisirAnnee(2025)(page); await ouvrirFiche(0)(page); },
    temoins: ['Centre-Nord', 'Facteurs principaux', 'Évolution du score',
              'Actions recommandées'],
    controle: (e) => (/Critique/.test(e.texte) ? null : 'niveau Critique absent de la fiche'),
  },
  {
    fichier: '04-fiche-region-faible.png',
    largeur: 1366, hauteur: 900,
    preparer: async (page) => { await choisirAnnee(2025)(page); await ouvrirFiche(12)(page); },
    temoins: ['Facteurs principaux', 'Indicateurs clés'],
    controle: (e) => (/Faible/.test(e.texte) ? null : 'niveau Faible absent de la fiche'),
  },
  {
    fichier: '05-ecran-etroit-390.png',
    largeur: 390, hauteur: 844,
    preparer: choisirAnnee(2025),
    temoins: ['EduAlert BF', 'Classement 2025'],
    // Sur telephone, le defaut qui compte est le debordement lateral.
    controle: (e) => (e.debordement > 2 ? `debordement horizontal de ${e.debordement} px` : null),
  },
];

for (const ecran of ECRANS) await capturer(ecran);
await navigateur.close();

console.log('\n--- bilan ---');
console.log(`produites : ${produites.length} / ${ECRANS.length}`);
for (const r of refusees) console.log(`refusee   : ${r.fichier} — ${r.raison}`);
if (produites.length !== ECRANS.length) {
  console.log('\nECHEC : au moins une capture a ete refusee.');
  process.exit(1);
}
console.log('Toutes les captures ont passe les gardes.');
