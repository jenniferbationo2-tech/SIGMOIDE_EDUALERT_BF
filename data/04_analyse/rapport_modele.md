# Rapport du modele de risque - etape 04 (EduAlert BF)

## 1. Ce que mesure le score (et ce qu'il ne mesure pas)

Les donnees disponibles ne contiennent aucun taux d'abandon par region,
aucun releve d'absenteisme et aucune donnee individuelle d'eleve. Le risque
de decrochage est donc mesure **indirectement**, par un indice composite
d'indicateurs de deperdition scolaire et de rupture de l'offre scolaire.

**Ce score n'est pas un taux d'abandon.** C'est un indicateur d'alerte,
destine a classer les regions entre elles, pas a chiffrer un nombre d'eleves
sortis du systeme.

## 2. Construction de l'indice

| Composante | Formule | Poids | Code facteur |
|---|---|---|---|
| ecart admission achevement | `ecart_tba_tap` | 0.25 | `ecart_admission_achevement` |
| faible achevement | `100 - taux_achevement` | 0.20 | `faible_achevement` |
| recul effectifs | `- recul_effectif_primaire_vs_pic` | 0.20 | `recul_effectifs` |
| fermeture ecoles | `- recul_nombre_ecoles_vs_pic` | 0.15 | `fermeture_ecoles` |
| faible scolarisation | `100 - taux_brut_scolarisation` | 0.10 | `faible_scolarisation` |
| disparite filles garcons | `abs(1 - ips_tap)` | 0.10 | `disparite_filles_garcons` |

Normalisation : rang percentile de chaque composante sur l'ensemble du panel
(13 regions x 2017-2025, soit 117 observations). Ce choix
est robuste aux valeurs extremes de 2022/23 et garde le score comparable d'une
annee a l'autre.

Score = 100 x somme(poids x percentile), arrondi a 1 decimale.
Niveaux : `Faible` < 33, `Modere` 33-66, `Critique` >= 66.

### Pourquoi le recul depuis le pic plutot que la variation annuelle

Une premiere version de l'indice utilisait les variations annuelles des
effectifs et du nombre d'ecoles. Ce choix faisait baisser a tort le risque des
regions encore devastees : en 2025, le Sahel gagne 10,5 % d'eleves et 10 %
d'ecoles, alors qu'il lui manque toujours 52,8 % de ses eleves et 82,0 % de ses
ecoles par rapport a son meilleur niveau. Les composantes mesurent donc
desormais le **recul depuis le pic** : ce qui n'a pas ete reconstitue. La
variante ecartee figure dans l'analyse de sensibilite sous le nom
`avec_variations_annuelles`.

## 3. Repartition des niveaux par annee

```
niveau  Critique  Faible  Modere
annee                           
2017           0       1      12
2018           0       1      12
2019           0       3      10
2020           1       3       9
2021           2       2       9
2022           3       4       6
2023           6       1       6
2024           7       1       5
2025           7       1       5
```

## 4. Modeles de prevision N+1

Paires annee N -> score N+1 : 104 observations au total,
65 en entrainement (cibles <= 2022) et 39 en test
(cibles 2023, 2024 et 2025). La validation est **temporelle** : aucun melange
aleatoire des annees, le modele ne voit jamais le futur.

```
                               modele   mae   rmse  justesse_niveau  f1_critique bat_la_reference_naive retenu
reference naive (score N+1 = score N) 6.995  9.064            0.821        0.889                      -    oui
         regression Ridge (alpha=0.1) 8.051  9.980            0.795        0.857                    non    non
        foret aleatoire (max_depth=3) 8.221 10.274            0.718        0.750                    non    non
```

**Modele retenu : reference naive (score N+1 = score N)** (meilleure MAE sur le test).

**Honnetement : aucun modele appris ne bat la reference naive** (MAE 6.995 contre 6.995 pour la reference).

Deux raisons, et il faut les dire :

1. **Le choc de 2022/23 est un changement de regime.** Le modele est
   entraine sur des annees ou le systeme scolaire se degrade lentement,
   puis teste sur l'apres-effondrement. Les relations apprises ne tiennent
   plus.
2. **104 observations, c'est tres peu** pour apprendre une relation
   a 9 variables. Le score d'une region est par ailleurs tres stable d'une
   annee a l'autre, ce qui rend la reference naive difficile a battre.

Conclusion assumee : pour la prevision 2026, on garde la methode la plus
simple et la plus fiable sur le test, plutot qu'un modele plus savant mais
moins juste.

### Matrice de confusion des niveaux (modele retenu, test 2023-2025)

```
               prevu Faible  prevu Modere  prevu Critique
reel Faible               3             0               0
reel Modere               3            13               0
reel Critique             0             4              16
```

## 5. Importance des variables

Importance par permutation sur le jeu de test (30 repetitions,
`random_state=42`), mesuree en degradation de la MAE.

```
            variable  importance_permutation  ecart_type  coefficient_standardise
               score                 10.9270      1.4418                  10.1119
     recul_effectifs                  3.3516      0.6299                  -3.9272
    fermeture_ecoles                  2.4092      0.6884                   3.1807
faible_scolarisation                  1.2741      0.5091                   3.0562
   taux_reussite_cep                  0.3350      0.2258                  -1.6756
```

