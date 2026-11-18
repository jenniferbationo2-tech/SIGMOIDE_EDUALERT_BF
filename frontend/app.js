/* ==========================================================================
   EduAlert BF — logique de l'interface
   --------------------------------------------------------------------------
   Vue 3 sans compilation, Leaflet pour la carte. Toutes les adresses d'API
   sont RELATIVES : l'application fonctionne derriere n'importe quel nom de
   domaine sans reconfiguration.
   ========================================================================== */

const { createApp } = Vue;

// Echelle de risque. Ces couleurs ne servent QU'aux donnees : les couleurs
// d'identite (vert institutionnel, jaune) ne doivent jamais arriver ici.
const COULEURS_RISQUE = {
  faible: '#4C9A72',
  modere: '#E0A43A',
  critique: '#B3261E',
};

const LIBELLES_NIVEAU = { faible: 'Faible', modere: 'Modéré', critique: 'Critique' };

const LIBELLES_FACTEURS = {
  ecart_admission_achevement: "Écart entre l'entrée au CP1 et la fin du primaire",
  faible_achevement: "Peu d'élèves terminent le primaire",
  recul_effectifs: 'Élèves perdus depuis le meilleur niveau',
  fermeture_ecoles: "Écoles fermées depuis le meilleur niveau",
  faible_scolarisation: 'Peu d\'enfants scolarisés',
  disparite_filles_garcons: 'Écart entre filles et garçons',
  aucun_facteur_marquant: 'Aucun facteur marquant',
};

// libelle court + pictogramme : dans le classement, la cause tient dans une
// puce au lieu d'une phrase.
const FACTEURS_COURTS = {
  ecart_admission_achevement: { libelle: 'Décrochage en cycle', icone: 'tendance' },
  faible_achevement: { libelle: 'Achèvement faible', icone: 'tendance' },
  recul_effectifs: { libelle: 'Effectifs en recul', icone: 'personnes' },
  fermeture_ecoles: { libelle: 'Écoles fermées', icone: 'ecole' },
  faible_scolarisation: { libelle: 'Peu scolarisés', icone: 'personnes' },
  disparite_filles_garcons: { libelle: 'Écart filles-garçons', icone: 'parite' },
  aucun_facteur_marquant: { libelle: 'Aucun facteur', icone: 'neutre' },
};

const ICONES_FACTEURS = {
  ecole: 'M2 6.6 8 3l6 3.6V13H2V6.6zm3 1.6v3.2h2V8.2H5zm4 0v3.2h2V8.2H9z',
  personnes: 'M6 7.4a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4zM1.8 13.2c0-2.1 1.9-3.4 4.2-3.4s4.2 1.3 4.2 3.4H1.8zm8.6-6.3a1.8 1.8 0 1 0 0-3.6 1.8 1.8 0 0 0 0 3.6zM11 13.2c0-1.5.5-2.6 1.4-3.1 1.7.3 2.8 1.4 2.8 3.1H11z',
  tendance: 'M1.4 12.1 6.2 7.3l2.3 2.3 5-5 1 1-6 6-2.3-2.3-3.8 3.8-1-1z',
  parite: 'M7.4 2h1.2v12H7.4V2zM4.6 6.6 2 11.4h5.2L4.6 6.6zm6.8 0-2.6 4.8H14l-2.6-4.8z',
  neutre: 'M8 3.2a4.8 4.8 0 1 0 0 9.6 4.8 4.8 0 0 0 0-9.6zm0 1.4a3.4 3.4 0 1 1 0 6.8 3.4 3.4 0 0 1 0-6.8z',
};


/* ==========================================================================
   Placement des etiquettes de region
   --------------------------------------------------------------------------
   Le centre geometrique d'un polygone tombe souvent sur un bord ou hors du
   trace (forme concave, region en croissant). On cherche donc le point le
   plus eloigne des bords — « pole of inaccessibility », approche polylabel —
   par une grille grossiere puis un raffinement local. Le resultat tient dans
   le polygone, au plus large, sans dependance externe.
   ========================================================================== */

/** Aire signee positive d'un anneau [lon, lat]. */
function aireAnneau(anneau) {
  let somme = 0;
  for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
    somme += (anneau[j][0] * anneau[i][1]) - (anneau[i][0] * anneau[j][1]);
  }
  return Math.abs(somme / 2);
}

function pointDansAnneau(x, y, anneau) {
  let dedans = false;
  for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
    const [xi, yi] = anneau[i];
    const [xj, yj] = anneau[j];
    const croise = ((yi > y) !== (yj > y))
      && (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi);
    if (croise) dedans = !dedans;
  }
  return dedans;
}

function distanceSegment(px, py, a, b) {
  const [ax, ay] = a;
  const [bx, by] = b;
  const dx = bx - ax;
  const dy = by - ay;
  const long2 = (dx * dx) + (dy * dy);
  const t = long2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / long2)) : 0;
  return Math.hypot(px - (ax + (t * dx)), py - (ay + (t * dy)));
}

