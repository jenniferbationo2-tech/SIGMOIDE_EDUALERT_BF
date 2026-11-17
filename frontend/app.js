/* EduAlert BF - logique de l'application (Vue 3 sans etape de compilation).

   Regle de l'equipe : l'interface n'appelle QUE l'API, jamais un fichier de
   donnees directement.

   Endpoints utilises : /sante, /annees, /regions, /geo/regions, /risque,
   /modele, /regions/{code}/fiche, /regions/{code}/fiche.pdf
*/
'use strict';

// L'application est servie par l'API elle-meme sur /app/ : l'API est donc a la
// racine du meme domaine. En developpement (fichier ouvert directement), on
// retombe sur le port 8000 en local.
const BASE_API = (window.location.protocol === 'file:')
  ? 'http://localhost:8000'
  : window.location.origin;

const COULEURS_NIVEAU = {
  Faible: '#4C9A72',
  Modere: '#E0A43A',
  Critique: '#C2412D',
};

const LIBELLES_FACTEURS = {
  ecart_admission_achevement: "Écart entre admission et achèvement",
  faible_achevement: "Faible taux d'achèvement",
  recul_effectifs: "Élèves perdus depuis le pic",
  fermeture_ecoles: "Fermetures d'écoles",
  faible_scolarisation: "Faible scolarisation",
  disparite_filles_garcons: "Inégalité filles-garçons",
  aucun_facteur_marquant: "Aucun facteur marquant",
};

const LIBELLES_NIVEAUX = {
  Faible: 'Faible',
  Modere: 'Modéré',
  Critique: 'Critique',
};

// Indicateurs montres dans la fiche, dans cet ordre.
const INDICATEURS_FICHE = [
  ['taux_achevement', "Taux d'achèvement (%)"],
  ['taux_brut_admission', "Taux brut d'admission (%)"],
  ['taux_brut_scolarisation', 'Taux brut de scolarisation (%)'],
  ['taux_reussite_cep', 'Taux de réussite au CEP (%)'],
  ['effectif_primaire', 'Effectif du primaire'],
  ['nouveaux_inscrits_cp1', 'Nouveaux inscrits au CP1'],
  ['nombre_ecoles', "Nombre d'écoles"],
  ['eleves_par_ecole', 'Élèves par école'],
  ['ecart_tba_tap', 'Écart admission - achèvement (points)'],
  ['recul_effectif_primaire_vs_pic', 'Élèves perdus depuis le pic (%)'],
  ['recul_nombre_ecoles_vs_pic', 'Écoles fermées depuis le pic (%)'],
  ['ips_tap', "Indice de parité F/G (achèvement)"],
];

const SEUIL_CRITIQUE = 66;

async function recuperer(chemin) {
  const reponse = await fetch(BASE_API + chemin);
  if (!reponse.ok) {
    throw new Error(`L'API a répondu ${reponse.status} pour ${chemin}`);
  }
  return reponse.json();
}

const { createApp } = Vue;

