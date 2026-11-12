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
