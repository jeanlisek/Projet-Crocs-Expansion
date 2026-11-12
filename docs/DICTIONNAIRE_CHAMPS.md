# Dictionnaire des champs

> Généré par `python -m src.collect.dictionnaire` à partir de l'entrepôt `data/gold/warehouse.duckdb` : ne pas modifier à la main, relancer le script. Types et exemples lus dans les données ; descriptions et sources tirées de `docs/DICTIONNAIRE_DONNEES.md`, du README et des scripts ; chaque formule est vérifiée sur les données. `TODO` = information manquante.

30 tables et 26 vues. Une table simulée porte `est_simule` = vrai sur toutes ses lignes ; « Source » donne alors la source publique sur laquelle la simulation est calibrée.

## Dimensions

### `dim_pays`

Pays étudiés : la France (référence) et six pays candidats. Table simulée, 7 lignes. Grain : `code_pays`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `nom_pays` | Texte | Nom du pays | — | Belgique | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `devise` | Texte | Devise du pays (code ISO 4217) | — | EUR | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `taux_change_vs_eur` | Décimal | Unités de la devise pour 1 € | — | 1 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `population_millions` | Décimal | Population, en millions d'habitants | — | 11.8 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `pib_habitant_spa_ue100` | Entier | PIB par habitant en standard de pouvoir d'achat (UE = 100) | — | 117 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `taux_chomage_pct` | Décimal | Taux de chômage (%) | — | 5.9 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `indice_niveau_prix_chaussures_ue100` | Entier | Indice de niveau de prix des chaussures (UE27 = 100) | — | 106 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `indice_confiance_conso` | Entier | Indicateur de confiance des consommateurs (solde d'opinion) | — | -10 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `langue_principale` | Texte | Langue principale | — | français/néerlandais | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `membre_ue` | Booléen | Vrai si le pays est membre de l'Union européenne | — | True | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `union_douaniere_avec_fr` | Booléen | Vrai si le pays est dans l'union douanière avec la France | — | True | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `est_pays_reference` | Booléen | Vrai pour la France, pays de référence | — | False | Simulé : generate_data.py (seed 2027), calibré sur Eurostat |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `dim_temps`

Calendrier mensuel 2019-2029. Table simulée, 132 lignes. Grain : `id_date`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_date` | Entier | Mois, au format AAAAMM (clé de dim_temps) | — | 201901 | Simulé : generate_data.py (seed 2027) |
| `date_debut_mois` | Date | Premier jour du mois | — | 2019-01-01 | Simulé : generate_data.py (seed 2027) |
| `annee` | Entier | Année | — | 2019 | Simulé : generate_data.py (seed 2027) |
| `trimestre` | Texte | Trimestre (T1 à T4) | — | T1 | Simulé : generate_data.py (seed 2027) |
| `mois` | Entier | Numéro du mois (1 à 12) | — | 1 | Simulé : generate_data.py (seed 2027) |
| `nom_mois` | Texte | Nom du mois en français | — | janvier | Simulé : generate_data.py (seed 2027) |
| `saison` | Texte | Saison (Hiver, Printemps, Été, Automne) | — | Hiver | Simulé : generate_data.py (seed 2027) |
| `periode_soldes_fr` | Booléen | Vrai en janvier et juillet, mois des soldes en France | — | True | Simulé : generate_data.py (seed 2027) |
| `black_friday` | Booléen | Vrai en novembre, mois du Black Friday | — | False | Simulé : generate_data.py (seed 2027) |
| `est_historique` | Booléen | Vrai jusqu'à octobre 2026 (données observées), faux ensuite | — | True | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `dim_produit`

Catalogue France : 147 SKU (30 modèles × coloris), Crocs et HEYDUDE. Table simulée, 147 lignes. Grain : `id_produit`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_produit` | Texte | Identifiant du produit (clé de dim_produit) | — | P0001 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `sku` | Texte | Référence article (modèle + coloris) | — | CR-CLASSICCLO-NOI001 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `marque` | Texte | Marque (Crocs ou HEYDUDE) | — | Crocs | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `categorie` | Texte | Catégorie (Sabots, Sandales, Bottes, Jibbitz, Chaussures toile) | — | Sabots | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `sous_categorie` | Texte | Sous-catégorie | — | Classic | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `modele` | Texte | Nom du modèle | — | Classic Clog | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `coloris` | Texte | Coloris | — | Noir | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `cible` | Texte | Cible (Adulte, Mixte, Enfant, Bébé) | — | Adulte | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `prix_vente_ttc_fr` | Décimal | Prix de vente public en France, TTC (€) | — | 49.99 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `prix_vente_ht_fr` | Décimal | Prix de vente public en France, HT (€) | prix_vente_ttc_fr ÷ 1,20 | 41.66 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `cout_fob_usd` | Décimal | Coût d'achat FOB à l'usine ($) | — | 9.69 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `cout_fob_eur` | Décimal | Coût d'achat FOB converti en euros (€) | cout_fob_usd × 0,92 (taux USD → EUR du générateur) | 8.91 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `cout_fret_unitaire_eur` | Décimal | Fret maritime et pré/post-acheminement par paire (€) | — | 0.83 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `droits_douane_ue_eur` | Décimal | Droits de douane UE par paire, sur la valeur CAF (€) | (cout_fob_eur + cout_fret_unitaire_eur) × taux_droit_ue_pct ÷ 100 | 1.65 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `cout_debarque_eur` | Décimal | Coût débarqué par paire : achat, fret et droits (€) | cout_fob_eur + cout_fret_unitaire_eur + droits_douane_ue_eur | 11.39 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `code_sh` | Texte | Code du système harmonisé (nomenclature douanière) | — | 6402.99 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `taux_droit_ue_pct` | Décimal | Taux de droit de douane UE du code SH (%) | — | 16.9 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `taux_droit_uk_pct` | Décimal | Taux de droit de douane britannique du code SH (%) | — | 16 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `pays_origine` | Texte | Pays de fabrication | — | Vietnam | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `poids_unitaire_kg` | Décimal | Poids d'une paire (kg) | — | 0.42 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `profil_saisonnier` | Texte | Profil de saisonnalité des ventes (plat, ete, hiver, noel...) | — | ete | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `produit_sous_licence` | Booléen | Vrai pour un produit sous licence (Disney, Pokémon...) | — | False | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `annee_lancement` | Entier | Année de lancement du produit | — | 2020 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `statut` | Texte | Statut du produit (Actif, Fin de série) | — | Actif | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `taux_marge_theorique_pct` | Décimal | Taux de marge théorique sur le prix HT (%) | (prix_vente_ht_fr − cout_debarque_eur) ÷ prix_vente_ht_fr × 100 | 72.7 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `dim_magasin`

Réseau France : 48 magasins physiques et le canal e-commerce. Table simulée, 49 lignes. Grain : `id_magasin`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_magasin` | Texte | Identifiant du magasin (clé de dim_magasin) | — | M001 | Simulé : generate_data.py (seed 2027) |
| `nom_magasin` | Texte | Nom du magasin | — | Crocs Paris Centre-ville 1 | Simulé : generate_data.py (seed 2027) |
| `ville` | Texte | Nom de la ville | — | Paris | Simulé : generate_data.py (seed 2027) |
| `region` | Texte | Région administrative française | — | Île-de-France | Simulé : generate_data.py (seed 2027) |
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | FR | Simulé : generate_data.py (seed 2027) |
| `latitude` | Décimal | Latitude (degrés décimaux, WGS 84) | — | 48.8281 | Simulé : generate_data.py (seed 2027) |
| `longitude` | Décimal | Longitude (degrés décimaux, WGS 84) | — | 2.3691 | Simulé : generate_data.py (seed 2027) |
| `type_emplacement` | Texte | Format : Centre-ville, Centre commercial, Outlet, Gare / Aéroport, E-commerce | — | Centre-ville | Simulé : generate_data.py (seed 2027) |
| `surface_vente_m2` | Entier | Surface de vente (m²) | — | 117 | Simulé : generate_data.py (seed 2027) |
| `annee_ouverture` | Entier | Année d'ouverture | — | 2015 | Simulé : generate_data.py (seed 2027) |
| `loyer_annuel_eur` | Entier | Loyer annuel (€) | — | 229505 | Simulé : generate_data.py (seed 2027) |
| `nb_etp` | Décimal | Effectif en équivalents temps plein | — | 4.7 | Simulé : generate_data.py (seed 2027) |
| `capex_ouverture_eur` | Entier | Investissement d'ouverture (€) | — | 221429 | Simulé : generate_data.py (seed 2027) |
| `id_hub_rattachement` | Texte | Hub qui approvisionne le magasin | — | H01 | Simulé : generate_data.py (seed 2027) |
| `distance_hub_km` | Décimal | Distance au hub de rattachement (km) | — | 39 | Simulé : generate_data.py (seed 2027) |
| `statut` | Texte | Statut du magasin (Ouvert, Fermé) | — | Ouvert | Simulé : generate_data.py (seed 2027) |
| `date_fermeture` | Date | Date de fermeture, vide si le magasin est ouvert | — | 2024-04-30 | Simulé : generate_data.py (seed 2027) |
| `canal` | Texte | Canal (Magasin physique, Digital) | — | Magasin physique | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `dim_hub_logistique`

Entrepôts : deux hubs France et le centre de distribution Crocs EMEA (Dordrecht). Table simulée, 3 lignes. Grain : `id_hub`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_hub` | Texte | Identifiant du hub logistique (clé de dim_hub_logistique) | — | H01 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `nom_hub` | Texte | Nom du hub | — | Hub Île-de-France | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `ville` | Texte | Nom de la ville | — | Moissy-Cramayel | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | FR | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `latitude` | Décimal | Latitude (degrés décimaux, WGS 84) | — | 48.6236 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `longitude` | Décimal | Longitude (degrés décimaux, WGS 84) | — | 2.5939 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `surface_m2` | Entier | Surface de l'entrepôt (m²) | — | 28000 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `type_hub` | Texte | Type d'entrepôt | — | Entrepôt groupe (simulé) | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `annee_ouverture` | Entier | Année d'ouverture | — | 2015 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `capacite_palettes` | Entier | Capacité de stockage (palettes) | — | 30800 | Simulé : generate_data.py (seed 2027), calibré sur Crocs Inc. 10-K 2024-2025 |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `dim_zone_chalandise`

Villes cibles des pays candidats (53 villes). Table simulée, 53 lignes. Grain : `id_zone`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | Simulé : generate_data.py (seed 2027) |
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | DE | Simulé : generate_data.py (seed 2027) |
| `ville` | Texte | Nom de la ville | — | Berlin | Simulé : generate_data.py (seed 2027) |
| `latitude` | Décimal | Latitude (degrés décimaux, WGS 84) | — | 52.52 | Simulé : generate_data.py (seed 2027) |
| `longitude` | Décimal | Longitude (degrés décimaux, WGS 84) | — | 13.405 | Simulé : generate_data.py (seed 2027) |
| `population_ville_millions` | Décimal | Population de la ville (millions d'habitants) | — | 3.75 | Simulé : generate_data.py (seed 2027) |
| `population_zone_chalandise_millions` | Décimal | Population de la zone de chalandise (millions) | — | 9.35 | Simulé : generate_data.py (seed 2027) |
| `indice_revenu_ue100` | Entier | Indice de revenu de la zone (UE = 100) | — | 116 | Simulé : generate_data.py (seed 2027) |
| `indice_frequentation_commerce` | Décimal | Indice de fréquentation commerciale, sans unité, plafonné à 100 : 40 + 9 × population_ville_millions, plus un aléa d'écart-type 6 (pas une mesure observée) | — | 70.7 | Simulé : generate_data.py (seed 2027) |
| `nb_centres_commerciaux` | Entier | Nombre de centres commerciaux de la zone | — | 19 | Simulé : generate_data.py (seed 2027) |
| `part_touristes_pct` | Décimal | Part des touristes dans la fréquentation (%) | — | 3.5 | Simulé : generate_data.py (seed 2027) |
| `climat_temperature_moy_ete` | Décimal | Température moyenne en été (°C) | — | 21.8 | Simulé : generate_data.py (seed 2027) |
| `nb_points_vente_concurrents` | Entier | Points de vente des concurrents nommés dans la ville | — | 286 | Simulé : generate_data.py (seed 2027) |
| `densite_concurrentielle_pour_100k_hab` | Décimal | Points de vente concurrents pour 100 000 habitants de la ville | nb_points_vente_concurrents ÷ (population_ville_millions × 10) | 7.63 | Simulé : generate_data.py (seed 2027) |
| `zone_insulaire` | Booléen | Vrai pour une ville sur une île (Las Palmas, Palma) | — | False | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `dim_concurrent`

Marques et enseignes du segment casual moulé & sandales. Table simulée, 12 lignes. Grain : `id_concurrent`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_concurrent` | Texte | Identifiant de la marque ou enseigne (clé de dim_concurrent ; C00 = Crocs) | — | C00 | Simulé : generate_data.py (seed 2027) |
| `nom_concurrent` | Texte | Nom de la marque ou de l'enseigne | — | Crocs | Simulé : generate_data.py (seed 2027) |
| `type_acteur` | Texte | Type d'acteur (marque, distributeur, équipementier...) | — | Marque (nous) | Simulé : generate_data.py (seed 2027) |
| `positionnement_prix` | Texte | Positionnement prix (Entrée, Moyen, Premium...) | — | Moyen | Simulé : generate_data.py (seed 2027) |
| `prix_moyen_eur` | Entier | Prix moyen d'une paire (€) | — | 50 | Simulé : generate_data.py (seed 2027) |
| `pays_origine` | Texte | Pays d'origine de l'acteur | — | USA | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

## Faits

### `fact_ventes_france`

Ventes du réseau France, par mois, magasin et produit. Table simulée, 246 476 lignes. Grain : `id_date, id_magasin, id_produit`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_vente` | Entier | Identifiant de la ligne de vente | — | 1 | Simulé : generate_data.py (seed 2027) |
| `id_date` | Entier | Mois, au format AAAAMM (clé de dim_temps) | — | 202301 | Simulé : generate_data.py (seed 2027) |
| `id_magasin` | Texte | Identifiant du magasin (clé de dim_magasin) | — | M001 | Simulé : generate_data.py (seed 2027) |
| `id_produit` | Texte | Identifiant du produit (clé de dim_produit) | — | P0001 | Simulé : generate_data.py (seed 2027) |
| `quantite_vendue` | Entier | Paires vendues | — | 22 | Simulé : generate_data.py (seed 2027) |
| `ca_brut_ttc_eur` | Décimal | Chiffre d'affaires TTC avant remise (€) | — | 1099.78 | Simulé : generate_data.py (seed 2027) |
| `ca_net_ttc_eur` | Décimal | Chiffre d'affaires TTC après remise (€) | — | 849.58 | Simulé : generate_data.py (seed 2027) |
| `ca_net_ht_eur` | Décimal | Chiffre d'affaires HT après remise (€) | ca_net_ttc_eur ÷ 1,20 | 707.98 | Simulé : generate_data.py (seed 2027) |
| `cout_marchandises_eur` | Décimal | Coût des marchandises vendues : coût débarqué, +2 % par an depuis 2023 (€) | — | 250.58 | Simulé : generate_data.py (seed 2027) |
| `remise_eur` | Décimal | Remises accordées : soldes, Black Friday, outlet, fins de série (€) | ca_brut_ttc_eur − ca_net_ttc_eur | 250.2 | Simulé : generate_data.py (seed 2027) |
| `marge_brute_eur` | Décimal | Marge brute (€) | ca_net_ht_eur − cout_marchandises_eur | 457.4 | Simulé : generate_data.py (seed 2027) |
| `quantite_retournee` | Entier | Paires retournées | — | 0 | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_marche`

Taille du marché par pays, année et segment (projections 2026-2029 incluses). Table simulée, 154 lignes. Grain : `code_pays, annee, segment`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `annee` | Entier | Année | — | 2019 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `segment` | Texte | Segment (Casual moulé & sandales, Chaussures total) | — | Casual moulé & sandales | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `taille_marche_meur` | Décimal | Taille du marché (M€) | — | 161.9 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `taux_croissance_annuel_pct` | Décimal | Croissance annuelle du marché (%) | — | -15.69 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `est_projection` | Booléen | Vrai pour une projection (2026-2029), faux pour une observation | — | False | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Panel marché simulé (calibré Euromonitor/Statista) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_parts_de_marche`

Parts de marché en valeur par pays, année et marque (segment casual moulé & sandales). Table simulée, 420 lignes. Grain : `code_pays, annee, id_concurrent`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `annee` | Entier | Année | — | 2021 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `id_concurrent` | Texte | Identifiant de la marque ou enseigne (clé de dim_concurrent ; C00 = Crocs) | — | C00 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `part_marche_valeur_pct` | Décimal | Part de marché en valeur (%) | — | 13.86 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `ca_estime_meur` | Décimal | Chiffre d'affaires estimé de la marque dans le segment (M€) | part_marche_valeur_pct ÷ 100 × fact_marche.taille_marche_meur (segment Casual moulé & sandales, même pays et même année) | 22.5 | Simulé : generate_data.py (seed 2027), calibré sur Euromonitor / Statista |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_presence_concurrents`

Points de vente des concurrents par ville cible. Table simulée, 512 lignes. Grain : `id_zone, id_concurrent`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | Simulé : generate_data.py (seed 2027) |
| `id_concurrent` | Texte | Identifiant de la marque ou enseigne (clé de dim_concurrent ; C00 = Crocs) | — | C00 | Simulé : generate_data.py (seed 2027) |
| `nb_points_de_vente` | Entier | Points de vente de l'acteur dans la ville | — | 32 | Simulé : generate_data.py (seed 2027) |
| `dont_magasins_propres` | Entier | Dont magasins en propre | — | 0 | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_immobilier`

Loyers et vacance commerciale par ville cible, année et type d'emplacement. Table simulée, 1 060 lignes. Grain : `id_zone, annee, type_emplacement`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | Simulé : generate_data.py (seed 2027), calibré sur Cushman & Wakefield, Main Streets Across the World |
| `annee` | Entier | Année | — | 2023 | Simulé : generate_data.py (seed 2027), calibré sur Cushman & Wakefield, Main Streets Across the World |
| `type_emplacement` | Texte | Type d'emplacement | — | Centre commercial | Simulé : generate_data.py (seed 2027), calibré sur Cushman & Wakefield, Main Streets Across the World |
| `loyer_m2_an_eur` | Entier | Loyer (€/m²/an) | — | 758 | Simulé : generate_data.py (seed 2027), calibré sur Cushman & Wakefield, Main Streets Across the World |
| `charges_m2_an_eur` | Entier | Charges locatives (€/m²/an) | — | 99 | Simulé : generate_data.py (seed 2027), calibré sur Cushman & Wakefield, Main Streets Across the World |
| `taux_vacance_pct` | Décimal | Taux de vacance commerciale (%) | — | 4.9 | Simulé : generate_data.py (seed 2027), calibré sur Cushman & Wakefield, Main Streets Across the World |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_logistique`

Coûts et délais de transport de chaque hub vers chaque ville. Table simulée, 159 lignes. Grain : `id_hub, id_zone`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_hub` | Texte | Identifiant du hub logistique (clé de dim_hub_logistique) | — | H01 | Simulé : generate_data.py (seed 2027) |
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | Simulé : generate_data.py (seed 2027) |
| `distance_route_km` | Entier | Distance routière du hub à la ville (km) | — | 1096 | Simulé : generate_data.py (seed 2027) |
| `delai_livraison_jours` | Décimal | Délai de livraison (jours) | — | 2.7 | Simulé : generate_data.py (seed 2027) |
| `cout_transport_palette_eur` | Décimal | Coût de transport d'une palette (€) | — | 187.44 | Simulé : generate_data.py (seed 2027) |
| `cout_transport_unitaire_eur` | Décimal | Coût de transport par paire (€) | cout_transport_palette_eur ÷ 180 (paires par palette) | 1.041 | Simulé : generate_data.py (seed 2027) |
| `frais_dedouanement_par_envoi_eur` | Décimal | Frais de dédouanement par envoi (€) | — | 0 | Simulé : generate_data.py (seed 2027) |
| `emissions_co2_kg_palette` | Décimal | Émissions de CO₂ par palette (kg) | — | 67.9 | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_fiscalite`

Fiscalité par pays : TVA, impôt sur les sociétés, droits, éco-contribution. Table simulée, 7 lignes. Grain : `code_pays`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `taux_tva_standard_pct` | Décimal | Taux normal de TVA (%) | — | 21 | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `taux_tva_chaussures_enfant_pct` | Décimal | Taux de TVA sur les chaussures enfant (%) | — | 21 | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `taux_impot_societes_pct` | Décimal | Taux de l'impôt sur les sociétés (%) | — | 25 | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `taxe_locale_additionnelle_pct` | Décimal | Taxe locale additionnelle (%) | — | 0 | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `eco_contribution_par_paire_eur` | Décimal | Éco-contribution par paire (€) | — | 0 | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `droit_import_marchandise_origine_asie_via_fr_pct` | Décimal | Droit d'import d'un produit fabriqué en Asie, expédié depuis la France (%) | — | 0 | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `regime_douanier` | Texte | Régime douanier vis-à-vis de la France | — | Marché unique UE | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `regime_rep` | Texte | Filière de responsabilité élargie du producteur (REP) applicable | — | Aucune REP chaussures | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `note` | Texte | Commentaire sur le régime douanier | — | Libre circulation : droits déjà acquittés à l'entrée UE | Simulé : generate_data.py (seed 2027), calibré sur Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_couts_exploitation`

Coûts d'exploitation d'un magasin par pays (2026). Table simulée, 7 lignes. Grain : `code_pays, annee_reference`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `salaire_brut_mensuel_vendeur_eur` | Entier | Salaire brut mensuel d'un vendeur (€) | — | 2400 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `taux_charges_patronales_pct` | Décimal | Charges patronales (% du brut) | — | 27 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `salaire_minimum_mensuel_eur` | Décimal | Salaire minimum mensuel (€) | — | 2070 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `cout_amenagement_m2_eur` | Entier | Coût d'aménagement du magasin (€/m²) | — | 1600 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `cout_energie_m2_an_eur` | Entier | Coût de l'énergie (€/m²/an) | — | 50 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `budget_marketing_lancement_eur` | Entier | Budget marketing de lancement par magasin (€) | — | 35000 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `duree_hebdo_travail_h` | Entier | Durée hebdomadaire du travail (heures) | — | 38 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `cout_complet_annuel_etp_eur` | Décimal | Coût complet annuel d'un ETP (€) | salaire_brut_mensuel_vendeur_eur × 12,5 × (1 + taux_charges_patronales_pct ÷ 100) | 38100 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `annee_reference` | Entier | Année de référence des coûts | — | 2026 | Simulé : generate_data.py (seed 2027), calibré sur Eurostat (salaires minimum) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_prix_releves`

Relevés de prix trimestriels (scraping simulé) : Crocs et équivalents concurrents. Table simulée, 4 153 lignes. Grain : `id_releve`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_releve` | Entier | Identifiant du relevé | — | 1 | Simulé : generate_data.py (seed 2027) |
| `id_date` | Entier | Mois, au format AAAAMM (clé de dim_temps) | — | 202501 | Simulé : generate_data.py (seed 2027) |
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | FR | Simulé : generate_data.py (seed 2027) |
| `enseigne` | Texte | Site ou enseigne du relevé | — | crocs.fr | Simulé : generate_data.py (seed 2027) |
| `id_concurrent` | Texte | Identifiant de la marque ou enseigne (clé de dim_concurrent ; C00 = Crocs) | — | C00 | Simulé : generate_data.py (seed 2027) |
| `id_produit` | Texte | Identifiant du produit (clé de dim_produit) | — | P0001 | Simulé : generate_data.py (seed 2027) |
| `libelle_produit` | Texte | Libellé du produit relevé | — | Classic Clog | Simulé : generate_data.py (seed 2027) |
| `categorie` | Texte | Catégorie du produit | — | Sabots | Simulé : generate_data.py (seed 2027) |
| `prix_affiche_eur` | Décimal | Prix affiché (€) | — | 49.99 | Simulé : generate_data.py (seed 2027) |
| `prix_affiche_devise_locale` | Décimal | Prix affiché dans la devise du pays | prix_affiche_eur × 0,85 au Royaume-Uni (GBP), prix_affiche_eur ailleurs | 49.99 | Simulé : generate_data.py (seed 2027) |
| `en_promotion` | Booléen | Vrai si le produit est en promotion au moment du relevé | — | False | Simulé : generate_data.py (seed 2027) |
| `taux_remise_pct` | Décimal | Remise appliquée (%) | — | 0 | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_penetration_categories`

Part des consommateurs (18-65 ans) ayant acheté la catégorie sur 12 mois. Table simulée, 70 lignes. Grain : `code_pays, annee, categorie`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027) |
| `annee` | Entier | Année | — | 2024 | Simulé : generate_data.py (seed 2027) |
| `categorie` | Texte | Catégorie de produit | — | Bottes | Simulé : generate_data.py (seed 2027) |
| `taux_penetration_pct` | Décimal | Part des 18-65 ans ayant acheté la catégorie sur 12 mois (%) | — | 14.5 | Simulé : generate_data.py (seed 2027) |
| `panier_moyen_categorie_eur` | Décimal | Panier moyen dans la catégorie (€) | — | 58.9 | Simulé : generate_data.py (seed 2027) |
| `taille_echantillon` | Entier | Taille de l'échantillon de l'enquête | — | 2588 | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Enquête consommateurs simulée (panel online) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_eligibilite_assortiment`

Éligibilité de chaque produit du catalogue France dans chaque pays candidat. Table simulée, 882 lignes. Grain : `code_pays, id_produit`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027) |
| `id_produit` | Texte | Identifiant du produit (clé de dim_produit) | — | P0001 | Simulé : generate_data.py (seed 2027) |
| `eligible` | Booléen | Vrai si le produit peut être vendu dans le pays | — | True | Simulé : generate_data.py (seed 2027) |
| `motif` | Texte | Motif d'exclusion, ou « Éligible » | — | Éligible | Simulé : generate_data.py (seed 2027) |
| `indice_demande_locale` | Décimal | Indice de demande locale pour le produit | — | 1.09 | Simulé : generate_data.py (seed 2027) |
| `recommandation_assortiment` | Texte | Recommandation (Assortiment cœur, optionnel, Exclu) | — | Assortiment cœur | Simulé : generate_data.py (seed 2027) |
| `adaptation_requise` | Texte | Adaptation nécessaire (étiquetage, notice...), vide si aucune | — | Notice multilingue NL/FR | Simulé : generate_data.py (seed 2027) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

### `fact_tendances_recherche`

Intérêt de recherche mensuel pour « crocs » (type Google Trends, 0-100). Table simulée, 406 lignes. Grain : `code_pays, id_date, mot_cle`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Simulé : generate_data.py (seed 2027), calibré sur Google Trends |
| `id_date` | Entier | Mois, au format AAAAMM (clé de dim_temps) | — | 202201 | Simulé : generate_data.py (seed 2027), calibré sur Google Trends |
| `mot_cle` | Texte | Mot-clé recherché | — | crocs | Simulé : generate_data.py (seed 2027), calibré sur Google Trends |
| `indice_interet` | Entier | Intérêt de recherche (0-100, 100 = pic de la période) | — | 22 | Simulé : generate_data.py (seed 2027), calibré sur Google Trends |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Générateur Python src/simulate/generate_data.py (seed 2027) | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | True | Pipeline : bronze_to_silver.py |

## Tables réelles

### `osm_villes`

Villes allemandes cibles dans OpenStreetMap : limite administrative et magasins. Table réelle, 12 lignes. Grain : `id_zone`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `ville` | Texte | Nom de la ville | — | Berlin | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `osm_relation_id` | Entier | Identifiant OSM de la limite administrative de la ville | — | 62422 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `nom_osm` | Texte | Nom de la ville dans OSM | — | Berlin | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `niveau_administratif` | Entier | Niveau administratif OSM (4 ville-État, 6 ville-arrondissement, 8 commune) | — | 4 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `code_communal` | Texte | Code officiel de la commune (AGS, 8 chiffres) | — | 11000000 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `population_osm` | Entier | Population indiquée dans OSM (comparaison seulement) | — | 3769962 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `annee_population_osm` | Entier | Année de la population OSM, quand le tag en donne une seule | — | 2020 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `tag_annee_population_osm` | Texte | Tag OSM d'où vient l'année de la population | — | source:population | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `source_population_osm` | Texte | Source de la population indiquée dans OSM | — | https://download.statistik-berlin-brandenburg.de/fa93e3bd19… | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `nb_magasins_chaussures` | Entier | Magasins de chaussures (shop=shoes) dans la ville | nombre de lignes de osm_magasins_chaussures de la ville | 251 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `nb_magasins_avec_enseigne` | Entier | Dont magasins avec une enseigne (tag brand) | — | 91 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | OpenStreetMap via l'API Overpass (https://overpass-api.de/a… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `osm_magasins_chaussures`

Magasins de chaussures (shop=shoes) des villes allemandes cibles. Table réelle, 992 lignes. Grain : `osm_type, osm_id`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z007 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `osm_type` | Texte | Type d'objet OSM (node, way, relation) | — | node | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `osm_id` | Entier | Identifiant OSM de l'objet | — | 247700599 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `nom` | Texte | Nom du magasin (tag name), vide s'il manque | — | Deichmann | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `enseigne` | Texte | Enseigne (tag brand), vide s'il manque | — | Deichmann | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `latitude` | Décimal | Latitude (degrés décimaux, WGS 84) | — | 51.2127 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `longitude` | Décimal | Longitude (degrés décimaux, WGS 84) | — | 6.80694 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | OpenStreetMap via l'API Overpass (https://overpass-api.de/a… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `destatis_population_villes`

Population officielle des villes allemandes cibles. Table réelle, 12 lignes. Grain : `id_zone`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `ville` | Texte | Nom de la ville | — | Berlin | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `code_communal` | Texte | Code officiel de la commune (AGS, 8 chiffres) | — | 11000000 | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `cle_regionale` | Texte | Clé régionale officielle (ARS, 12 chiffres) | — | 110000000000 | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `nom_destatis` | Texte | Nom de la commune dans le classeur Destatis | — | Berlin, Stadt | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `population` | Entier | Population officielle | — | 3685265 | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `date_reference` | Date | Date de référence de la population | — | 2024-12-31 | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `source_url` | Texte | Page Destatis du classeur | — | https://www.destatis.de/DE/Themen/Laender-Regionen/Regional… | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `date_consultation` | Date | Jour du téléchargement du classeur | — | 2026-11-12 | Destatis, Gemeindeverzeichnis (src/collect/destatis.py) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Statistisches Bundesamt (Destatis), Gemeindeverzeichnis : S… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `osrm_distances`

Distance et durée routières de chaque hub vers chaque ville allemande cible. Table réelle, 36 lignes. Grain : `id_hub, id_zone`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `id_hub` | Texte | Identifiant du hub logistique (clé de dim_hub_logistique) | — | H01 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `id_zone` | Texte | Identifiant de la ville cible (clé de dim_zone_chalandise) | — | Z001 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `commune_hub` | Texte | Commune du hub | — | Moissy-Cramayel | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `ville` | Texte | Nom de la ville | — | Berlin | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `latitude_hub` | Décimal | Latitude du hub géocodé (Nominatim) | — | 48.6272 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `longitude_hub` | Décimal | Longitude du hub géocodé (Nominatim) | — | 2.59371 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `latitude_ville` | Décimal | Latitude de la ville | — | 52.5105 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `longitude_ville` | Décimal | Longitude de la ville | — | 13.3944 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `distance_route_km` | Décimal | Distance routière (km) | — | 1085 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `duree_h` | Décimal | Durée du trajet en voiture (heures) | — | 11.1 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `ecart_route_hub_m` | Entier | Écart entre le hub et le point de route le plus proche (m) | — | 24 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `ecart_route_ville_m` | Entier | Écart entre la ville et le point de route le plus proche (m) | — | 17 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Itinéraires : OSRM (https://router.project-osrm.org/route/v… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `crocs_catalogue`

Catalogue listé sur crocs.fr et crocs.de : une ligne par site, catégorie, modèle et coloris. Table réelle, 3 472 lignes. Grain : `site, categorie, code_modele, code_coloris`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `site` | Texte | Site relevé (FR = crocs.fr, DE = crocs.de) | — | DE | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `categorie` | Texte | Page de catégorie où la référence est listée (Sabots, Sandales, Chaussures) | — | Chaussures | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `code_modele` | Texte | Code modèle Crocs (identique sur les deux sites) | — | 10001 | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `nom` | Texte | Nom du modèle | — | Classic Clog | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `code_coloris` | Texte | Code coloris Crocs (identique sur les deux sites) | — | 001 | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `coloris` | Texte | Nom du coloris | — | Black | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Site https://www.crocs.de, pages de la catégorie /c/silhoue… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `crocs_produits`

Prix relevés sur les pages produit de crocs.fr et crocs.de, par modèle et coloris. Table réelle, 577 lignes. Grain : `site, code_modele, code_coloris`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `site` | Texte | Site relevé (FR = crocs.fr, DE = crocs.de) | — | DE | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `code_modele` | Texte | Code modèle Crocs | — | 10001 | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `nom` | Texte | Nom du modèle | — | Classic Clog | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `code_coloris` | Texte | Code coloris Crocs | — | 001 | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `coloris` | Texte | Nom du coloris | — | Black | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `categorie` | Texte | Catégorie exclusive du modèle : Sabots, sinon Sandales, sinon Chaussures | — | Sabots | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `silhouette` | Texte | Silhouette indiquée par le site (Clog, Sandal, Boot...) | — | Clog | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `categorie_site` | Texte | Catégorie principale du modèle sur le site | — | clogs | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `genre` | Texte | Cible indiquée par le site (unisex, womens, mens, kids) | — | unisex | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `prix_affiche` | Décimal | Prix affiché TTC, le plus bas des pointures du coloris (€) | — | 38.49 | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `prix_barre` | Décimal | Prix de référence barré, vide s'il n'y a pas de promotion (€) | — | 54.99 | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `devise` | Texte | Devise du prix | — | EUR | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `disponible` | Booléen | Vrai si au moins une pointure du coloris est commandable | — | True | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `url` | Texte | Page du produit, avec le coloris en paramètre (?cid=) | — | https://www.crocs.de/p/classic-clog/10001.html?cid=001 | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py) |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Site https://www.crocs.de, page produit publique, relevé du… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `taxes_reference`

Référentiel des taxes par pays : TVA, impôt sur les sociétés, droit de douane UE sur les chaussures (chapitre 64). Table réelle, 7 lignes. Grain : `code_pays`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `taux_tva_standard_pct` | Décimal | Taux normal de TVA (%) | — | 21 | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `taux_tva_reduite_chaussures_enfant_pct` | Décimal | Taux de TVA réduit sur les chaussures enfant (%) ; vide s'il n'en existe pas | — | 0 | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `taux_impot_societes_pct` | Décimal | Taux de l'impôt sur les sociétés (%) ; ce qu'il inclut est dans la note | — | 25 | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `droit_douane_ue_chaussures_ch64_pct` | Décimal | Droit de douane de pays tiers de l'UE sur les chaussures, code NC 6402 99 (%) ; vide hors union douanière | — | 16.8 | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `source_url` | Texte | Pages officielles d'où viennent les valeurs, séparées par un point-virgule | — | https://ec.europa.eu/taxation_customs/tedb/#/vat-search;htt… | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `date_consultation` | Date | Jour où les pages ont été lues | — | 2026-11-12 | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `note` | Texte | Ce que couvre chaque taux et pourquoi une cellule est vide | — | TVA : TEDB (Commission européenne), recherche sur le code N… | Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : Commission européenne (TEDB, TARIC), OCDE, textes nationaux |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Saisie manuelle depuis les sources officielles, URL par lig… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `eurostat_pays`

Indicateurs pays Eurostat : une ligne par pays et indicateur (dernière année publiée). Table réelle, 77 lignes. Grain : `code_pays, indicateur`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `indicateur` | Texte | Nom de l'indicateur | — | commerce_chaussures_ca_meur | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `libelle_eurostat` | Texte | Libellés Eurostat des codes du filtre | — | Retail sale of footwear and leather goods in specialised st… | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `jeu_donnees` | Texte | Code du jeu de données Eurostat | — | sbs_ovw_act | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `filtre` | Texte | Codes des dimensions retenues (dimension=code) | — | nace_r2=G4772;indic_sbs=NETTUR_MEUR | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `annee` | Entier | Dernière année publiée, vide si aucune | — | 2024 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `valeur` | Décimal | Valeur publiée, vide si Eurostat n'en publie pas | — | 1378 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `unite` | Texte | Unité de la valeur | — | millions d'euros | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `statut_eurostat` | Texte | Statut Eurostat (p provisoire, e estimé, d définition différente) | — | p | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `note` | Texte | TODO quand Eurostat ne publie pas la série pour le pays | — | TODO : aucune valeur publiée par Eurostat depuis 2018 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Eurostat, jeu sbs_ovw_act (https://ec.europa.eu/eurostat/ap… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

### `eurostat_series`

Séries annuelles Eurostat : une ligne par pays, indicateur et année publiée depuis annee_depuis, pour les taux de croissance. Table réelle, 463 lignes. Grain : `code_pays, indicateur, annee`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `code_pays` | Texte | Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB) | — | BE | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `indicateur` | Texte | Nom de l'indicateur | — | commerce_chaussures_ca_meur | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `annee` | Entier | Année de la valeur | — | 2021 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `valeur` | Décimal | Valeur publiée par Eurostat pour l'année | — | 1356.38 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `unite` | Texte | Unité de la valeur | — | millions d'euros | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `statut_eurostat` | Texte | Statut Eurostat de la valeur (p provisoire, b rupture de série, d définition différente) ; vide si la valeur est définitive | — | p | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `jeu_donnees` | Texte | Code du jeu de données Eurostat | — | sbs_ovw_act | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `filtre` | Texte | Codes des dimensions retenues (dimension=code) | — | nace_r2=G4772;indic_sbs=NETTUR_MEUR | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `date_collecte` | Date | Jour de la collecte | — | 2026-11-12 | API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne |
| `source` | Texte | Origine de la ligne : script et source, ou générateur pour une ligne simulée | — | Eurostat, jeu sbs_ovw_act (https://ec.europa.eu/eurostat/ap… | Pipeline : bronze_to_silver.py |
| `est_simule` | Booléen | Vrai pour une donnée simulée, faux pour une donnée réelle | — | False | Pipeline : bronze_to_silver.py |

## Paramètres des KPI

### `parametres_kpi`

Paramètres numériques des vues KPI (seuils, périodes, scénarios), lus dans config/hypotheses.yaml. Table paramètres, 43 lignes. Grain : `parametre`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `parametre` | Texte | Clé du paramètre dans config/hypotheses.yaml (sections jointes par un point) | — | business_case_allemagne.annee_premiere_ouverture | config/hypotheses.yaml (src/transform/parametres_kpi.py) |
| `valeur` | Décimal | Valeur numérique du paramètre | — | 0 | config/hypotheses.yaml (src/transform/parametres_kpi.py) |

### `parametres_kpi_texte`

Paramètres texte des vues KPI (formats retenus...), lus dans config/hypotheses.yaml. Table paramètres, 10 lignes. Grain : `parametre`.

| Champ | Type | Description | Formule | Exemple | Source |
|---|---|---|---|---|---|
| `parametre` | Texte | Clé du paramètre dans config/hypotheses.yaml (sections jointes par un point) | — | business_case_allemagne.emplacement_immobilier.Centre comme… | config/hypotheses.yaml (src/transform/parametres_kpi.py) |
| `valeur` | Texte | Valeur texte du paramètre | — | 6402.99 | config/hypotheses.yaml (src/transform/parametres_kpi.py) |

## Vues (KPI, business case, scoring)

Calculées par `make kpi` à partir des fichiers `sql/kpi/*.sql` ; leur définition est l'en-tête de chaque fichier.

| Vue | Définition |
|---|---|
| `business_case` | Business case Allemagne (T8) : une ligne par scénario et par format. Payback : mois au bout desquels l'EBITDA cumulé couvre l'investissement (montée en charge comprise, interpolation linéaire dans l'année) ; vide s'il n'est pas atteint dans l'horizon. Point mort : CA HT annuel qui couvre les coûts fixes (loyer et charges, personnel, énergie, amortissement) avec le taux de marge sur coûts variables. Coût d'occupation : (loyer + charges) ÷ CA HT de croisière. |
| `business_case_annuel` | Business case Allemagne (T8), compte de résultat d'un magasin type, année par année, par scénario et par format : montée en charge les 3 premières années, croisière ensuite. EBITDA = marge brute - loyer et charges - personnel - énergie - coûts variables (démarque, frais bancaires, frais de siège, logistique). Résultat = EBITDA - amortissement de l'investissement. Investissement = aménagement x surface + part fixe + marketing de lancement. |
| `business_case_france` | Comparaison France sur le même périmètre de coûts que le business case Allemagne (T8-sensibilite). Magasins France ouverts toute l'année de référence (magasins_france_reference), formats retenus. Mêmes postes que business_case : loyer + charges, personnel, énergie, coûts variables (démarque, frais bancaires, siège, logistique : mêmes % du CA), amortissement de l'investissement sur la même durée. Charges locatives : absentes du jeu France ; estimées avec le ratio charges / loyer de fact_immobilier pour le même type d'emplacement (toutes villes, année de référence) : HYPOTHÈSE de proxy. Payback : investissement ÷ EBITDA d'un magasin à maturité (pas de montée en charge : magasins établis ; investissement France sans marketing de lancement). Ligne INFO : référence, pas un critère. |
| `business_case_hypotheses` | Business case Allemagne (T8), entrées : une ligne par scénario et par format retenu. Magasin type = moyennes du réseau France au même format (règle 7 : CA/m² à format identique) : surface, ETP, CA HT/m² et taux de marge brute recalculés depuis les sommes (règle 6). Taux de marge Allemagne = taux France + écart de marge post-taxe DE - FR (kpi_marge_post_taxe). Loyer + charges : moyenne des 12 villes allemandes pour le type d'emplacement du format. Coûts allemands : fact_couts_exploitation. Hypothèses : config/hypotheses.yaml (parametres_kpi). |
| `city_scoring` | Scoring des villes allemandes (T8), sur 100. Chaque critère est ramené de 0 à 100 entre les villes (0 = la moins favorable, 100 = la plus favorable), puis pondéré (city_scoring.poids). Potentiel : population officielle de la ville (Destatis, réel ; à défaut, population simulée de la ville) x indice de revenu (jeu simulé), noté sur son logarithme (CONVENTION : sinon Berlin, 4 à 10 fois plus peuplée, écrase les autres villes). Loyer : loyer + charges moyens des types d'emplacement des formats retenus (jeu simulé). Densité concurrentielle : réelle (OSM) si disponible, sinon simulée ; plus dense = moins favorable (CONVENTION : on lit la densité comme une pression concurrentielle). Distance au hub : réelle (OSRM) si disponible, sinon simulée. est_prioritaire : rang <= business_case_allemagne.nb_magasins_cible_2029. |
| `densite_concurrentielle` | KPI « Densité concurrentielle » (README, section 2.3), par ville allemande. Magasins de chaussures toutes enseignes (OpenStreetMap, shop=shoes) pour 100 000 habitants. Numérateur : osm_villes (réel). Dénominateur : destatis_population_villes (réel, officiel, même date de référence pour toutes les villes). Les colonnes *_population_osm et *_population_simulee refont le même calcul avec les deux autres populations, pour comparaison ; densite_simulee est la valeur du jeu simulé (recalibré), qui comptait les points de vente de neuf concurrents nommés (autre mesure). |
| `distance_hub` | KPI « Distance aux hubs » (README, section 2.3), par ville allemande. Pour chaque ville : le hub le plus proche par la route et la distance routière réelle (OSRM), comparés au hub le plus proche et à la distance du jeu simulé (fact_logistique, distance à vol d'oiseau majorée de 25 %). duree_conduite_h est un temps de conduite en voiture, pas un délai de livraison. L'emplacement des hubs est une hypothèse du scénario (centre de la commune). |
| `impact_origine` | Levier d'origine : droit de douane UE sur les chaussures selon le pays de fabrication. Produits du code SH impact_origine.code_sh (6402.99) : le jeu simulé leur applique son propre droit (taux_droit_ue_pct de dim_produit). On le remplace par le droit réel, calculé comme le simulé sur la valeur FOB + fret : - droit_tiers_reel : 16,8 % pour tous (taxes_reference, droit de pays tiers TARIC) ; - preference_vietnam : 0 % pour les produits fabriqués au Vietnam (TARIC, préférence tarifaire de l'accord UE-Vietnam), 16,8 % pour les autres. simule (référence) garde le droit du jeu simulé : il doit retrouver le business case tel quel. Coût débarqué = FOB + fret + droit. L'économie de droit, pondérée par les quantités vendues en magasin en France au même format l'année kpi.annee_reference, s'ajoute au taux de marge du business case (business_case_hypotheses), puis le payback est recalculé comme dans business_case (montée en charge, EBITDA cumulé, horizon). Ne modifie ni business_case, ni kpi_summary. |
| `kpi_catalogue_eligible` | KPI « % du catalogue éligible » (README 2.3), par pays. REEL : crocs_catalogue (T3, pages de catégorie de crocs.fr et crocs.de). Références (code modèle + code coloris) du site du pays de référence aussi listées sur le site du pays, ÷ références du site du pays de référence. Une référence listée dans plusieurs catégories compte une fois. SIMULE : fact_eligibilite_assortiment. SKU éligibles ÷ SKU du catalogue France (dim_produit), dénominateur compté et non écrit en dur. Autre mesure : éligibilité réglementaire du jeu simulé, et non présence sur le site. est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays. |
| `kpi_cout_m2` | KPI « Coût moyen au m² » (README 2.3) : loyer + charges en €/m²/an, par ville et par format, année kpi.annee_reference. Comparable seulement à format identique (règle 7). |
| `kpi_cout_occupation` | KPI « Coût d'occupation » (README 2.3) : loyer ÷ CA HT du magasin, recalculé depuis les sommes (règle 6), par format et tous formats, pour le réseau France (benchmark). Charges locatives absentes du jeu France : le taux est un minorant. Allemagne : T8. |
| `kpi_croissance_depenses_chaussures` | Confirmation de la croissance du secteur sur données réelles (T4, Eurostat) : TCAM des dépenses de consommation des ménages en chaussures (COICOP CP032, euros courants) entre kpi.tcam_annee_debut et kpi.tcam_annee_fin. Périmètre différent du KPI « Croissance du secteur » (segment casual moulé & sandales, jeu simulé) : toutes chaussures, en valeur, inflation comprise. Ligne INFO de confirmation : le verdict GO / NO-GO reste porté par la définition du README (2.3). Un pays sans valeur publiée pour l'une des deux années (Royaume-Uni) n'a pas de ligne. |
| `kpi_croissance_secteur` | KPI « Croissance du secteur » (README 2.3) : TCAM de la taille du marché du segment casual moulé & sandales, entre kpi.tcam_annee_debut et kpi.tcam_annee_fin (parametres_kpi). Années observées seulement : les projections (est_projection) sont exclues. |
| `kpi_densite_concurrentielle_pays` | KPI « Densité concurrentielle » (README 2.3), agrégée par pays : points de vente pour 100 000 habitants, recalculée depuis les sommes des villes (règle 6). REEL : vue densite_concurrentielle (OpenStreetMap shop=shoes, population Destatis). SIMULE : dim_zone_chalandise (points de vente de neuf concurrents nommés : autre mesure). est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays. |
| `kpi_distance_hub_pays` | KPI « Distance moyenne aux hubs » (README 2.3), par pays : moyenne, sur les villes du pays, de la distance routière au hub le plus proche. Les zones insulaires sont exclues (T2). REEL : vue distance_hub (OSRM). SIMULE : fact_logistique (vol d'oiseau × 1,25). est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays. |
| `kpi_indice_prix` | KPI « Indice prix relatif » (README 2.3) : moyenne, sur un panier identique de SKU hors promotion, de (prix HT pays ÷ prix HT pays de référence) × 100. REEL : crocs_produits (T3, pages produit de crocs.fr et crocs.de). Une paire = même code modèle et même code coloris, commandable sur les deux sites. Prix hors promotion : le prix barré s'il existe, le prix affiché sinon. TVA : collecte.crocs.tva_pct de config/hypotheses.yaml. Les prix HT sont arrondis au centime avant le rapport, avec le même arrondi (au pair le plus proche, round_even) que src/collect/scrape_crocs.py, pour que les deux calculs donnent le même chiffre : 54,99 ÷ 1,20 = 45,825 tombe pile sur une demie, et l'arrondi classique donnerait 100,83 au lieu de 100,85. Sans arrondi, l'indice vaut 100,84. SIMULE : fact_prix_releves, via kpi_prix_crocs_ht (panier des SKU du catalogue simulé). est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays. |
| `kpi_marge_post_taxe` | KPI « Marge brute post-taxe » (README 2.3) : (prix TTC local ÷ (1 + TVA) − coût débarqué − droits d'import − transport unitaire) ÷ prix HT, recalculée depuis les sommes du panier (règle 6), jamais en moyennant des taux. Droits d'import : nuls dans l'UE (règle 3), appliqués à la valeur FOB + fret hors UE. Transport unitaire : moyenne, sur les villes non insulaires du pays, du coût depuis le hub le plus proche. Le pays de référence n'a pas de ville dans fact_logistique : transport compté 0, ce qui favorise légèrement la référence (limite assumée). Pour chaque pays, la marge de référence est recalculée sur le même panier de SKU. |
| `kpi_part_de_marche` | KPI « Part de marché » (README 2.3) : part en valeur de chaque marque, tous canaux confondus (règle 5 : ce n'est pas le CA de notre réseau), année kpi.annee_reference. Recalculée depuis les CA estimés (règle 6), pas reprise de part_marche_valeur_pct. |
| `kpi_payback` | KPI « Payback » (README 2.3) : investissement d'ouverture ÷ résultat annuel, en mois. Résultat = marge brute − coûts fixes (loyer, personnel, énergie). Agrégé depuis les sommes (règle 6) ; la médiane des magasins est donnée à titre de comparaison. Réseau France (benchmark) ; Allemagne par scénario (pessimiste, central, optimiste) : T8. |
| `kpi_penetration_categories` | KPI « Pénétration des catégories » (README 2.3) : part des consommateurs ayant acheté la catégorie, par pays, année kpi.annee_reference. |
| `kpi_point_mort` | KPI « Point mort par magasin » (README 2.3) : coûts fixes annuels ÷ taux de marge brute, en CA HT annuel. Par format et tous formats : (coûts fixes moyens) ÷ (marge totale ÷ CA total). Réseau France (benchmark) ; Allemagne par scénario : T8. |
| `kpi_prix_crocs_ht` | Base des KPIs « Indice prix relatif » et « Marge brute post-taxe » (pas un KPI en soi). Prix publics Crocs relevés sur les sites officiels (enseigne crocs.*), hors promotion (README 2.5, règle 4), moyennés par SKU et par pays, puis convertis en HT avec la TVA du pays : taux réduit chaussures enfant pour les cibles Enfant et Bébé, standard sinon. TODO T3 : quand la table réelle des prix scrapés existera, la lire ici en priorité. |
| `kpi_summary` | Table de synthèse des KPIs : contrat entre T7, l'IA (T9) et le dashboard (T11). Colonnes figées (docs/equipe/REGLES_COMMUNES.md, « Contrat entre les tâches ») : kpi, axe, pays, valeur, unite, seuil, statut_go, statut_epistemique, origine_donnees. Seuils : parametres_kpi (section go_no_go de config/hypotheses.yaml, README 4.2). statut_go : GO / NO-GO quand un seuil s'applique au pays candidat ; INFO sinon (pays de référence, KPI sans seuil, lignes de comparaison réel / simulé). |
| `kpi_taxes` | KPI « Droits & taxes locales » (README 2.3) : une ligne par pays et par taxe. Réel prioritaire : taxes_reference (T18, saisi depuis les sources officielles, URL par ligne). Le jeu simulé (fact_fiscalite) reste en comparaison pour les taxes que le réel couvre, et seul pour celles qu'il ne couvre pas (droit d'import via la France, éco-contribution). TVA chaussures enfant : sans taux réduit publié, le taux normal s'applique. Impôt sur les sociétés : taux tels que publiés, pas toujours sur le même périmètre (voir note) : l'Allemagne est un taux combiné (IS 15 % + solidarité 5,5 % de l'IS + taxe professionnelle moyenne 14,23 %, variable selon la commune) ; la France est le taux normal hors surtaxes. |
| `magasins_france_reference` | Base des KPIs de rentabilité France (pas un KPI en soi) : un magasin physique par ligne, ouvert toute l'année kpi.annee_reference (ouvert avant, pas fermé pendant), avec son compte de résultat simplifié. Coûts fixes = loyer + personnel (ETP × coût complet) + énergie (m² × coût au m²). Les charges locatives ne sont pas connues pour les magasins France (limite). Le compte de résultat complet (marketing, logistique, démarque, siège...) relève de T8. |
| `sensibilite_payback` | Sensibilité du payback (T8-sensibilite) : scénario et format de sensibilite_payback (pessimiste, centre commercial), en faisant varier deux entrées du magasin type, toutes choses égales par ailleurs : - le nombre d'ETP, de etp_min à l'ETP du magasin type (moyenne France), par pas de etp_pas ; - le CA/m² en part de la France même format, de ca_m2_ratio_min à ca_m2_ratio_max. Même calcul que business_case_annuel / business_case (montée en charge, EBITDA cumulé). Seuil inchangé : go_no_go.payback_pessimiste_max_mois. Lecture : pour un nombre d'ETP donné, GO si CA/m² >= ca_m2_ratio_min_go ; pour un CA/m² donné, GO si ETP <= etp_max_go (vide = jamais GO dans la grille). |