/** Point interieur le plus eloigne des bords, en [lon, lat]. */
function pointEtiquette(anneau) {
  let minX = Infinity; let minY = Infinity;
  let maxX = -Infinity; let maxY = -Infinity;
  anneau.forEach(([x, y]) => {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  });

  const distanceAuBord = (x, y) => {
    let d = Infinity;
    for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
      d = Math.min(d, distanceSegment(x, y, anneau[j], anneau[i]));
    }
    return d;
  };

  const essais = 22;
  let x = (minX + maxX) / 2;
  let y = (minY + maxY) / 2;
  let d = -1;

  for (let ix = 0; ix <= essais; ix += 1) {
    for (let iy = 0; iy <= essais; iy += 1) {
      const cx = minX + ((maxX - minX) * ix) / essais;
      const cy = minY + ((maxY - minY) * iy) / essais;
      if (!pointDansAnneau(cx, cy, anneau)) continue;
      const cd = distanceAuBord(cx, cy);
      if (cd > d) { x = cx; y = cy; d = cd; }
    }
  }

  let pas = Math.max((maxX - minX) / essais, (maxY - minY) / essais) / 2;
  const directions = [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, 1], [-1, 1], [1, -1]];
  while (pas > 0.002) {
    let ameliore = false;
    for (const [dx, dy] of directions) {
      const nx = x + (dx * pas);
      const ny = y + (dy * pas);
      if (!pointDansAnneau(nx, ny, anneau)) continue;
      const nd = distanceAuBord(nx, ny);
      if (nd > d) { x = nx; y = ny; d = nd; ameliore = true; }
    }
    if (!ameliore) pas /= 2;
  }
  return [x, y];
}


/* ==========================================================================
   Pastille d'aide
   --------------------------------------------------------------------------
   Les explications ne vivent plus dans le flux : elles s'ouvrent sous une
   pastille « ? » posee contre le libelle concerne. Une seule ouverte a la
   fois, fermeture par Echap, clic exterieur ou defilement.
   ========================================================================== */

const etatAide = Vue.reactive({ actif: null });

const PastilleAide = {
  props: {
    identifiant: { type: String, required: true },
    titre: { type: String, required: true },
    texte: { type: String, required: true },
  },
  data() {
    return { ouvert: false, position: {} };
  },
  computed: {
    doitFermer() { return etatAide.actif !== this.identifiant; },
  },
  watch: {
    doitFermer(fermer) { if (fermer) this.ouvert = false; },
  },
  methods: {
    basculer() {
      if (this.ouvert) { this.fermer(); return; }
      etatAide.actif = this.identifiant;
      this.ouvert = true;
      this.$nextTick(this.placer);
    },
    /** Position fixe calculee depuis le bouton, rabattue dans la fenetre. */
    placer() {
      const bouton = this.$el.getBoundingClientRect();
      const largeur = Math.min(300, window.innerWidth - 24);
      this.position = {
        left: `${Math.max(12, Math.min(bouton.left, window.innerWidth - largeur - 12))}px`,
        top: `${Math.min(bouton.bottom + 8, window.innerHeight - 170)}px`,
        width: `${largeur}px`,
      };
    },
    fermer() { this.ouvert = false; },
    surEchap(evenement) { if (evenement.key === 'Escape') this.fermer(); },
    surExterieur(evenement) {
      if (this.ouvert && !this.$el.contains(evenement.target)) this.fermer();
    },
    surDefilement() { if (this.ouvert) this.fermer(); },
  },
  mounted() {
    document.addEventListener('keydown', this.surEchap);
    document.addEventListener('click', this.surExterieur, true);
    window.addEventListener('scroll', this.surDefilement, true);
    window.addEventListener('resize', this.surDefilement);
  },
  beforeUnmount() {
    document.removeEventListener('keydown', this.surEchap);
    document.removeEventListener('click', this.surExterieur, true);
    window.removeEventListener('scroll', this.surDefilement, true);
    window.removeEventListener('resize', this.surDefilement);
  },
  template: `
    <span class="pastille-aide">
      <button type="button" class="pastille-aide__bouton"
              :aria-expanded="ouvert ? 'true' : 'false'"
              :aria-label="'Aide : ' + titre"
              @click.stop="basculer">?</button>
      <span v-if="ouvert" class="pastille-aide__panneau" role="tooltip" :style="position">
        <span class="pastille-aide__titre">{{ titre }}</span>
        <span class="pastille-aide__texte">{{ texte }}</span>
      </span>
    </span>`,
};


// Indicateurs montres dans la fiche, avec le sens de lecture : `hautBon`
// indique si une valeur elevee est une BONNE nouvelle. Sans cette precision,
// la colonne « ecart » colorerait en vert un retard et en rouge une avance.
const INDICATEURS_FICHE = [
  { code: 'taux_achevement',         libelle: "Taux d'achèvement",        hautBon: true,  echelle: 100 },
  { code: 'taux_brut_admission',     libelle: "Taux brut d'admission",    hautBon: true,  echelle: 100 },
  { code: 'taux_brut_scolarisation', libelle: 'Taux brut de scolarisation', hautBon: true, echelle: 100 },
  { code: 'taux_reussite_cep',       libelle: 'Taux de réussite au CEP',  hautBon: true,  echelle: 100 },
  { code: 'ecart_tba_tap',           libelle: 'Écart admission − achèvement', hautBon: false, echelle: 100 },
  // Ceux-ci n'ont pas de plafond naturel : l'echelle est relative a la plus
  // grande des deux valeurs (region ou moyenne).
  { code: 'eleves_par_ecole',        libelle: 'Élèves par école',         hautBon: false },
  { code: 'ips_tap',                 libelle: 'Indice de parité',         hautBon: true,  echelle: 2 },
];