createApp({
  data() {
    return {
      sante: {},
      annees: [],
      annee: null,
      risques: [],
      modele: {},
      regionChoisie: null,
      fiche: null,
      carte: null,
      coucheRegions: null,
      geojson: null,
      chargement: true,
      erreur: '',
    };
  },

  computed: {
    donneesFictives() {
      return this.sante.source_risque && this.sante.source_risque !== 'reel';
    },
    anneeMin() { return this.annees.length ? Math.min(...this.annees) : 2017; },
    anneeMax() { return this.annees.length ? Math.max(...this.annees) : 2026; },
    estPrevision() {
      return this.risques.some((r) => r.est_prevision);
    },
    classement() {
      return [...this.risques].sort((a, b) => b.score - a.score);
    },
    parCode() {
      const index = {};
      this.risques.forEach((r) => { index[r.region_code] = r; });
      return index;
    },
    incertitudes() {
      const index = {};
      (this.modele.incertitude_2026 || []).forEach((i) => {
        index[i.region_code] = i;
      });
      return index;
    },
    phraseFiabilite() {
      const nom = (this.modele.modele_retenu || '').toLowerCase();
      const erreur = this.modele.mae_moyenne_glissante;
      if (!erreur) return '';
      const methode = nom.includes('naive')
        ? "La prévision 2026 reprend le score de 2025 : testée sur les trois "
          + "dernières années, cette méthode simple s'est révélée plus juste que "
          + 'les deux modèles statistiques essayés'
        : `La prévision 2026 vient du modèle « ${this.modele.modele_retenu} »`;
      return `${methode}. En moyenne, elle se trompe d'environ `
        + `${this.nombreFr(erreur, 1)} points de score sur 100. `
        + "À lire comme une alerte, pas comme une certitude.";
    },
    ficheScore() {
      return this.fiche && this.fiche.risque_actuel
        ? this.fiche.risque_actuel.score : 0;
    },
    ficheNiveau() {
      return this.fiche && this.fiche.risque_actuel
        ? this.fiche.risque_actuel.niveau : 'Faible';
    },
    facteursFiche() {
      if (!this.fiche || !this.fiche.risque_actuel) return [];
      return (this.fiche.risque_actuel.facteurs || '')
        .split(';').filter((code) => code.length);
    },
    indicateursCles() {
      if (!this.fiche) return [];
      const table = {};
      this.fiche.indicateurs.forEach((ligne) => {
        table[ligne.indicateur] = table[ligne.indicateur] || {};
        table[ligne.indicateur][ligne.sexe] = ligne.valeur;
      });
      return INDICATEURS_FICHE
        .filter(([code]) => table[code])
        .map(([code, libelle]) => ({
          code,
          libelle,
          G: this.valeurOuTiret(table[code].G, code),
          F: this.valeurOuTiret(table[code].F, code),
          T: this.valeurOuTiret(table[code].T, code),
        }));
    },
    urlFichePdf() {
      return `${BASE_API}/regions/${this.regionChoisie}/fiche.pdf`;
    },
    // La fiche de l'API decrit la situation la plus recente de la region. Pour
    // eviter toute confusion avec l'annee du curseur, on rappelle l'annee
    // affichee sur la carte des qu'elle differe.
    pointAnneeChoisie() {
      if (!this.fiche || !this.fiche.historique_risque) return null;
      const point = this.fiche.historique_risque.find((p) => p.annee === this.annee);
      return point || null;
    },
    anneeFicheDifferente() {
      return Boolean(
        this.fiche && this.fiche.risque_actuel && this.pointAnneeChoisie
        && this.pointAnneeChoisie.annee !== this.fiche.risque_actuel.annee,
      );
    },
    largeurSvg() {
      const nombre = this.fiche ? this.fiche.historique_risque.length : 10;
      return this.margeSvg + nombre * this.pasSvg + 6;
    },
    margeSvg() { return 22; },
    pasSvg() { return 40; },
    descriptionGraphique() {
      if (!this.fiche) return '';
      const points = this.fiche.historique_risque
        .map((p) => `${p.annee} : ${Math.round(p.score)}`)
        .join(', ');
      return `Évolution du score de risque. ${points}.`;
    },
  },

  watch: {
    annee() { this.chargerRisque(); },
  },

  mounted() {
    this.chargerTout();
  },

  methods: {
    nombreFr(valeur, decimales) {
      if (valeur === null || valeur === undefined || Number.isNaN(valeur)) {
        return '—';
      }
      return Number(valeur).toLocaleString('fr-FR', {
        minimumFractionDigits: decimales,
        maximumFractionDigits: decimales,
      });
    },

    valeurOuTiret(valeur, code) {
      if (valeur === null || valeur === undefined) return '—';
      // Les ratios se lisent a 2 decimales, les taux a 1, les effectifs entiers.
      if (code.startsWith('ips_')) return this.nombreFr(valeur, 2);
      if (Number.isInteger(valeur)) return this.nombreFr(valeur, 0);
      return this.nombreFr(valeur, 1);
    },

    classeNiveau(niveau) {
      return (niveau || '').toLowerCase().replace('é', 'e');
    },

    libelleNiveau(niveau) { return LIBELLES_NIVEAUX[niveau] || niveau; },

    couleurNiveau(niveau) { return COULEURS_NIVEAU[niveau] || '#8A9099'; },

    libelleFacteur(code) {
      if (!code) return '—';
      return LIBELLES_FACTEURS[code] || code.replace(/_/g, ' ');
    },

    premierFacteur(facteurs) {
      return (facteurs || '').split(';')[0] || '';
    },

    incertitudeDe(code) { return this.incertitudes[code] || null; },

    // Region « proche du seuil » : son intervalle probable chevauche 66.
    procheDuSeuil(code) {
      const borne = this.incertitudes[code];
      if (!borne) return false;
      return borne.score_bas < SEUIL_CRITIQUE && borne.score_haut >= SEUIL_CRITIQUE;
    },

    async chargerTout() {
      this.erreur = '';
      this.chargement = true;
      try {
        const [sante, annees, geojson] = await Promise.all([
          recuperer('/sante'),
          recuperer('/annees'),
          recuperer('/geo/regions'),
        ]);
        this.sante = sante;
        this.annees = annees;
        this.geojson = geojson;
        // Par defaut : la derniere annee observee, pas la prevision.
        this.annee = annees.filter((a) => a <= 2025).pop() || annees[annees.length - 1];
        try {
          this.modele = await recuperer('/modele');
        } catch (erreur) {
          this.modele = {};     // l'application reste utilisable sans /modele
        }
        this.initialiserCarte();
        await this.chargerRisque();
      } catch (erreur) {
        this.erreur = "Impossible de contacter l'API EduAlert BF. "
          + 'Vérifiez que le serveur est démarré (run.bat ou run.sh), '
          + `puis réessayez. Détail : ${erreur.message}`;
      } finally {
        this.chargement = false;
      }
    },

    async chargerRisque() {
      if (!this.annee) return;
      this.chargement = true;
      try {
        this.risques = await recuperer(`/risque?annee=${this.annee}`);
        this.dessinerRegions();
      } catch (erreur) {
        this.erreur = `Pas de données de risque pour ${this.annee}. `
          + `Détail : ${erreur.message}`;
      } finally {
        this.chargement = false;
      }
    },

    initialiserCarte() {
      if (this.carte) return;
      // Fond neutre, sans tuiles : l'application fonctionne hors ligne.
      // zoomSnap sous 1 : fitBounds peut alors remplir le cadre au lieu de
      // laisser une bande vide (le pays est plus large que haut).
      this.carte = L.map('carte', {
        zoomControl: true,
        attributionControl: false,
        scrollWheelZoom: false,
        zoomSnap: 0.15,
        zoomDelta: 0.5,
      });
      this.carte.setView([12.3, -1.6], 6);
    },

    dessinerRegions() {
      if (!this.carte || !this.geojson) return;
      if (this.coucheRegions) {
        this.coucheRegions.remove();
      }
      const application = this;
      this.coucheRegions = L.geoJSON(this.geojson, {
        style(element) {
          const code = application.codeDeLElement(element);
          const donnee = application.parCode[code];
          const prevision = donnee && donnee.est_prevision;
          return {
            fillColor: donnee ? application.couleurNiveau(donnee.niveau) : '#E3E5E8',
            fillOpacity: 0.82,
            color: prevision ? '#2B333B' : '#FFFFFF',
            weight: prevision ? 1.6 : 1.2,
            dashArray: prevision ? '4 3' : null,
          };
        },
        onEachFeature(element, couche) {
          const code = application.codeDeLElement(element);
          const donnee = application.parCode[code];
          if (!donnee) return;
          const incertitude = application.incertitudeDe(code);
          let contenu = `<strong>${donnee.region_nom}</strong>`
            + `<span class="valeur">Score ${application.nombreFr(donnee.score, 1)}`
            + ` · ${application.libelleNiveau(donnee.niveau)}</span>`;
          if (donnee.est_prevision && incertitude) {
            contenu += `<span class="valeur">Intervalle `
              + `${application.nombreFr(incertitude.score_bas, 1)} – `
              + `${application.nombreFr(incertitude.score_haut, 1)}</span>`;
          }
          couche.bindTooltip(contenu, {
            className: 'etiquette-region',
            sticky: true,
            direction: 'top',
          });
          couche.on('click', () => application.ouvrirFiche(code));
          couche.on('mouseover', () => couche.setStyle({ fillOpacity: 0.95, weight: 2.4 }));
          couche.on('mouseout', () => application.coucheRegions.resetStyle(couche));
        },
      }).addTo(this.carte);

      const limites = this.coucheRegions.getBounds();
      if (limites.isValid()) {
        this.carte.fitBounds(limites, { padding: [12, 12] });
      }
    },

    // Le GeoJSON de l'equipe porte le code region dans l'une de ces proprietes.
    codeDeLElement(element) {
      const p = element.properties || {};
      return p.region_code || p.REGION_CODE || p.code || p.admin1Name || '';
    },

    async ouvrirFiche(code) {
      this.regionChoisie = code;
      this.fiche = null;
      try {
        this.fiche = await recuperer(`/regions/${code}/fiche`);
      } catch (erreur) {
        this.erreur = `Impossible de charger la fiche de ${code}. `
          + `Détail : ${erreur.message}`;
      }
    },

    fermerFiche() {
      this.regionChoisie = null;
      this.fiche = null;
    },
  },
}).mount('#application');
