# Enseignements

Ce que les KPIs apprennent au fil des tâches, à reprendre dans le business case, le dashboard et les slides. Chaque chiffre vient d'une vue de l'entrepôt (`make all`) ; la vue et l'origine des données sont indiquées.

## 1. Le réseau France dépasse déjà le seuil de coût d'occupation

Constat du 12/11/2026, vue `kpi_cout_occupation`, année 2025, données simulées (jeu recalibré par T2).

Le loyer des magasins France pèse **18,5 % de leur CA HT**, tous formats confondus, alors que le seuil Go fixé pour l'Allemagne est de **15 %** (README, section 4.2).

| Format | Magasins | Loyer ÷ CA HT | Par rapport au seuil de 15 % |
|---|---|---|---|
| Centre commercial | 22 | 15,2 % | Juste au-dessus |
| Centre-ville | 13 | 23,6 % | Au-dessus |
| Gare / aéroport | 3 | 28,9 % | Au-dessus |
| Outlet | 5 | 13,5 % | En dessous |
| **Tous formats** | **43** | **18,5 %** | **Au-dessus** |

- Le taux est recalculé depuis les sommes de loyer et de CA, pas en moyennant les magasins. Il porte sur les 43 magasins physiques ouverts toute l'année 2025.
- C'est un minorant : les charges locatives ne sont pas connues pour les magasins France, seul le loyer est compté.
- Conséquence pour le business case (T8) : le réseau qui sert de référence ne respecterait pas lui-même le critère, sauf en outlet. Un magasin allemand construit sur la productivité française part avec ce handicap, surtout en centre-ville et en gare.

## 2. L'indice prix n'est pas significatif sans les prix réels

Constat du 12/11/2026, vue `kpi_indice_prix`, panier de 15 SKU, données simulées.

| Pays | Indice prix HT (France = 100) |
|---|---|
| Allemagne | 100,34 |
| Belgique, Espagne, Pays-Bas | 99,17 |
| Italie | 98,36 |
| Royaume-Uni | 107,29 |

- Le jeu simulé applique le même prix public TTC dans toute la zone euro. Une fois les prix ramenés en HT, l'indice ne mesure donc que l'écart de TVA entre le pays et la France : trois pays à 21 % de TVA obtiennent exactement le même indice.
- L'indice du Royaume-Uni est tiré vers le haut par la TVA à 0 % sur les chaussures enfant.
- L'Allemagne passe le critère (entre 95 et 110), mais ce GO ne dit rien du positionnement prix réel de la marque. Il ne sera interprétable qu'avec les prix relevés sur crocs.fr et crocs.de (T3).

## 3. Prix réels : même prix TTC en France et en Allemagne, tout le catalogue est sur crocs.de

