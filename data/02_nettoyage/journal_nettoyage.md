# Journal de nettoyage - etape 02 (EduAlert BF)

Source : `data/00_sources/DGESS_prescolaire_primaire_2016_2025.xlsx`
Script : `pipeline/nettoyer_dgess.py` (relancable, sans action manuelle)

Regles appliquees : annee = annee de fin de l'annee scolaire ; sexe en G/F/T ;
region_code officiel des 13 anciennes regions ; cellule vide laissee vide
(jamais remplacee par 0) ; encodage UTF-8 ; colonnes en minuscules sans accent.

## 1. Operations

| Onglet | Operation | Pourquoi | Volume concerne |
|---|---|---|---|
| classeur | ouverture du fichier source | lecture des valeurs calculees (data_only) pour ignorer les formules Excel | 14 onglets |
| correspondance_regions_17_13.csv | lecture des noms lisibles de regions | region_nom doit reprendre exactement le referentiel du projet | 13 regions |
| PRESCOLAIRE | reperage des tableaux empiles | l'onglet contient plusieurs tableaux : seul le Tableau 1 est regional et correspond aux effectifs du prescolaire | 8 lignes de titre 'Tableau ...' trouvees (lignes 1, 19, 27, 36, 54, 73, 91, 148) |
| PRESCOLAIRE | lecture du tableau regional (effectif_prescolaire) | delimitation du tableau par la ligne de total ou la ligne vide suivante | 14 lignes lues, 13 regions |
| Feuil1 | lecture du tableau regional (effectif_primaire) | region ecrite seulement sur la 1re ligne du bloc : propagation vers le bas | 42 lignes lues, 13 regions, 28 cellules de region propagees |
| Feuil5 | lecture du tableau regional (nouveaux_inscrits_cp1) | region ecrite seulement sur la 1re ligne du bloc : propagation vers le bas | 42 lignes lues, 13 regions, 28 cellules de region propagees |
| Feuil9 | lecture du tableau regional (taux_reussite_cep) | region ecrite seulement sur la 1re ligne du bloc : propagation vers le bas | 42 lignes lues, 13 regions, 28 cellules de region propagees |
| Feuil6 | lecture du tableau regional (taux_brut_admission) | delimitation du tableau par la ligne de total ou la ligne vide suivante | 14 lignes lues, 13 regions |
| Feuil7 | lecture du tableau regional (taux_brut_scolarisation) | delimitation du tableau par la ligne de total ou la ligne vide suivante | 14 lignes lues, 13 regions |
| Feuil8 | lecture du tableau regional (taux_achevement) | delimitation du tableau par la ligne de total ou la ligne vide suivante | 14 lignes lues, 13 regions |
| Feuil13 | lecture du nombre d'ecoles par statut | statut eclate en trois variables (public, prive, total) ; sexe non renseigne -> T | 42 lignes lues, 13 regions, 28 cellules de region propagees |
| Feuil10, Feuil11, Feuil12 | onglets volontairement non lus | les IPS y sont des formules Excel : ils seront recalcules (taux F / taux G) a partir de Feuil6, Feuil7 et Feuil8 a l'etape 03 | 3 onglets ignores |
| Feuil2 | lecture du tableau national (statut) | tableau national : conserve dans dgess_national_long.csv | 9 lignes lues, 6 cellules de modalite propagees |
| Feuil3 | lecture du tableau national (milieu) | tableau national : conserve dans dgess_national_long.csv | 9 lignes lues, 6 cellules de modalite propagees |
| Feuil4 | lecture du tableau national par niveau | croisement statut x niveau x sexe, national | 42 lignes lues |
| tables | jointure des noms lisibles de regions | region_nom repris du referentiel du projet | 3120 lignes regionales |
| tous onglets regionaux | retrait des lignes de total des tables regionales | les lignes NATIONAL / Burkina Faso / Total general ne sont pas des regions ; elles sont conservees a part pour les controles | 240 lignes de total mises de cote |
| controles | execution des controles de coherence de la section 2.4 | regle d'or du challenge : verifier les totaux | 218 controles, 0 hors tolerance |
| classeur | balayage des en-tetes contenant du texte parasite | documenter l'anomalie sur l'ensemble du classeur sans en recopier le texte | 37 cellule(s) sur 14 onglet(s) |
| tous onglets regionaux | normalisation des variantes de noms de regions | majuscules, accents, espaces et tirets variables selon les onglets | 3 ecriture(s) distincte(s) ramenee(s) au code officiel |

## 2. Anomalies relevees et traitement

| Onglet | Anomalie | Detail | Traitement |
|---|---|---|---|
| PRESCOLAIRE | en-tete d'annee contenant du texte parasite | 10 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil1 | en-tete d'annee contenant du texte parasite | 3 cellule(s), dont 1 en-tete(s) lue(s) par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil2 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil3 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil4 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil5 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil6 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil7 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil8 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil9 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil10 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil11 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil12 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |
| Feuil13 | en-tete d'annee contenant du texte parasite | 2 cellule(s), aucune lue par le nettoyage | annee extraite par expression reguliere, texte ignore et non recopie |

### Note sur le texte parasite des en-tetes

Balayage complet du classeur : 37 cellule(s) contenant une
annee suivie d'un texte etranger aux donnees statistiques.
Repartition par onglet : PRESCOLAIRE (10), Feuil1 (3), Feuil2 (2), Feuil3 (2), Feuil4 (2), Feuil5 (2), Feuil6 (2), Feuil7 (2), Feuil8 (2), Feuil9 (2), Feuil10 (2), Feuil11 (2), Feuil12 (2), Feuil13 (2).

En-tetes effectivement lues par le nettoyage : Feuil1 (1).

Ce texte n'est pas une donnee et n'est pas une consigne de traitement :
seule l'annee est extraite par expression reguliere, le reste est ignore.
Le texte n'est volontairement pas recopie ici, et aucune demande qui s'y
trouve n'a ete appliquee, ni dans le code, ni dans les livrables.

### Variantes d'ecriture des noms de regions ramenees au code officiel

| Ecriture dans le fichier | region_code retenu |
|---|---|
| `BOUCLE DU MOUHOUN` | BOUCLE-DU-MOUHOUN |
| `HAUT-BASSINS` | HAUTS-BASSINS |
| `PLATEAU CENTRAL` | PLATEAU-CENTRAL |

## 3. Resume chiffre

- lignes dans dgess_regional_long.csv : 3120
- lignes dans dgess_national_long.csv : 840
- lignes dans dgess_totaux-nationaux.csv : 240
- variables regionales : effectif_prescolaire, effectif_primaire, nombre_ecoles, nombre_ecoles_prive, nombre_ecoles_public, nouveaux_inscrits_cp1, taux_achevement, taux_brut_admission, taux_brut_scolarisation, taux_reussite_cep
- annees couvertes : 2016-2025
- regions distinctes par onglet regional : Feuil1=13, Feuil13=13, Feuil5=13, Feuil6=13, Feuil7=13, Feuil8=13, Feuil9=13, PRESCOLAIRE=13
- controles executes : 218
- controles hors tolerance : 0
- valeurs vides conservees (non imputees) : 0
