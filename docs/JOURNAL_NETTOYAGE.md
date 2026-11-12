# Journal de nettoyage (bronze → silver)

> **État au 12/11/2026.** Les 10 constats du rapport de contrôles sur le jeu simulé, recalibré par T2, sont consignés ci-dessous. Chaque décision est une **proposition à valider par l'équipe**. Aucune correction n'est appliquée : le jeu v1 est écrit en silver tel quel.
> Les données réelles de T3 (prix Crocs), de T16 (OpenStreetMap, Destatis) et de T17 (OSRM) sont consignées en section 2. La section de T4 reste à ouvrir.

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

Constats de `make silver` sur le jeu recalibré par T2 (seed 2027, 12/11/2026), multiplicateur IQR de 1,5. Aucun doublon, aucune valeur nulle inattendue. Les comptes du jeu v1, consignés avant le recalibrage, ont été recalculés.

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| N-001 | 12/11/2026 | `fact_ventes_france` | `quantite_vendue` | Quantités mensuelles hors intervalle IQR, calculé par magasin × produit : 3 755 valeurs hautes, 153 basses | 3 908 sur 246 476 (1,59 % des lignes, 2,40 % du CA net HT) | **Conservé** (proposition à valider par l'équipe) | Saisonnalité, pas erreur de saisie. 48,6 % des lignes tombent en novembre-décembre (Black Friday, Noël), dont 1 347 sur des produits au profil « noël ». Les pics de juin-juillet portent sur les produits au profil « été » (610 lignes), ceux de mars à mai sur le profil « printemps » (329 lignes). Les soldes n'expliquent pas ces volumes : dans le générateur, ils n'agissent que sur la remise ; juillet, mois du pic des produits d'été, compte 531 valeurs hautes, et janvier, l'autre mois de soldes, seulement 12. Les valeurs basses se concentrent en janvier-février sur les produits au profil « plat » (75 lignes). Supprimer ces lignes effacerait la saisonnalité, qui est l'information métier | Aucune |
| N-002 | 12/11/2026 | `fact_prix_releves` | `prix_affiche_eur` | Prix sous la borne basse de l'intervalle IQR, calculé par produit ; aucun prix au-dessus de la borne haute | 574 sur 4 153 | **Conservé** (proposition à valider par l'équipe) | Promotions : les 574 lignes ont toutes `en_promotion = True`, avec une remise de 15,0 % à 34,9 % (558 relevés Crocs, 16 relevés concurrents). Pas d'effet pays : elles se répartissent sur les 7 pays (63 à 97 lignes chacun) et aucun prix n'est anormalement haut, Royaume-Uni compris. Ces relevés sont de vrais prix affichés. Ils restent en silver et sont écartés au calcul de l'indice prix, qui se fait hors promotion (README 2.5, règle 4), grâce à la colonne `en_promotion` | Aucune |
| N-003 | 12/11/2026 | `fact_immobilier` | `loyer_m2_an_eur` | Loyers au-dessus de la borne haute de l'intervalle IQR, calculé par type d'emplacement | 47 sur 1 060 | **Conservé** (proposition à valider par l'équipe) | Villes prime : Londres (20 lignes) et Milan (20 lignes) sur les 5 types d'emplacement et les 4 années, Rome (7 lignes, 2024-2026). Ce sont les loyers les plus élevés du benchmark, pas des erreurs. Aucune ville allemande n'est signalée : le KPI « coût moyen au m² » de l'Allemagne n'est pas concerné | Aucune |
| N-004 | 12/11/2026 | `dim_produit` | `prix_vente_ttc_fr` | Prix sous la borne basse de l'intervalle IQR, calculé par catégorie | 3 sur 147 | **Conservé** (proposition à valider par l'équipe) | Les 3 coloris du modèle HEYDUDE Wendy Youth (P0145 à P0147), à 49,99 €. C'est le seul modèle enfant de la catégorie « Chaussures toile », dont les modèles adultes valent 69,99 € à 79,99 € : un prix enfant plus bas est cohérent. Le contrôle compare ici adultes et enfants ; le grouper par catégorie et cible lèverait le signalement | Aucune |
| N-005 | 12/11/2026 | `fact_logistique` | `cout_transport_palette_eur` | Coûts au-dessus de la borne haute de l'intervalle IQR (391,93 €), calculé sur toute la table | 3 sur 159 | **Conservé** (proposition à valider par l'équipe) | Les 3 liaisons vers Las Palmas (Canaries) depuis chacun des 3 hubs : 3 319 à 3 900 km, 476,52 € à 552,06 € par palette. Le coût est cohérent avec la distance, la plus longue de la table. Limite à connaître : la distance « routière » du générateur est la distance à vol d'oiseau majorée de 25 %, alors que Las Palmas est une île ; ce coût est théorique. La ville porte désormais `zone_insulaire = True` dans `dim_zone_chalandise`, pour l'écarter du benchmark logistique. Sans effet sur l'Allemagne | Aucune |
| N-006 | 12/11/2026 | `fact_prix_releves` | `id_produit` | Valeurs nulles | 1 157 sur 4 153 | **Conservé** (proposition à valider par l'équipe) | Relevés de produits concurrents, absents du catalogue Crocs : il n'existe pas d'`id_produit` à leur attribuer (audit du jeu v1). Tous les relevés Crocs ont le leur. Non imputé | Aucune |
| N-007 | 12/11/2026 | `fact_eligibilite_assortiment` | `adaptation_requise` | Valeurs nulles | 55 sur 882 | **Conservé** (proposition à valider par l'équipe) | Ce sont exactement les 55 couples pays × produit non éligibles : un produit exclu de l'assortiment n'a pas d'adaptation à prévoir. Non imputé | Aucune |
| N-008 | 12/11/2026 | `fact_marche` | `taux_croissance_annuel_pct` | Valeurs nulles | 14 sur 154 | **Conservé** (proposition à valider par l'équipe) | Année 2019, première année de chacune des 14 séries (7 pays × 2 segments) : sans année précédente, le taux de croissance n'est pas calculable. Non imputé | Aucune |
| N-009 | 12/11/2026 | `fact_couts_exploitation` | `salaire_minimum_mensuel_eur` | Valeur nulle | 1 sur 7 | **Conservé** (proposition à valider par l'équipe) | Italie : pas de salaire minimum légal (audit du jeu v1). Une valeur imputée serait un chiffre inventé | Aucune |
| N-015 | 12/11/2026 | `dim_magasin` | `date_fermeture` | Valeurs nulles | 46 sur 49 | **Conservé** (proposition à valider par l'équipe) | Un magasin ouvert n'a pas de date de fermeture, pas plus que le canal e-commerce. Seuls 3 magasins ont fermé (M032 en avril 2023, M023 en avril 2024, M043 en janvier 2025), ajoutés par T2 pour illustrer le biais de survie. Non imputé | Aucune |

### 2. Données réelles

Sections à ouvrir quand les fichiers datés existent dans `data/bronze/`. Pour chaque source, noter le fichier et son URL avant la première ligne du tableau.

#### 2.1 Prix Crocs France et Allemagne (scraping, T3)

Fichiers : `data/bronze/crocs_liste_<site>_<catégorie>_2026-11-12.json` (6 listes de catégorie), `crocs_<site>_<code modèle>_2026-11-12.json` (44 pages produit : 21 pour la France, 23 pour l'Allemagne), `crocs_catalogue.csv` et `crocs_produits.csv`. Sources : <https://www.crocs.fr> et <https://www.crocs.de>, pages publiques de catégorie et de produit, relevé du 12/11/2026.

Aucun doublon. Les 304 valeurs nulles de `prix_barre` (sur 577 lignes) sont attendues : un coloris qui n'est pas en promotion n'a pas de prix barré.

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| N-016 | 12/11/2026 | `crocs_produits` | `prix_affiche` | Prix au-dessus de la borne haute de l'intervalle IQR (49,49 €), calculé par catégorie ; aucun prix sous la borne basse | 6 sur 577 | **Conservé** (proposition à valider par l'équipe) | Un seul modèle : Brooklyn Buckle Low Wedge Sandal (code 207431), à 59,99 € dans 3 coloris (Chalk, Deep Navy, Pink Caramel), relevés à l'identique sur crocs.fr et crocs.de. 59,99 € est le prix hors promotion du modèle : ses 3 autres coloris sont affichés à 35,99 € avec un prix barré de 59,99 €. C'est le prix le plus élevé de la catégorie Sandales (66 lignes, de 20,99 € à 59,99 €), où 30 lignes sont en promotion, ce qui abaisse la borne haute. Ces 6 coloris ne sont pas disponibles à la commande (`disponible = False`) : ils ne font pas partie des 128 paires FR/DE et n'entrent pas dans l'indice prix. Vrais prix affichés, non corrigés | Aucune |

#### 2.2 Indicateurs pays Eurostat (API, T4)

Fichiers : `data/bronze/eurostat_<jeu de données>_2026-11-12.json` (une réponse brute par jeu : `nama_10_cp18`, `prc_hicp_ainr`, `prc_ppp_ind_1`, `sbs_ovw_act`, `tec00114`, `tps00001`, `une_rt_a`), `eurostat_pays.csv` et `eurostat_series.csv`. Source : API de diffusion Eurostat, <https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/>, © Union européenne. Le code du jeu et le filtre de chaque série sont dans les colonnes `jeu_donnees` et `filtre`.

Aucun doublon, aucun constat à examiner dans le rapport de contrôles. Les valeurs nulles sont attendues : une série qu'Eurostat ne publie pas pour un pays (le Royaume-Uni : aucune valeur publiée depuis 2018, première année collectée) porte un TODO dans `note`, sans valeur imputée. Une valeur provisoire, une rupture de série ou une définition différente est signalée par `statut_eurostat` (`p`, `b`, `d`) et conservée telle quelle : aucune correction.

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

#### 2.5 Distances routières (OSRM et Nominatim, T17)

Fichiers : `data/bronze/osrm_geocodage_<id_hub>_2026-11-12.json` (3 communes), `osrm_trajet_<id_hub>_<id_zone>_2026-11-12.json` (36 trajets) et `osrm_distances.csv`. Sources : <https://nominatim.openstreetmap.org/search> et <https://router.project-osrm.org/route/v1/driving>, données © les contributeurs d'OpenStreetMap, licence ODbL.

Collecte sans erreur : 39 requêtes, 3 communes géocodées avec un seul résultat chacune, 36 trajets obtenus. Aucun doublon, aucune valeur nulle.

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| N-014 | 12/11/2026 | `osrm_distances` | `latitude_ville`, `longitude_ville` | Les données OpenStreetMap de T16 ne contiennent pas les coordonnées du centre des villes (seulement les tags de leur limite administrative) | 12 villes, soit les 36 trajets | **Point médian des magasins de chaussures** de chaque ville (décision du 12/11/2026) | Ce point se calcule sur les 992 magasins déjà relevés, sans nouvelle requête à un serveur instable. Il tombe dans le centre commerçant, là où un magasin s'installerait, à 1,3 km au plus du centre simulé de la ville (moins de 1 km pour 11 villes sur 12, 1,27 km pour Berlin). La médiane ignore les magasins isolés en périphérie. OSRM accroche ensuite le point à la route la plus proche, à 109 m au plus. Sur des trajets de 208 à 1 235 km, l'écart avec un centre administratif est négligeable | `city_points` dans `src/collect/osrm.py` |


#### 2.6 Référentiel des taxes (saisie manuelle, T18)

Fichier : `data/manual/taxes_reference.csv`, saisi le 12/11/2026, une ligne par pays de `dim_pays`. Sources par ligne dans `source_url` : Commission européenne (TEDB pour la TVA, situation au 01/07/2026 ; TARIC pour le droit de douane, date de référence 12/11/2026), OCDE (taux d'impôt sur les sociétés 2025), impots.gouv.fr, textes allemands (§ 23 KStG, § 4 SolZG) et UK Trade Tariff. La colonne `note` dit ce que couvre chaque taux.

Aucun doublon. Les valeurs nulles sont attendues : 6 sur 7 pour `taux_tva_reduite_chaussures_enfant_pct` (pas de taux réduit pour les chaussures enfant dans l'UE selon TEDB), 1 sur 7 pour `droit_douane_ue_chaussures_ch64_pct` (le Royaume-Uni est hors de l'union douanière).

La table réelle est chargée à côté de `fact_fiscalite`, sans la remplacer. Les écarts ci-dessous sont des **différences de définition ou de calibrage**, pas des erreurs de saisie : aucune ligne n'est corrigée.

| ID | Date | Table | Colonne | Anomalie constatée | Lignes concernées | Décision | Justification métier | Correction dans le code |
|---|---|---|---|---|---|---|---|---|
| N-017 | 12/11/2026 | `fact_fiscalite` | `taux_tva_chaussures_enfant_pct` | Le jeu simulé recopie le taux normal quand il n'existe pas de taux réduit (BE, DE, ES, FR, IT, NL) ; la table réelle laisse alors la cellule vide | 6 sur 7 (Royaume-Uni : 0 % des deux côtés) | **Conservé** ; écart de définition | Les deux conventions donnent le même taux appliqué : sans taux réduit, une chaussure enfant paie le taux normal. Une vue qui lit la table réelle doit remplacer la cellule vide par le taux normal | Aucune |
| N-018 | 12/11/2026 | `fact_fiscalite` | `taux_impot_societes_pct` | Allemagne : 29,9 % simulé contre 30,06 % réel ; Italie : 27,9 % contre 27,81 %. Les cinq autres pays sont identiques | 2 sur 7 | **Conservé** ; écart de calibrage | Le taux réel est le taux combiné statutaire de l'OCDE pour 2025 : en Allemagne, impôt sur les sociétés et contribution de solidarité (15,825 %) plus une taxe professionnelle moyenne (14,23 %) qui varie selon la commune ; en Italie, 3,9 % d'impôt régional compris. Le taux français de 25 % est le taux national seul : les deux ne se comparent pas directement | Aucune |
| N-019 | 12/11/2026 | `fact_fiscalite` | `droit_import_marchandise_origine_asie_via_fr_pct` | Le jeu simulé met 0 % pour les pays de l'UE et 16 % pour le Royaume-Uni ; la table réelle donne 16,8 % pour les pays de l'UE et laisse le Royaume-Uni vide | 7 sur 7 | **Conservé** ; deux mesures différentes | La colonne simulée mesure le droit supplémentaire d'un produit fabriqué en Asie et réexpédié depuis la France : nul dans l'UE, car le droit est déjà payé à l'entrée. La colonne réelle mesure ce droit d'entrée dans l'UE (TARIC, droit de pays tiers sur le code NC 6402 99), le même pour la France et l'Allemagne. Pour le Royaume-Uni, les 16 % simulés correspondent au tarif britannique relevé (16 %, UK Trade Tariff), noté dans la colonne `note` | Aucune |
| N-020 | 12/11/2026 | `dim_produit` | `taux_droit_ue_pct` | 16,9 % simulé pour le code SH 6402.99 contre 16,8 % dans TARIC (codes NC 6402 99 10 à 6402 99 98) | 87 produits sur 147 | **Conservé** ; écart de calibrage à signaler | Écart de 0,1 point, sans effet visible sur la marge post-taxe. Le générateur est gelé (règle 9) : le droit réel n'est pas réinjecté dans `dim_produit`. Les autres codes du catalogue simulé (6401.92, 6402.20, 6402.91, 6404.19, 3926.40) n'ont pas été vérifiés dans TARIC | Aucune |