Constat du 12/11/2026, tables réelles `crocs_produits` et `crocs_catalogue` (T3, relevé des sites crocs.fr et crocs.de du 12/11/2026). Les totaux viennent des vues `kpi_indice_prix` et `kpi_catalogue_eligible` (lignes `REEL` de l'Allemagne) ; le détail par catégorie est calculé par `price_index` et `catalogue_share` de `src/collect/scrape_crocs.py`.

| Catégorie | Paires FR/DE | Modèles | Indice prix HT (France = 100) | Références du catalogue France | Présentes sur crocs.de |
|---|---|---|---|---|---|
| Sabots | 94 | 7 | 100,85 | 772 | 772 (100 %) |
| Sandales | 21 | 5 | 100,84 | 152 | 152 (100 %) |
| Chaussures | 13 | 5 | 100,84 | 131 | 131 (100 %) |
| **Total** | **128** | **17** | **100,85** | **1 055** | **1 055 (100 %)** |

- **Prix TTC identiques.** Sur les 128 paires réelles (même code modèle, même code coloris, coloris disponible sur les deux sites), le prix affiché TTC est le même en France et en Allemagne, sans exception. Vérifié à la main sur un exemple le 12/11/2026 : le Classic Clog noir, à 38,49 € (prix barré 54,99 €) sur crocs.fr comme sur crocs.de.
- **L'indice HT de 100,85 est dû uniquement à la TVA.** À prix TTC égal, le prix HT allemand est plus élevé parce que la TVA est de 19 % en Allemagne contre 20 % en France : 1,20 ÷ 1,19 = 100,84, aux arrondis au centime près. L'indice est calculé sur le prix hors promotion (le prix barré quand il existe : 103 paires sur 128 étaient en promotion le jour du relevé) ; sur les prix affichés, il vaut 100,83. Il passe le critère Go (entre 95 et 110).
- **100 % du catalogue France est disponible sur crocs.de.** Les 1 055 références (modèle + coloris, 433 modèles) listées sur crocs.fr le sont aussi sur crocs.de, dans les trois catégories. Le seuil Go est de 80 %.
- Limites : un seul jour de relevé ; les prix sont lus sur 17 modèles (les premiers modèles communs de chaque catégorie), le catalogue sur les trois pages « silhouette » des sites, sans les accessoires ; « présent » veut dire listé sur le site, pas en stock.
- Conséquence : le prix n'est pas un levier de différenciation entre les deux pays, et l'assortiment français peut être repris tel quel. L'hypothèse du jeu simulé (même prix public TTC dans la zone euro, section 2) est confirmée pour le couple France-Allemagne. Dans `kpi_summary`, l'Allemagne est jugée sur ces valeurs réelles (indice 100,85 et catalogue 100 %, `origine_donnees` = REEL, GO tous les deux) ; les valeurs du jeu simulé (indice 100,34, catalogue éligible 97,96 %) restent affichées sur une ligne « (comparaison, jeu simulé) », sans verdict.

## 4. Business case Allemagne : le scénario pessimiste ne passe pas en l'état, un format allégé à 3 ETP passe

Constat du 12/11/2026, données simulées. Vues `business_case`, `sensibilite_payback` et `business_case_france` (T8 et T8-sensibilité), reprises dans `kpi_summary` (axe Rentabilité). Statuts du README (section 2.3) : payback en HYPOTHÈSE, coût d'occupation et point mort en CALCUL.

### Lecture « en l'état » : le magasin type du business case

Le magasin type reprend les effectifs moyens des magasins France du même format : 5,35 ETP en centre commercial, 4,55 ETP en centre-ville.

| Format | Payback, scénario pessimiste (seuil : 36 mois) | Coût d'occupation, scénario central (seuil : 15 %) | CA/m² nécessaire pour un payback de 36 mois en scénario pessimiste |
|---|---|---|---|
| Centre commercial | Non atteint en 10 ans : **NO-GO** | 14,9 % : **GO** de justesse | +31 % par rapport à la France du même format |
| Centre-ville | Non atteint en 10 ans : **NO-GO** | 16,9 % : **NO-GO** | +22 % par rapport à la France du même format |

- **Payback** : en scénario pessimiste (CA/m² à 75 % de la France du même format), l'investissement n'est remboursé dans aucun des deux formats sur l'horizon du modèle (10 ans). C'est le scénario sur lequel le critère est jugé (README, section 4.2).
- **Coût d'occupation** (loyer + charges ÷ CA HT de croisière), scénario central : 14,9 % en centre commercial, juste sous le seuil de 15 %, contre 16,9 % en centre-ville.
- **Effort nécessaire** : la vue `sensibilite_payback` donne le premier GO, au pas de 1 % de la grille, à 1,32 × le CA/m² France en centre commercial et à 1,23 × en centre-ville. Le calcul continu donne +31 % et +22 %. La grille configurée (`sensibilite_payback` dans `config/hypotheses.yaml`) s'arrête à 1,05 × la France et ne porte que sur le centre commercial : à 5,35 ETP, elle ne montre donc aucun GO. Ces deux seuils ont été obtenus avec la même vue sur une grille élargie à 1,60 et pour chacun des deux formats.

### Lecture « format allégé à 3 ETP » : le minimum du réseau France

Centre commercial, scénario pessimiste, vue `sensibilite_payback` telle que configurée.

- À 3 ETP, le payback passe sous les 36 mois dès **1,02 × le CA/m² France** du même format (+2 %). Au CA/m² de la France (1,00), il est de 36,8 mois : NO-GO de peu.
- Au CA/m² maximal de la grille (1,05 × la France, celui du scénario optimiste), le GO tient jusqu'à **3,25 ETP**. Au-delà de 3,25 ETP, aucun CA/m² de la grille ne donne un GO.
- En centre-ville, à 3 ETP, il faudrait 1,03 × le CA/m² France (+3 %). Ce chiffre a été obtenu avec la même vue en passant son format à « Centre-ville ».
- Lecture : le critère de payback ne se joue pas sur le CA, que le scénario pessimiste fixe à 75 % de la France, mais sur l'effectif. Un magasin allemand ne passe qu'avec une équipe ramenée au minimum du réseau France ET un CA/m² au moins égal à celui de la France, soit bien au-dessus du scénario pessimiste.

### Référence France sur le même périmètre de coûts

Vue `business_case_france` : magasins France ouverts toute l'année 2025, mêmes postes de coûts que l'Allemagne (loyer et charges, personnel, énergie, coûts variables, amortissement). Les charges locatives, absentes du jeu France, sont estimées avec le ratio charges / loyer de `fact_immobilier` (HYPOTHÈSE de proxy). Le payback France est calculé sur un magasin à maturité, sans montée en charge ni marketing de lancement.

| Format | Magasins | CA HT moyen | Coût d'occupation | Point mort | Payback |
|---|---|---|---|---|---|
| Centre commercial | 22 | 653 103 € | 17,4 % | 540 354 € | 26,2 mois |
| Centre-ville | 13 | 649 800 € | 26,9 % | 590 268 € | 37,2 mois |

- Sur ce périmètre, les magasins France dépassent eux-mêmes le seuil de coût d'occupation de 15 % dans les deux formats. Le magasin France de centre-ville ne tiendrait pas non plus le critère de payback de 36 mois.
- L'Allemagne en scénario central a un coût d'occupation plus bas que la France (14,9 % contre 17,4 % en centre commercial, 16,9 % contre 26,9 % en centre-ville) : les loyers et charges simulés y sont plus bas, pour un CA/m² à 90 % de la France.
- Le point mort allemand est proche du point mort français (565 010 € contre 540 354 € en centre commercial). Avec 5,35 ETP, le magasin type allemand a un coût de personnel plus élevé que la moyenne France (206 519 € contre 185 332 €) pour un CA plus faible.

### Classement des villes avec la population Destatis

Vue `city_scoring` : le critère potentiel (40 % du score) utilise désormais la population officielle de chaque ville (Destatis, 31/12/2024) au lieu de la population simulée de sa zone de chalandise, toujours multipliée par l'indice de revenu simulé. Les autres critères sont inchangés.

| Rang | Ville | Rang avant | Prioritaire |
|---|---|---|---|
| 1 | Berlin | 1 | Oui |
| 2 | Dortmund | 2 | Oui |
| 3 | Hamburg | 3 | Oui |
| 4 | Köln | 4 | Oui |
| 5 | Hannover | 5 | Oui |
| 6 | **Nürnberg** | 7 | **Oui (entre)** |
| 7 | **Leipzig** | 6 | **Non (sort)** |
| 8 | Frankfurt | 8 | Non |
| 9 | Düsseldorf | 9 | Non |
| 10 | **München** | 12 | Non |
| 11 | **Dresden** | 10 | Non |
| 12 | **Stuttgart** | 11 | Non |

- Les cinq premières villes ne bougent pas. Nürnberg remplace Leipzig parmi les six villes prioritaires. München gagne deux places, Dresden et Stuttgart en perdent une.
- Le changement vient surtout de la définition du potentiel (ville au lieu de zone de chalandise), pas de l'écart entre population réelle et simulée, qui est de 0,1 à 6 % selon les villes. La zone de chalandise simulée valait de 1,6 à 2,5 fois la population de la ville : München, où ce rapport était le plus faible, gagne deux places ; Leipzig, où il était le plus élevé, sort des villes prioritaires.

## 5. Marché réel : les dépenses en chaussures progressent en Allemagne, stagnent en France

Constat du 12/11/2026, table réelle `eurostat_series` (T4) : dépenses de consommation des ménages en chaussures (Eurostat, jeu `nama_10_cp18`, poste CP032, millions d'euros courants), toutes chaussures confondues, données mises à jour par Eurostat le 10/11/2026. Aucune vue KPI ne lit encore cette table : `kpi_croissance_secteur` reste sur le jeu simulé.

| Pays | Dépenses 2022 | Dépenses 2025 | TCAM 2022-2025 en valeur | TCAM en volume (estimation indicative) | Statut Eurostat |
|---|---|---|---|---|---|
| **Allemagne** | 17 485 M€ | 20 554 M€ | **+5,5 %** | environ +2,9 % | provisoire sur toute la période (2022 à 2025) |
| **France** | 7 510 M€ | 7 456 M€ | **−0,2 %** | environ −1,6 % | provisoire en 2024 et 2025 |

- **En valeur, inflation comprise** : le TCAM est calculé sur les dépenses en euros courants, entre 2022 et 2025. Le marché allemand de la chaussure a progressé de 5,5 % par an ; le marché français a reculé de 0,2 % par an.
- **En volume, estimation indicative** : en retirant la hausse des prix des chaussures (indice des prix à la consommation harmonisé, jeu `prc_hicp_ainr`, poste CP032, moyenne annuelle), la croissance serait d'environ +2,9 % par an en Allemagne et −1,6 % en France. C'est une approximation : l'indice des prix suit un panier de chaussures, pas exactement la composition des dépenses.
- **Données allemandes provisoires** : Eurostat signale comme provisoires toutes les valeurs allemandes de 2022 à 2025. Elles peuvent être révisées.
- **Comparaison avec le jeu simulé, à périmètre égal** (toutes chaussures, `fact_marche`, segment « Chaussures (total) », TCAM 2022-2025) : +1,9 % pour l'Allemagne et +1,4 % pour la France. Le réel donne une croissance plus forte en Allemagne et une baisse en France : il creuse l'écart entre les deux pays, dans le sens favorable à l'Allemagne.
- Le KPI « Croissance du secteur » de `kpi_summary` porte sur un autre périmètre : le segment simulé « Casual moulé & sandales » (+3,9 % pour l'Allemagne, +3,0 % pour la France). Eurostat ne publie pas ce segment ; le chiffre réel ci-dessus ne le remplace donc pas tel quel.
