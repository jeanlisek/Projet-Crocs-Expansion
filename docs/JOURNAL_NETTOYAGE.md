# Journal de nettoyage (bronze → silver)

> **État au 12/11/2026.** Les 9 constats du rapport de contrôles sur le jeu v1 sont consignés ci-dessous. Chaque décision est une **proposition à valider par l'équipe**. Aucune correction n'est appliquée : le jeu v1 est écrit en silver tel quel.
> Les données réelles de T16 (OpenStreetMap, Destatis) sont consignées en section 2. Les sections de T3 et T4 restent à ouvrir.

## Principe

- `data/bronze/` n'est **jamais modifié**. Une correction se fait dans `src/transform/bronze_to_silver.py`, qui retransforme le bronze à chaque exécution.
- **Toute correction est consignée ici** : l'anomalie, le nombre de lignes, la décision, la justification métier.
- Conserver une valeur signalée est aussi une décision : elle se consigne de la même façon.

## Mode d'emploi

1. Lancer `make silver`. Le script type les tables, les contrôle et écrit `data/silver/rapport_controles.csv`.
2. Lire les lignes du rapport au statut `a_examiner`. Les lignes `attendu` sont des valeurs nulles déjà expliquées dans le `TableSpec` de la table.
3. Pour chaque constat, décider et ajouter une ligne au journal, avec un identifiant `N-001`, `N-002`…
4. Si la décision modifie les données, déclarer une `Correction` portant **le même identifiant** dans la liste `CORRECTIONS` du script, puis relancer `make silver`.

## Contrôles du script

| Contrôle (`controle`) | Ce qu'il compte |
|---|---|
| `doublons` | Lignes qui répètent la clé primaire de la table |
| `valeurs_nulles` | Valeurs manquantes, colonne par colonne |
| `valeurs_aberrantes_iqr` | Valeurs hors de l'intervalle [Q1 − k × IQR ; Q3 + k × IQR], calculé si besoin par groupe comparable (même format, même produit…) |

Le multiplicateur k est `nettoyage.iqr_multiplicateur` dans `config/hypotheses.yaml`. Les colonnes contrôlées et leurs groupes sont déclarés dans `outlier_checks`, table par table.

Une valeur qui ne correspond pas au type attendu (par exemple un prix `49,99 €` dans une colonne numérique) n'est pas comptée : elle arrête le script. Elle se traite par une correction sur le texte brut, consignée ici comme les autres.

## Décisions possibles

| Décision | Quand |
|---|---|
| **Conservé** | La valeur est correcte : elle s'explique par le métier |
| **Corrigé** | La valeur est récupérable : format, unité, orthographe |
| **Supprimé** | La ligne est inutilisable ou en double |
| **Imputé** | La valeur manquante est remplacée ; la règle de remplacement est écrite dans la justification |

## Journal

### 1. Données simulées (générateur, 19 tables)