const application = createApp({
  data() {
    return {
      annees: [],
      annee: null,
      anneePrevision: null,
      premiereAnnee: null,
      classement: [],
      classementPrecedent: [],
      // Scores de toutes les regions et toutes les annees (mini-courbes).
      historique: [],
      fiche: null,
      sante: {},
      modele: {},
      incertitudes: {},
      // Indicateurs de TOUTES les regions pour l'annee courante : sert au
      // bandeau de chiffres cles et aux moyennes de comparaison.
      indicateurs: [],
      anneeIndicateurs: null,
      chargement: true,
      erreur: '',
      // Vue affichee : la carte du pays ou le classement. Chacune occupe sa
      // propre page ; la fiche region s'ouvre par-dessus et revient a la vue
      // d'ou l'on vient.
      onglet: 'carte',
      ongletPrecedent: 'carte',
      ordreNiveaux: ['critique', 'modere', 'faible'],
      // Type de graphique choisi pour la courbe d'evolution (memorise).
      typeGraphique: 'barres',
      partageOuvert: false,
      lienCopie: false,
      carte: null,
      coucheRegions: null,
      etiquettes: [],
      geojson: null,
    };
  },

  computed: {
    estPrevision() { return this.annee === this.anneePrevision; },

    nbCritiques() {
      return this.classement.filter((r) => this.classeNiveau(r.niveau) === 'critique').length;
    },

    /** Somme, sur les 13 regions, des eleves non encore retrouves. */
    elevesEnMoins() { return this.manquantDepuisLePic('effectif_primaire', 'recul_effectif_primaire_vs_pic'); },

    ecolesEnMoins() { return this.manquantDepuisLePic('nombre_ecoles', 'recul_nombre_ecoles_vs_pic'); },

    /** Nombre de regions qui changent de niveau par rapport a l'annee N-1. */
    nbChangements() {
      if (!this.classementPrecedent.length) return 0;
      const avant = {};
      this.classementPrecedent.forEach((r) => { avant[r.region_code] = r.niveau; });
      return this.classement.filter(
        (r) => avant[r.region_code] && avant[r.region_code] !== r.niveau).length;
    },

    ficheScore() {
      return this.fiche && this.fiche.risque_actuel ? this.fiche.risque_actuel.score : 0;
    },

    ficheNiveau() {
      return this.fiche && this.fiche.risque_actuel ? this.fiche.risque_actuel.niveau : '';
    },

    facteursFiche() {
      if (!this.fiche || !this.fiche.risque_actuel) return [];
      return (this.fiche.risque_actuel.facteurs || '').split(';').filter(Boolean);
    },

    incertitudeFiche() {
      if (!this.fiche || !this.fiche.risque_actuel) return null;
      if (!this.fiche.risque_actuel.est_prevision) return null;
      return this.incertitudes[this.fiche.region_code] || null;
    },

    /** Nombre de regions par niveau : alimente la legende et les onglets. */
    repartition() {
      const compte = { faible: 0, modere: 0, critique: 0 };
      this.classement.forEach((r) => { compte[this.classeNiveau(r.niveau)] += 1; });
      return compte;
    },

    /** Toutes les annees d'une region, dans l'ordre. */
    seriesParRegion() {
      const par = {};
      this.historique.forEach((h) => {
        (par[h.region_code] = par[h.region_code] || []).push(h);
      });
      return par;
    },

    /** Causes de la fiche, en puces courtes avec pictogramme. */
    causesCourtes() {
      const actuel = this.fiche && this.fiche.risque_actuel;
      return this.facteursCourts(actuel ? actuel.facteurs : '');
    },

    /** Le classement, enrichi de la mini-courbe de chaque region. */
    classementCourbes() {
      return this.classement.map((ligne) => ({
        ...ligne,
        courbe: this.miniCourbe(ligne.region_code),
      }));
    },

    /** Pistes d'action a plat : une action par carte numerotee. */
    actionsCartes() {
      if (!this.fiche) return [];
      const cartes = [];
      (this.fiche.recommandations || []).forEach((texte) => {
        cartes.push({ titre: 'Priorité régionale', texte });
      });
      (this.fiche.actions_par_facteur || []).forEach((bloc) => {
        bloc.actions.forEach((texte) => cartes.push({ titre: bloc.libelle, texte }));
      });
      return cartes.map((carte, i) => ({ ...carte, num: i + 1 }));
    },

    /**
     * Courbe d'evolution de la region, en coordonnees SVG 600 x 200.
     * Meme echelle que la carte (0-100) : la lecture reste comparable.
     */
    courbeFiche() {
      const serie = (this.fiche && this.fiche.historique_risque) || [];
      if (!serie.length) return null;
      const largeurTotale = 600;
      const hauteurTotale = 200;
      const zone = { x: 34, y: 12, largeur: largeurTotale - 34 - 14, hauteur: hauteurTotale - 12 - 30 };
      const points = serie.map((h, i) => {
        const x = zone.x + (zone.largeur * i) / Math.max(1, serie.length - 1);
        const y = zone.y + zone.hauteur
          - (Math.max(0, Math.min(100, h.score)) / 100) * zone.hauteur;
        return {
          x: +x.toFixed(1),
          y: +y.toFixed(1),
          annee: h.annee,
          score: h.score,
          niveau: h.niveau,
          prevision: Boolean(h.est_prevision),
        };
      });
      return {
        points,
        trace: points.map((p) => `${p.x},${p.y}`).join(' '),
        dernier: points[points.length - 1],
        avantDernier: points.length > 1 ? points[points.length - 2] : null,
        zone,
        grille: [0, 25, 50, 75, 100].map((v) => ({
          v,
          y: zone.y + zone.hauteur - (v / 100) * zone.hauteur,
        })),
      };
    },

    /** Adresse partagee : la fiche PDF si une region est ouverte, sinon la page. */
    lienPartage() {
      if (this.fiche) {
        return new URL(`../regions/${this.fiche.region_code}/fiche.pdf`, window.location.href).href;
      }
      return `${window.location.origin}${window.location.pathname}`;
    },

    messagePartage() {
      const sujet = this.fiche
        ? `EduAlert BF — fiche ${this.fiche.region_nom}`
        : `EduAlert BF — risque de décrochage scolaire ${this.annee}`;
      const corps = this.fiche
        ? `${this.fiche.region_nom} : score de risque ${this.nombreFr(this.ficheScore, 1)} sur 100, `
          + `niveau ${this.libelleNiveau(this.ficheNiveau).toLowerCase()}.\n\nFiche : ${this.lienPartage}`
        : `Carte et classement du risque de décrochage scolaire par région, ${this.annee}.`
          + `\n\n${this.lienPartage}`;
      return { sujet, corps };
    },

    lienGmail() {
      const { sujet, corps } = this.messagePartage;
      return 'https://mail.google.com/mail/?view=cm&fs=1'
        + `&su=${encodeURIComponent(sujet)}&body=${encodeURIComponent(corps)}`;
    },

    lienOutlook() {
      const { sujet, corps } = this.messagePartage;
      return 'https://outlook.live.com/mail/0/deeplink/compose'
        + `?subject=${encodeURIComponent(sujet)}&body=${encodeURIComponent(corps)}`;
    },

    /** Écart de score entre la région la plus et la moins exposée. */
    ecartExtremes() {
      if (this.classement.length < 2) return 0;
      return this.classement[0].score - this.classement[this.classement.length - 1].score;
    },

    /**
     * Phrase de synthese construite a partir des donnees, jamais ecrite a la
     * main : annee, niveau, score, tendance depuis le dernier changement de
     * niveau, et les deux causes principales.
     */
    phraseSynthese() {
      if (!this.fiche || !this.fiche.risque_actuel) return '';
      const actuel = this.fiche.risque_actuel;
      const niveau = this.libelleNiveau(actuel.niveau).toLowerCase();
      const score = this.nombreFr(actuel.score, 1);
      const nom = this.fiche.region_nom;
      const quand = actuel.est_prevision
        ? `En ${actuel.annee} (prévision)`
        : `En ${actuel.annee}`;

      let tendance = '';
      const histo = this.fiche.historique_risque || [];
      if (histo.length >= 2) {
        const dernier = histo[histo.length - 1];
        // On remonte tant que le niveau est le meme : donne l'annee a partir
        // de laquelle la region est dans sa situation actuelle.
        let depuis = dernier.annee;
        for (let i = histo.length - 2; i >= 0; i -= 1) {
          if (histo[i].niveau !== dernier.niveau) break;
          depuis = histo[i].annee;
        }
        const premier = histo[0];
        const ecart = dernier.score - premier.score;
        if (depuis > premier.annee) {
          tendance = `, ${ecart >= 0 ? 'en hausse' : 'en baisse'} depuis ${depuis}`;
        } else if (Math.abs(ecart) >= 3) {
          tendance = ecart > 0 ? ', en hausse sur la période' : ', en baisse sur la période';
        } else {
          tendance = ', stable sur la période';
        }
      }

      const causes = this.facteursFiche.slice(0, 2)
        .map((c) => this.minusculeInitiale(this.libelleFacteur(c)));
      const phraseCauses = causes.length
        ? ` Principales causes : ${causes.join(' ; ')}.`
        : '';

      const sujet = this.sujetRegion(nom);
      return `${quand}, ${sujet.groupe} ${sujet.verbe} en risque ${niveau} `
        + `(${score}/100)${tendance}.${phraseCauses}`;
    },

    /** Indicateurs de la region, confrontes a la moyenne des 13 regions. */
    indicateursCompares() {
      if (!this.fiche) return [];
      const valeurs = {};
      (this.fiche.indicateurs || []).forEach((i) => {
        if (i.sexe === 'T') valeurs[i.indicateur] = i.valeur;
      });

      return INDICATEURS_FICHE.map((def) => {
        const valeur = valeurs[def.code];
        if (valeur === undefined || valeur === null) return null;
        const moyenne = this.moyenneNationale(def.code);
        if (moyenne === null) return null;
        const ecart = valeur - moyenne;
        // Defavorable = la region est du mauvais cote de la moyenne.
        const defavorable = def.hautBon ? ecart < 0 : ecart > 0;
        return { ...def, valeur, moyenne, ecart, defavorable };
      }).filter(Boolean);
    },

    phraseFiabilite() {
      const nom = (this.modele.modele_retenu || '').toLowerCase();
      const erreur = this.modele.mae_moyenne_glissante;
      if (!erreur) return '';
      const methode = nom.includes('naive')
        ? `La prévision ${this.anneePrevision} reprend le score de ${this.anneePrevision - 1} : `
          + 'testée sur les trois dernières années, cette méthode simple s\'est révélée '
          + 'plus juste que les deux modèles statistiques essayés'
        : `La prévision ${this.anneePrevision} vient du modèle « ${this.modele.modele_retenu} »`;
      return `${methode}. En moyenne, elle se trompe d'environ `
        + `${this.nombreFr(erreur, 1)} points de score sur 100. `
        + 'À lire comme une alerte, pas comme une certitude.';
    },
  },

  watch: {
    /**
     * La fiche est une page autonome : le bandeau de chiffres, le selecteur
     * d'annee et le glossaire disparaissent autour d'elle. La classe est
     * posee sur <body> et non sur #application : Vue ne traite pas les
     * attributs de l'element sur lequel il est monte.
     */
    fiche(ouverte) {
      document.body.classList.toggle('mode-fiche', Boolean(ouverte));
    },
  },

  methods: {
    /** Nombre au format francais : virgule decimale, espace pour les milliers. */
    nombreFr(valeur, decimales = 1) {
      if (valeur === null || valeur === undefined || Number.isNaN(valeur)) return '—';
      return Number(valeur).toLocaleString('fr-FR', {
        minimumFractionDigits: decimales,
        maximumFractionDigits: decimales,
      });
    },

    classeNiveau(niveau) {
      const n = (niveau || '').toLowerCase();
      if (n.startsWith('crit')) return 'critique';
      if (n.startsWith('mod')) return 'modere';
      return 'faible';
    },

    libelleNiveau(niveau) { return LIBELLES_NIVEAU[this.classeNiveau(niveau)]; },

    couleurNiveau(niveau) { return COULEURS_RISQUE[this.classeNiveau(niveau)]; },

    seuilNiveau(niveau) {
      return {
        critique: '66 et plus',
        modere: '33 à 66',
        faible: 'moins de 33',
      }[this.classeNiveau(niveau)];
    },

    changerOnglet(nom) {
      this.onglet = nom;
      if (nom !== 'carte') return;
      // La carte etait masquee : Leaflet a perdu ses dimensions, il faut les
      // remesurer avant de recadrer.
      this.$nextTick(() => {
        if (!this.carte) return;
        this.carte.invalidateSize({ pan: false });
        this.cadrer();
      });
    },

    libelleFacteur(code) {
      if (!code) return '—';
      return LIBELLES_FACTEURS[code] || code.replace(/_/g, ' ');
    },

    /**
     * Met l'initiale en minuscule sans toucher au reste : un `toLowerCase()`
     * global transformerait « CP1 » en « cp1 » et « CEP » en « cep ».
     */
    minusculeInitiale(texte) {
      if (!texte) return '';
      return texte.charAt(0).toLowerCase() + texte.slice(1);
    },

    /**
     * Article defini + verbe accorde devant un nom de region, pour que la
     * phrase de synthese se lise en francais correct. Verifie sur les 13
     * regions : « l'Est », « les Cascades SONT », « la Boucle du Mouhoun ».
     * Rend { groupe, verbe } car le pluriel change aussi le verbe.
     */
    sujetRegion(nom) {
      if (!nom) return { groupe: '', verbe: 'est' };
      const pluriels = ['Hauts-Bassins', 'Cascades'];
      const feminins = ['Boucle du Mouhoun'];
      if (pluriels.includes(nom)) return { groupe: `les ${nom}`, verbe: 'sont' };
      if (feminins.includes(nom)) return { groupe: `la ${nom}`, verbe: 'est' };
      // Elision devant une voyelle ou un h muet : « l'Est ».
      if (/^[AEIOUYÉÈÊÀÂÎÔÛH]/i.test(nom)) return { groupe: `l'${nom}`, verbe: 'est' };
      return { groupe: `le ${nom}`, verbe: 'est' };
    },

    /** Deux puces courtes (libelle + pictogramme), pour le classement. */
    facteursCourts(facteurs) {
      return (facteurs || '').split(';').filter(Boolean).slice(0, 2).map((code) => {
        const court = FACTEURS_COURTS[code]
          || { libelle: code.replace(/_/g, ' '), icone: 'neutre' };
        return {
          code,
          libelle: court.libelle,
          icone: ICONES_FACTEURS[court.icone] || ICONES_FACTEURS.neutre,
        };
      });
    },

    /**
     * Courbe des scores d'une region, en coordonnees SVG 96 x 26.
     * L'echelle est commune a toutes les regions (0-100) : deux courbes se
     * comparent donc d'une ligne a l'autre, au lieu d'etre recadrees chacune.
     */
    miniCourbe(code) {
      const serie = this.seriesParRegion[code] || [];
      if (serie.length < 2) return null;
      const largeur = 96;
      const hauteur = 26;
      const marge = 3;
      const points = serie.map((h, i) => {
        const x = marge + ((largeur - 2 * marge) * i) / (serie.length - 1);
        const y = hauteur - marge
          - (Math.max(0, Math.min(100, h.score)) / 100) * (hauteur - 2 * marge);
        return { x: +x.toFixed(1), y: +y.toFixed(1) };
      });
      const fin = points[points.length - 1];
      return {
        points: points.map((p) => `${p.x},${p.y}`).join(' '),
        finX: fin.x,
        finY: fin.y,
        debut: serie[0].annee,
        debutScore: serie[0].score,
        dernier: fin.annee,
        dernierScore: fin.score,
      };
    },

    ariaCourbe(ligne) {
      const c = ligne.courbe;
      if (!c) return '';
      return `Score de ${this.nombreFr(c.debutScore, 1)} en ${c.debut} `
        + `à ${this.nombreFr(c.dernierScore, 1)} en ${c.dernier}`;
    },

    /** Echelle commune aux deux barres (region et moyenne) d'un indicateur. */
    echelleIndicateur(ind) {
      const max = Math.max(Math.abs(ind.valeur || 0), Math.abs(ind.moyenne || 0));
      // Un taux brut peut depasser 100 : l'echelle suit alors la valeur, sinon
      // le trait de la moyenne sortirait de la piste.
      const base = ind.echelle || 0;
      return Math.max(base, max * 1.05) || 1;
    },

    /** Écart signé, sans « -0,0 » : un écart nul s'écrit 0,0. */
    formatEcart(ecart) {
      if (Math.abs(ecart) < 0.05) return '0,0';
      return `${ecart > 0 ? '+' : ''}${this.nombreFr(ecart, 1)}`;
    },

    largeurIndicateur(ind) {
      return Math.min(100, (Math.abs(ind.valeur) / this.echelleIndicateur(ind)) * 100);
    },

    largeurMoyenne(ind) {
      return Math.min(100, (Math.abs(ind.moyenne) / this.echelleIndicateur(ind)) * 100);
    },

    /**
     * Somme du manque depuis le pic, en valeur absolue.
     * Le CSV donne un POURCENTAGE de recul ; on le reconvertit en effectif a
     * partir de la valeur de l'annee, sinon on additionnerait des pourcentages.
     */
    manquantDepuisLePic(codeValeur, codeRecul) {
      let total = 0;
      const parRegion = {};
      this.indicateurs.forEach((i) => {
        if (i.sexe !== 'T') return;
        if (i.indicateur !== codeValeur && i.indicateur !== codeRecul) return;
        parRegion[i.region_code] = parRegion[i.region_code] || {};
        parRegion[i.region_code][i.indicateur] = i.valeur;
      });
      Object.values(parRegion).forEach((r) => {
        const actuel = r[codeValeur];
        const reculPct = r[codeRecul];
        if (actuel === undefined || reculPct === undefined) return;
        const perte = -reculPct;                        // le CSV stocke un nombre negatif
        if (perte <= 0) return;                         // region au-dessus de son pic
        const pic = actuel / (1 - perte / 100);
        total += pic - actuel;
      });
      return Math.round(total);
    },

    /** Moyenne d'un indicateur sur les 13 regions, sexe « Total ». */
    moyenneNationale(code) {
      const valeurs = this.indicateurs
        .filter((i) => i.indicateur === code && i.sexe === 'T' && i.valeur !== null)
        .map((i) => i.valeur);
      if (!valeurs.length) return null;
      return valeurs.reduce((a, b) => a + b, 0) / valeurs.length;
    },

    /**
     * Imprimer, c'est imprimer le PDF de la fiche, pas la page web : le
     * navigateur ouvre le PDF dans un onglet, pret a sortir sur papier.
     */
    imprimer() {
      if (!this.fiche) return;
      const url = new URL(`../regions/${this.fiche.region_code}/fiche.pdf`,
        window.location.href).href;
      window.open(url, '_blank', 'noopener');
    },

    choisirGraphique(type) {
      this.typeGraphique = type;
      try { localStorage.setItem('edualert-graphique', type); } catch (e) { /* navigation privee */ }
    },

    basculerPartage() {
      this.partageOuvert = !this.partageOuvert;
      this.lienCopie = false;
    },

    fermerPartage() { this.partageOuvert = false; },

    async copierLien() {
      try {
        await navigator.clipboard.writeText(this.lienPartage);
        this.lienCopie = true;
      } catch (e) {
        // Navigateur sans presse-papiers : on selectionne l'adresse a la main.
        this.lienCopie = false;
      }
    },

    ouvrirGlossaire() {
      const panneau = this.$refs.glossaire;
      if (panneau && !panneau.open) panneau.showModal();
    },

    fermerGlossaire() {
      const panneau = this.$refs.glossaire;
      if (panneau && panneau.open) panneau.close();
    },

    async json(chemin) {
      const reponse = await fetch(chemin);
      if (!reponse.ok) throw new Error(`${chemin} : ${reponse.status}`);
      return reponse.json();
    },

    async choisirAnnee(a) {
      this.annee = a;
      await this.chargerAnnee();
    },

    /** Charge le classement, l'annee precedente et les indicateurs. */
    async chargerAnnee() {
      try {
        this.chargement = true;
        const [courant, indicateurs] = await Promise.all([
          this.json(`../risque?annee=${this.annee}`),
          this.json(`../indicateurs?annee=${this.anneeDonnees()}`),
        ]);
        this.classement = courant;
        this.indicateurs = indicateurs;

        if (this.annee > this.premiereAnnee) {
          try {
            this.classementPrecedent = await this.json(`../risque?annee=${this.annee - 1}`);
          } catch (e) {
            this.classementPrecedent = [];
          }
        } else {
          this.classementPrecedent = [];
        }

        this.dessinerRegions();
        this.erreur = '';
      } catch (e) {
        this.erreur = `Impossible de charger les données de ${this.annee}. `
          + 'Vérifiez que le service est démarré, puis rechargez la page.';
      } finally {
        this.chargement = false;
      }
    },

    /**
     * Les indicateurs s'arretent a la derniere annee OBSERVEE : demander
     * l'annee de prevision renverrait une liste vide et mettrait tous les
     * chiffres cles a zero.
     */
    anneeDonnees() {
      return this.estPrevision ? this.anneePrevision - 1 : this.annee;
    },

    async ouvrirFiche(code) {
      try {
        this.ongletPrecedent = this.onglet;
        this.fiche = await this.json(`../regions/${code}/fiche`);
        this.mettreEnValeur(code);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (e) {
        this.erreur = `Impossible d'ouvrir la fiche de ${code}.`;
      }
    },

    ouvrirFicheDepuisListe(evenement) {
      const code = evenement.target.value;
      if (code) this.ouvrirFiche(code); else this.fermerFiche();
    },

    fermerFiche() {
      this.fiche = null;
      this.onglet = this.ongletPrecedent || 'carte';
      this.dessinerRegions();
      // La carte vient de reapparaitre : ses dimensions ont change.
      this.$nextTick(() => {
        if (!this.carte) return;
        this.carte.invalidateSize({ pan: false });
        this.cadrer();
      });
    },

    mettreEnValeur(code) {
      if (!this.coucheRegions) return;
      this.coucheRegions.eachLayer((couche) => {
        const estCelle = couche.feature.properties.region_code === code;
        couche.setStyle({ weight: estCelle ? 3.5 : this.epaisseur(couche.feature) });
      });
    },

    epaisseur(feature) {
      const ligne = this.classement.find((r) => r.region_code === feature.properties.region_code);
      // Contour renforce pour les regions critiques : la couleur seule ne
      // suffit pas a les faire ressortir d'un coup d'oeil.
      return ligne && this.classeNiveau(ligne.niveau) === 'critique' ? 2.2 : 1;
    },

    styleRegion(feature, parCode) {
      const ligne = parCode[feature.properties.region_code];
      return {
        fillColor: ligne ? this.couleurNiveau(ligne.niveau) : '#D5DBE0',
        fillOpacity: 0.92,
        color: this.estPrevision ? '#1F3A2C' : '#FFFFFF',
        weight: this.epaisseur(feature),
        dashArray: this.estPrevision ? '6 4' : null,
        lineJoin: 'round',
      };
    },

    dessinerRegions() {
      if (!this.carte || !this.geojson) return;

      if (this.coucheRegions) this.carte.removeLayer(this.coucheRegions);
      this.etiquettes.forEach((e) => this.carte.removeLayer(e));
      this.etiquettes = [];

      const parCode = {};
      this.classement.forEach((r) => { parCode[r.region_code] = r; });

      this.coucheRegions = L.geoJSON(this.geojson, {
        style: (feature) => this.styleRegion(feature, parCode),
        onEachFeature: (feature, couche) => {
          const code = feature.properties.region_code;
          const ligne = parCode[code];
          const nom = (ligne && ligne.region_nom) || feature.properties.region_nom || code;
          if (ligne) {
            couche.bindTooltip(
              `<span class="infobulle__nom">${nom}</span>`
              + `<span class="infobulle__score">${this.nombreFr(ligne.score, 1)}`
              + '<small>/100</small></span>'
              + `<span class="infobulle__niveau">${this.libelleNiveau(ligne.niveau)}</span>`
              + '<span class="infobulle__aide">Cliquez pour ouvrir la fiche</span>',
              { sticky: true, direction: 'top', className: 'infobulle-carte', opacity: 1 });
          }
          // Survol : la region se detache (contour sombre, teinte pleine).
          couche.on('mouseover', () => {
            couche.setStyle({ weight: 2.6, color: '#12331F', fillOpacity: 1 });
            couche.bringToFront();
          });
          couche.on('mouseout', () => {
            if (this.coucheRegions) this.coucheRegions.resetStyle(couche);
          });
          couche.on('click', () => this.ouvrirFiche(code));
          couche.on('keydown', (e) => { if (e.originalEvent.key === 'Enter') this.ouvrirFiche(code); });
        },
      }).addTo(this.carte);

      this.cadrer();
      this.poserEtiquettes(parCode);
    },

    /**
     * Nom et score de chaque region, poses au point le plus large du polygone.
     * Trois tailles selon l'aire : une petite region recoit un nom seul, sans
     * score, pour ne pas deborder sur sa voisine.
     */
    poserEtiquettes(parCode) {
      this.coucheRegions.eachLayer((couche) => {
        const code = couche.feature.properties.region_code;
        const ligne = parCode[code];
        const nom = (ligne && ligne.region_nom) || couche.feature.properties.region_nom || code;

        const geometrie = couche.feature.geometry;
        const anneaux = geometrie.type === 'Polygon'
          ? [geometrie.coordinates[0]]
          : geometrie.coordinates.map((polygone) => polygone[0]);

        let anneau = anneaux[0];
        anneaux.forEach((candidat) => {
          if (aireAnneau(candidat) > aireAnneau(anneau)) anneau = candidat;
        });
        const aire = aireAnneau(anneau);
        const [lon, lat] = pointEtiquette(anneau);

        const taille = aire > 1.2 ? 'grande' : (aire > 0.4 ? 'moyenne' : 'petite');
        const score = ligne ? Math.round(ligne.score) : null;
        const contenu = `<span class="etiquette-region__nom">${nom}</span>`
          + (score !== null && taille !== 'petite'
            ? `<span class="etiquette-region__score">${score}</span>`
            : '');

        const etiquette = L.tooltip({
          permanent: true,
          direction: 'center',
          opacity: 1,
          className: `etiquette-region etiquette-region--${taille}`,
        })
          .setContent(contenu)
          .setLatLng([lat, lon]);

        etiquette.addTo(this.carte);
        this.etiquettes.push(etiquette);
      });
    },

    cadrer() {
      if (!this.coucheRegions) return;
      // Sans animation : la projection doit etre definitive avant que les
      // etiquettes soient posees, sinon elles se decalent vers l'exterieur.
      this.carte.fitBounds(this.coucheRegions.getBounds(), {
        padding: [8, 8],
        maxZoom: 8,
        animate: false,
      });
    },

    /** Re-pose les etiquettes apres un changement de taille de la carte. */
    replacerEtiquettes() {
      if (!this.carte || !this.coucheRegions) return;
      this.etiquettes.forEach((e) => this.carte.removeLayer(e));
      this.etiquettes = [];
      const parCode = {};
      this.classement.forEach((r) => { parCode[r.region_code] = r; });
      this.poserEtiquettes(parCode);
    },

    async monte() {
      try {
        const [sante, annees, geojson] = await Promise.all([
          this.json('../sante'),
          this.json('../annees'),
          this.json('../geo/regions'),
        ]);
        this.sante = sante;
        this.annees = annees;
        this.geojson = geojson;

        try {
          const choisi = localStorage.getItem('edualert-graphique');
          if (['barres', 'courbe', 'tableau'].includes(choisi)) this.typeGraphique = choisi;
        } catch (e) { /* navigation privee : on garde les barres */ }

        // Historique complet, pour les mini-courbes du classement. Son absence
        // ne doit pas empecher la carte de s'afficher.
        try {
          this.historique = await this.json('../risque/historique');
        } catch (e) {
          this.historique = [];
        }
        this.premiereAnnee = Math.min(...annees);
        this.anneePrevision = Math.max(...annees);
        // On ouvre sur la derniere annee OBSERVEE, pas sur la prevision : un
        // chiffre prevu ne doit pas etre la premiere chose que l'on voit.
        this.annee = this.anneePrevision - 1;
        this.anneeIndicateurs = this.annee;

        this.carte = L.map('carte', {
          zoomControl: false,              // remplace par un controle place a la main
          attributionControl: false,
          scrollWheelZoom: false,          // evite de zoomer par accident en faisant defiler
          zoomSnap: 0.1,
          zoomDelta: 0.5,
          minZoom: 5,
          maxZoom: 9,
          zoomAnimation: true,
        });
        L.control.zoom({ position: 'topright', zoomInTitle: 'Agrandir', zoomOutTitle: 'Réduire' })
          .addTo(this.carte);
        L.control.scale({ position: 'bottomright', imperial: false, maxWidth: 110 })
          .addTo(this.carte);

        try {
          this.modele = await this.json('../modele');
          // La cle est « incertitude_2026 » dans le contrat de l'API ; on
          // garde une solution de repli si elle est un jour renommee.
          const inc = this.modele.incertitude_2026 || this.modele.incertitude || [];
          inc.forEach((i) => { this.incertitudes[i.region_code] = i; });
        } catch (e) { this.modele = {}; }

        await this.chargerAnnee();

        // La hauteur du cadre depend de la fenetre : on remesure une fois la
        // mise en page stabilisee, puis on redessine etiquettes comprises.
        const recaler = () => {
          if (!this.carte) return;
          this.carte.invalidateSize({ pan: false });
          this.cadrer();
          this.replacerEtiquettes();
        };
        this.$nextTick(recaler);
        window.addEventListener('resize', recaler);
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(recaler);

        // Une variation de la taille du cadre (en-tete, zoom navigateur,
        // barre d'adresse mobile) laissait la carte rognee : on l'observe.
        if ('ResizeObserver' in window) {
          let derniere = '';
          this._tailleObserver = new ResizeObserver(() => {
            const el = document.getElementById('carte');
            if (!el) return;
            const taille = `${el.clientWidth}x${el.clientHeight}`;
            if (taille === derniere) return;
            derniere = taille;
            recaler();
          });
          this._tailleObserver.observe(document.getElementById('carte'));
        }
      } catch (e) {
        this.chargement = false;
        this.erreur = 'Impossible de contacter le service. Vérifiez qu\'il est démarré '
          + '(run.sh ou run.bat), puis rechargez la page.';
      }
    },
  },

  mounted() {
    this.monte();

    // Le menu de partage se ferme au clic exterieur et sur Echap.
    document.addEventListener('click', (evenement) => {
      if (this.partageOuvert && !evenement.target.closest('.partage')) {
        this.partageOuvert = false;
      }
    });
    document.addEventListener('keydown', (evenement) => {
      if (evenement.key === 'Escape') this.partageOuvert = false;
    });
  },
});
application.component('pastille-aide', PastilleAide);
application.mount('#application');