## 6. Analyse de sensibilite des poids

```
                       variante  spearman_classement  part_regions_changeant_de_niveau_pct
                    poids_egaux               0.9825                                   6.8
sans_ecart_admission_achevement               0.9054                                  23.1
         sans_faible_achevement               0.9616                                   9.4
           sans_recul_effectifs               0.9561                                  10.3
          sans_fermeture_ecoles               0.9846                                   7.7
      sans_faible_scolarisation               0.9894                                   5.1
  sans_disparite_filles_garcons               0.9845                                   7.7
      avec_variations_annuelles               0.8302                                  19.7
```

Lecture : une correlation de Spearman proche de 1 signifie que le classement
des regions ne depend pas du detail des poids. C'est le cas ici, ce qui rend
l'indice robuste a ce choix.

## 7. Prevision 2026

Methode : reference naive : score 2026 = score 2025.
Les facteurs affiches pour 2026 sont ceux de 2025.

### Classement 2025 (observe)

| Rang | Region | Score | Niveau | Facteurs |
|---|---|---|---|---|
| 1 | CENTRE-NORD | 87.7 | Critique | ecart_admission_achevement;faible_achevement;recul_effectifs |
| 2 | BOUCLE-DU-MOUHOUN | 81.0 | Critique | ecart_admission_achevement;recul_effectifs;faible_achevement |
| 3 | SAHEL | 75.4 | Critique | faible_achevement;recul_effectifs;fermeture_ecoles |
| 4 | EST | 72.9 | Critique | faible_achevement;recul_effectifs;fermeture_ecoles |
| 5 | NORD | 69.7 | Critique | ecart_admission_achevement;faible_achevement;fermeture_ecoles |
| 6 | CASCADES | 67.3 | Critique | ecart_admission_achevement;faible_achevement;recul_effectifs |
| 7 | CENTRE-EST | 67.1 | Critique | ecart_admission_achevement;faible_achevement;fermeture_ecoles |
| 8 | SUD-OUEST | 56.7 | Modere | ecart_admission_achevement;faible_achevement;fermeture_ecoles |
| 9 | PLATEAU-CENTRAL | 55.9 | Modere | ecart_admission_achevement;fermeture_ecoles;faible_achevement |
| 10 | HAUTS-BASSINS | 55.7 | Modere | ecart_admission_achevement;recul_effectifs;fermeture_ecoles |
| 11 | CENTRE-SUD | 41.7 | Modere | ecart_admission_achevement;recul_effectifs;faible_achevement |
| 12 | CENTRE-OUEST | 37.9 | Modere | ecart_admission_achevement;disparite_filles_garcons;recul_effectifs |
| 13 | CENTRE | 26.4 | Faible | ecart_admission_achevement;recul_effectifs;fermeture_ecoles |

### Classement 2026 (prevision)

| Rang | Region | Score | Niveau | Facteurs |
|---|---|---|---|---|
| 1 | CENTRE-NORD | 87.7 | Critique | ecart_admission_achevement;faible_achevement;recul_effectifs |
| 2 | BOUCLE-DU-MOUHOUN | 81.0 | Critique | ecart_admission_achevement;recul_effectifs;faible_achevement |
| 3 | SAHEL | 75.4 | Critique | faible_achevement;recul_effectifs;fermeture_ecoles |
| 4 | EST | 72.9 | Critique | faible_achevement;recul_effectifs;fermeture_ecoles |
| 5 | NORD | 69.7 | Critique | ecart_admission_achevement;faible_achevement;fermeture_ecoles |
| 6 | CASCADES | 67.3 | Critique | ecart_admission_achevement;faible_achevement;recul_effectifs |
| 7 | CENTRE-EST | 67.1 | Critique | ecart_admission_achevement;faible_achevement;fermeture_ecoles |
| 8 | SUD-OUEST | 56.7 | Modere | ecart_admission_achevement;faible_achevement;fermeture_ecoles |
| 9 | PLATEAU-CENTRAL | 55.9 | Modere | ecart_admission_achevement;fermeture_ecoles;faible_achevement |
| 10 | HAUTS-BASSINS | 55.7 | Modere | ecart_admission_achevement;recul_effectifs;fermeture_ecoles |
| 11 | CENTRE-SUD | 41.7 | Modere | ecart_admission_achevement;recul_effectifs;faible_achevement |
| 12 | CENTRE-OUEST | 37.9 | Modere | ecart_admission_achevement;disparite_filles_garcons;recul_effectifs |
| 13 | CENTRE | 26.4 | Faible | ecart_admission_achevement;recul_effectifs;fermeture_ecoles |

## 8. Limites

- Le score est un **indice relatif** : il classe les regions entre elles. Un
  score de 50 ne veut pas dire « la moitie des eleves decrochent ».
- La normalisation par rang percentile implique que, par construction, il y a
  toujours des regions en haut et en bas du classement.
- Les taux de scolarisation dependent de denominateurs de population projetes
  depuis le RGPH 2019, incertains dans les regions a forts deplacements.
- La prevision 2026 suppose la continuite des conditions de 2025.
  Une degradation ou une amelioration securitaire brutale la rendrait fausse.
- `random_state=42` partout : deux executions donnent le meme resultat.