Constats de `make silver` sur le jeu v1 (seed 2027), multiplicateur IQR de 1,5. Aucun doublon, aucune valeur nulle inattendue.

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| N-001 | 12/11/2026 | `fact_ventes_france` | `quantite_vendue` | Quantités mensuelles hors intervalle IQR, calculé par magasin × produit : 3 480 valeurs hautes, 149 basses | 3 629 sur 261 832 (1,39 % des lignes, 1,98 % du CA net HT) | **Conservé** (proposition à valider par l'équipe) | Saisonnalité, pas erreur de saisie. 60,7 % des lignes tombent en novembre-décembre (Black Friday, Noël), dont 1 738 sur des produits au profil « noël ». Les pics de juin-juillet portent sur les produits au profil « été » (363 lignes), ceux de mars à mai sur le profil « printemps » (384 lignes). Les soldes n'expliquent pas ces volumes : dans le générateur, ils n'agissent que sur la remise ; les 309 pics de juillet sont des pics d'été et janvier n'en compte que 4. Les valeurs basses se concentrent en janvier-février sur les produits au profil « plat » (78 lignes). Supprimer ces lignes effacerait la saisonnalité, qui est l'information métier | Aucune |
| N-002 | 12/11/2026 | `fact_prix_releves` | `prix_affiche_eur` | Prix sous la borne basse de l'intervalle IQR, calculé par produit ; aucun prix au-dessus de la borne haute | 310 sur 4 199 | **Conservé** (proposition à valider par l'équipe) | Promotions : les 310 lignes ont toutes `en_promotion = True`, avec une remise de 15,1 % à 35 % (264 relevés Crocs, 46 relevés concurrents). Pas d'effet pays : elles se répartissent sur les 7 pays (37 à 58 lignes chacun) et aucun prix n'est anormalement haut, Royaume-Uni compris. Ces relevés sont de vrais prix affichés. Ils restent en silver et sont écartés au calcul de l'indice prix, qui se fait hors promotion (README 2.5, règle 4), grâce à la colonne `en_promotion` | Aucune |
| N-003 | 12/11/2026 | `fact_immobilier` | `loyer_m2_an_eur` | Loyers au-dessus de la borne haute de l'intervalle IQR, calculé par type d'emplacement | 44 sur 1 060 | **Conservé** (proposition à valider par l'équipe) | Villes prime : Londres (20 lignes) et Milan (20 lignes) sur les 5 types d'emplacement et les 4 années, Rome (4 lignes, 2025-2026). Ce sont les loyers les plus élevés du benchmark, pas des erreurs. Aucune ville allemande n'est signalée : le KPI « coût moyen au m² » de l'Allemagne n'est pas concerné | Aucune |
| N-004 | 12/11/2026 | `dim_produit` | `prix_vente_ttc_fr` | Prix sous la borne basse de l'intervalle IQR, calculé par catégorie | 3 sur 147 | **Conservé** (proposition à valider par l'équipe) | Les 3 coloris du modèle HEYDUDE Wendy Youth (P0145 à P0147), à 49,99 €. C'est le seul modèle enfant de la catégorie « Chaussures toile », dont les modèles adultes valent 69,99 € à 79,99 € : un prix enfant plus bas est cohérent. Le contrôle compare ici adultes et enfants ; le grouper par catégorie et cible lèverait le signalement | Aucune |
| N-005 | 12/11/2026 | `fact_logistique` | `cout_transport_palette_eur` | Coûts au-dessus de la borne haute de l'intervalle IQR (391,93 €), calculé sur toute la table | 3 sur 159 | **Conservé** (proposition à valider par l'équipe) | Les 3 liaisons vers Las Palmas (Canaries) depuis chacun des 3 hubs : 3 319 à 3 900 km, 476,52 € à 552,06 € par palette. Le coût est cohérent avec la distance, la plus longue de la table. Limite à connaître : la distance « routière » du générateur est la distance à vol d'oiseau majorée de 25 %, alors que Las Palmas est une île ; ce coût est théorique. Sans effet sur l'Allemagne : Las Palmas appartient au benchmark Espagne | Aucune |
| N-006 | 12/11/2026 | `fact_prix_releves` | `id_produit` | Valeurs nulles | 1 184 sur 4 199 | **Conservé** (proposition à valider par l'équipe) | Relevés de produits concurrents, absents du catalogue Crocs : il n'existe pas d'`id_produit` à leur attribuer (audit du jeu v1). Non imputé | Aucune |
| N-007 | 12/11/2026 | `fact_eligibilite_assortiment` | `adaptation_requise` | Valeurs nulles | 55 sur 882 | **Conservé** (proposition à valider par l'équipe) | Ce sont exactement les 55 couples pays × produit non éligibles : un produit exclu de l'assortiment n'a pas d'adaptation à prévoir. Non imputé | Aucune |
| N-008 | 12/11/2026 | `fact_marche` | `taux_croissance_annuel_pct` | Valeurs nulles | 14 sur 154 | **Conservé** (proposition à valider par l'équipe) | Année 2019, première année de chacune des 14 séries (7 pays × 2 segments) : sans année précédente, le taux de croissance n'est pas calculable. Non imputé | Aucune |
| N-009 | 12/11/2026 | `fact_couts_exploitation` | `salaire_minimum_mensuel_eur` | Valeur nulle | 1 sur 7 | **Conservé** (proposition à valider par l'équipe) | Italie : pas de salaire minimum légal (audit du jeu v1). Une valeur imputée serait un chiffre inventé | Aucune |

### 2. Données réelles

Sections à ouvrir quand les fichiers datés existent dans `data/bronze/`. Pour chaque source, noter le fichier et son URL avant la première ligne du tableau.

#### 2.1 Prix Crocs France et Allemagne (scraping, T3)

_TODO T3 : aucun fichier collecté à ce jour._

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| _N-…_ | | | | | | | | |

#### 2.2 Indicateurs pays Eurostat (API, T4)

_TODO T4 : aucun fichier collecté à ce jour._

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| _N-…_ | | | | | | | | |

#### 2.3 Magasins de chaussures OpenStreetMap (API Overpass, T16)

Fichiers : `data/bronze/osm_overpass_<id_zone>_2026-11-12.json` (une réponse brute par ville), `osm_villes.csv` et `osm_magasins_chaussures.csv`. Source : <https://overpass-api.de/api/interpreter>, données © les contributeurs d'OpenStreetMap, licence ODbL.

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| N-010 | 12/11/2026 | `osm_villes`, `osm_magasins_chaussures` | — | Erreurs HTTP 502 (Bad Gateway) du serveur Overpass pendant la collecte | 12 requêtes sur 24 ; aucune ligne de données | **Reprise** : attente de 30 s entre deux essais, arrêt après 3 échecs de suite, relance quelques minutes plus tard à partir du cache | Indisponibilité passagère d'un serveur public que sa politique d'usage annonce comme surchargé, et non un refus : aucune limite n'a été approchée (24 requêtes pour un plafond de 10 000 par jour). Les données ne sont pas touchées : une réponse en erreur n'est jamais enregistrée, chaque ville a une réponse complète avec exactement une limite administrative, et une ville déjà obtenue n'est pas redemandée | `RETRY_STATUSES` et `fetch` dans `src/collect/osm.py` |
| N-011 | 12/11/2026 | `osm_magasins_chaussures` | `enseigne` | Valeurs nulles | 574 sur 992 | **Conservé** (proposition à valider par l'équipe) | Le tag `brand` est facultatif dans OpenStreetMap : un magasin sans enseigne renseignée reste un magasin de chaussures et compte dans la densité. Limite signalée dans le README (section 3.4) pour toute analyse par enseigne. Non imputé | Aucune |
| N-012 | 12/11/2026 | `osm_magasins_chaussures` | `nom` | Valeurs nulles | 4 sur 992 | **Conservé** (proposition à valider par l'équipe) | Le tag `name` est facultatif ; l'identifiant OSM et les coordonnées suffisent à compter le magasin. Non imputé | Aucune |
| N-013 | 12/11/2026 | `osm_villes` | `population_osm`, `annee_population_osm`, `source_population_osm` | Valeurs nulles : le tag `population` manque sur la limite administrative de 7 villes, son année pour 9, sa source pour 10 | 7, 9 et 10 sur 12 | **Conservé** ; la densité se calcule avec la population officielle Destatis (décision du 12/11/2026) | Ces tags sont facultatifs dans OpenStreetMap et ne suffisent pas à calculer la densité des 12 villes avec une année et une source connues. La population Destatis est officielle et porte la même date de référence (31/12/2024) pour toutes les villes. Les valeurs OSM existantes sont gardées pour comparaison, sans imputation | Aucune |

#### 2.4 Population des villes allemandes (Destatis, T16)

Fichiers : `data/bronze/destatis_05-staedte_2024-12-31.xlsx` (classeur officiel tel que téléchargé le 12/11/2026) et `destatis_population_villes.csv` (les 12 villes, extraites par leur code communal). Source : <https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/Administrativ/05-staedte.html>.

Aucune anomalie : les 12 villes sont trouvées, chacune une seule fois, sans valeur nulle.

