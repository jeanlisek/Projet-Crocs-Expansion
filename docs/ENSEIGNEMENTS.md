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

## 4. Business case Allemagne (provisoire) : le scénario pessimiste ne passe pas

Constat du 12/11/2026, vue `business_case` (T8), reprise dans `kpi_summary` (axe Rentabilité, Allemagne), données simulées, statut HYPOTHÈSE. **Chiffres provisoires** : Alexis corrige le modèle (voir la fin de la section).

| Format | Payback, scénario pessimiste (seuil : 36 mois) | Coût d'occupation, scénario central (seuil : 15 %) |
|---|---|---|
| Centre commercial | Non atteint en 10 ans : **NO-GO** | 14,9 % : **GO** de justesse |
| Centre-ville | Non atteint en 10 ans : **NO-GO** | 16,9 % : **NO-GO** |

- **Payback** : en scénario pessimiste, l'investissement n'est remboursé dans aucun des deux formats sur l'horizon du modèle (10 ans). C'est le scénario sur lequel le critère est jugé (README, section 4.2).
- **Coût d'occupation** (loyer + charges ÷ CA HT de croisière), scénario central : 14,9 % en centre commercial, juste sous le seuil de 15 %, contre 16,9 % en centre-ville.
- **Effort nécessaire** : pour tenir un payback de 36 mois en scénario pessimiste, il faudrait +22 % (centre-ville) à +31 % (centre commercial) de CA/m² par rapport à la France du même format, estimation provisoire en attendant la vue `sensibilite_payback` (T8-sensibilité). Elle a été obtenue le 12/11/2026 en faisant varier le CA/m² du scénario pessimiste dans la vue `business_case`.
- **Points en cours de correction par Alexis**, qui peuvent déplacer ces chiffres : les effectifs des magasins sont repris de la France ; le potentiel des villes utilise la population simulée ; la France doit être comparée sur le même périmètre de coûts.
