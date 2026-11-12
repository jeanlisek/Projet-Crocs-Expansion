"""Generate docs/DICTIONNAIRE_CHAMPS.md, the field-by-field dictionary of the gold layer (T12).

Usage (from the repository root, after `make all`):
    python -m src.collect.dictionnaire [--warehouse FILE] [--output FILE]

One section per gold table, in the format of the course: Champ, Type, Description, Formule,
Exemple, Source. What can be read is read, never typed: the tables, columns and types come
from the DuckDB warehouse, the grain from the TableSpec of bronze_to_silver.py, the example
from the data. Descriptions and sources come from docs/DICTIONNAIRE_DONNEES.md, the README
and the comments of the scripts that build each table; a field nobody documented gets TODO.
Each formula is checked on the data before it is written: one that does not hold within
rounding is replaced by a TODO with the gap found. The SQL views (sql/kpi/) are listed at
the end with the header comment of their file.

Run it again when a table is added (T4, T9, T18...): the new table appears with TODO.
"""

import argparse
from pathlib import Path

import duckdb

from src.transform.bronze_to_silver import TABLES
from src.transform.build_gold import DEFAULT_WAREHOUSE

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "DICTIONNAIRE_CHAMPS.md"
SQL_DIR = REPO_ROOT / "sql" / "kpi"
TODO = "TODO"
EXAMPLE_MAX_LENGTH = 60

TYPES = {
    "VARCHAR": "Texte",
    "BIGINT": "Entier",
    "INTEGER": "Entier",
    "DOUBLE": "Décimal",
    "BOOLEAN": "Booléen",
    "DATE": "Date",
}

SIMULATED = "Simulé : generate_data.py (seed 2027)"
PIPELINE = "Pipeline : bronze_to_silver.py"

# --- Tables: section order, description and source -----------------------------------------
# Descriptions: docs/DICTIONNAIRE_DONNEES.md (dimensions, faits) and the docstrings of the
# collection scripts (tables réelles). Calibration sources: section « Sources à citer » of
# docs/DICTIONNAIRE_DONNEES.md.
TABLE_INFO = {
    "dim_pays": ("Pays étudiés : la France (référence) et six pays candidats.", "Eurostat"),
    "dim_temps": ("Calendrier mensuel 2019-2029.", None),
    "dim_produit": (
        "Catalogue France : 147 SKU (30 modèles × coloris), Crocs et HEYDUDE.",
        "Crocs Inc. 10-K 2024-2025, TARIC / UK Global Tariff",
    ),
    "dim_magasin": ("Réseau France : 48 magasins physiques et le canal e-commerce.", None),
    "dim_hub_logistique": (
        "Entrepôts : deux hubs France et le centre de distribution Crocs EMEA (Dordrecht).",
        "Crocs Inc. 10-K 2024-2025",
    ),
    "dim_zone_chalandise": ("Villes cibles des pays candidats (53 villes).", None),
    "dim_concurrent": ("Marques et enseignes du segment casual moulé & sandales.", None),
    "fact_ventes_france": ("Ventes du réseau France, par mois, magasin et produit.", None),
    "fact_marche": (
        "Taille du marché par pays, année et segment (projections 2026-2029 incluses).",
        "Euromonitor / Statista",
    ),
    "fact_parts_de_marche": (
        "Parts de marché en valeur par pays, année et marque (segment casual moulé & sandales).",
        "Euromonitor / Statista",
    ),
    "fact_presence_concurrents": ("Points de vente des concurrents par ville cible.", None),
    "fact_immobilier": (
        "Loyers et vacance commerciale par ville cible, année et type d'emplacement.",
        "Cushman & Wakefield, Main Streets Across the World",
    ),
    "fact_logistique": ("Coûts et délais de transport de chaque hub vers chaque ville.", None),
    "fact_fiscalite": (
        "Fiscalité par pays : TVA, impôt sur les sociétés, droits, éco-contribution.",
        "Commission européenne, Taxes in Europe Database ; TARIC / UK Global Tariff",
    ),
    "fact_couts_exploitation": (
        "Coûts d'exploitation d'un magasin par pays (2026).",
        "Eurostat (salaires minimum)",
    ),
    "fact_prix_releves": (
        "Relevés de prix trimestriels (scraping simulé) : Crocs et équivalents concurrents.",
        None,
    ),
    "fact_penetration_categories": (
        "Part des consommateurs (18-65 ans) ayant acheté la catégorie sur 12 mois.",
        None,
    ),
    "fact_eligibilite_assortiment": (
        "Éligibilité de chaque produit du catalogue France dans chaque pays candidat.",
        None,
    ),
    "fact_tendances_recherche": (
        "Intérêt de recherche mensuel pour « crocs » (type Google Trends, 0-100).",
        "Google Trends",
    ),
    "osm_villes": (
        "Villes allemandes cibles dans OpenStreetMap : limite administrative et magasins.",
        "OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL",
    ),
    "osm_magasins_chaussures": (
        "Magasins de chaussures (shop=shoes) des villes allemandes cibles.",
        "OpenStreetMap via l'API Overpass (src/collect/osm.py), © contributeurs OSM, ODbL",
    ),
    "destatis_population_villes": (
        "Population officielle des villes allemandes cibles.",
        "Destatis, Gemeindeverzeichnis (src/collect/destatis.py)",
    ),
    "osrm_distances": (
        "Distance et durée routières de chaque hub vers chaque ville allemande cible.",
        "OSRM et Nominatim, serveurs publics (src/collect/osrm.py), © contributeurs OSM",
    ),
    "crocs_catalogue": (
        "Catalogue listé sur crocs.fr et crocs.de : une ligne par site, catégorie, modèle "
        "et coloris.",
        "Pages de catégorie de crocs.fr et crocs.de (src/collect/scrape_crocs.py)",
    ),
    "crocs_produits": (
        "Prix relevés sur les pages produit de crocs.fr et crocs.de, par modèle et coloris.",
        "Pages produit de crocs.fr et crocs.de (src/collect/scrape_crocs.py)",
    ),
    "taxes_reference": (
        "Référentiel des taxes par pays : TVA, impôt sur les sociétés, droit de douane UE "
        "sur les chaussures (chapitre 64).",
        "Saisie manuelle (data/manual/), sources officielles par ligne dans source_url : "
        "Commission européenne (TEDB, TARIC), OCDE, textes nationaux",
    ),
    "eurostat_pays": (
        "Indicateurs pays Eurostat : une ligne par pays et indicateur (dernière année publiée).",
        "API de diffusion Eurostat (src/collect/eurostat.py), © Union européenne",
    ),
    "parametres_kpi": (
        "Paramètres numériques des vues KPI (seuils, périodes, scénarios), lus dans "
        "config/hypotheses.yaml.",
        "config/hypotheses.yaml (src/transform/parametres_kpi.py)",
    ),
    "parametres_kpi_texte": (
        "Paramètres texte des vues KPI (formats retenus...), lus dans config/hypotheses.yaml.",
        "config/hypotheses.yaml (src/transform/parametres_kpi.py)",
    ),
}
GROUPS = [
    ("Dimensions", "dim_"),
    ("Faits", "fact_"),
    ("Tables réelles", None),
    ("Paramètres des KPI", "parametres_"),
]

# --- Fields -------------------------------------------------------------------------------
# Same meaning in every table where the name appears.
COMMON = {
    "code_pays": "Code pays ISO 3166-1 alpha-2 (FR, DE, ES, IT, BE, NL, GB)",
    "id_date": "Mois, au format AAAAMM (clé de dim_temps)",
    "id_produit": "Identifiant du produit (clé de dim_produit)",
    "id_magasin": "Identifiant du magasin (clé de dim_magasin)",
    "id_zone": "Identifiant de la ville cible (clé de dim_zone_chalandise)",
    "id_hub": "Identifiant du hub logistique (clé de dim_hub_logistique)",
    "id_concurrent": "Identifiant de la marque ou enseigne (clé de dim_concurrent ; C00 = Crocs)",
    "annee": "Année",
    "latitude": "Latitude (degrés décimaux, WGS 84)",
    "longitude": "Longitude (degrés décimaux, WGS 84)",
    "ville": "Nom de la ville",
    "date_collecte": "Jour de la collecte",
    "source": "Origine de la ligne : script et source, ou générateur pour une ligne simulée",
    "est_simule": "Vrai pour une donnée simulée, faux pour une donnée réelle",
    "annee_ouverture": "Année d'ouverture",
}
FIELDS = {
    "dim_pays": {
        "nom_pays": "Nom du pays",
        "devise": "Devise du pays (code ISO 4217)",
        "taux_change_vs_eur": "Unités de la devise pour 1 €",
        "population_millions": "Population, en millions d'habitants",
        "pib_habitant_spa_ue100": "PIB par habitant en standard de pouvoir d'achat (UE = 100)",
        "taux_chomage_pct": "Taux de chômage (%)",
        "indice_niveau_prix_chaussures_ue100": "Indice de niveau de prix des chaussures "
        "(UE27 = 100)",
        "indice_confiance_conso": "Indicateur de confiance des consommateurs (solde d'opinion)",
        "langue_principale": "Langue principale",
        "membre_ue": "Vrai si le pays est membre de l'Union européenne",
        "union_douaniere_avec_fr": "Vrai si le pays est dans l'union douanière avec la France",
        "est_pays_reference": "Vrai pour la France, pays de référence",
    },
    "dim_temps": {
        "date_debut_mois": "Premier jour du mois",
        "trimestre": "Trimestre (T1 à T4)",
        "mois": "Numéro du mois (1 à 12)",
        "nom_mois": "Nom du mois en français",
        "saison": "Saison (Hiver, Printemps, Été, Automne)",
        "periode_soldes_fr": "Vrai en janvier et juillet, mois des soldes en France",
        "black_friday": "Vrai en novembre, mois du Black Friday",
        "est_historique": "Vrai jusqu'à octobre 2026 (données observées), faux ensuite",
    },
    "dim_produit": {
        "sku": "Référence article (modèle + coloris)",
        "marque": "Marque (Crocs ou HEYDUDE)",
        "categorie": "Catégorie (Sabots, Sandales, Bottes, Jibbitz, Chaussures toile)",
        "sous_categorie": "Sous-catégorie",
        "modele": "Nom du modèle",
        "coloris": "Coloris",
        "cible": "Cible (Adulte, Mixte, Enfant, Bébé)",
        "prix_vente_ttc_fr": "Prix de vente public en France, TTC (€)",
        "prix_vente_ht_fr": "Prix de vente public en France, HT (€)",
        "cout_fob_usd": "Coût d'achat FOB à l'usine ($)",
        "cout_fob_eur": "Coût d'achat FOB converti en euros (€)",
        "cout_fret_unitaire_eur": "Fret maritime et pré/post-acheminement par paire (€)",
        "droits_douane_ue_eur": "Droits de douane UE par paire, sur la valeur CAF (€)",
        "cout_debarque_eur": "Coût débarqué par paire : achat, fret et droits (€)",
        "code_sh": "Code du système harmonisé (nomenclature douanière)",
        "taux_droit_ue_pct": "Taux de droit de douane UE du code SH (%)",
        "taux_droit_uk_pct": "Taux de droit de douane britannique du code SH (%)",
        "pays_origine": "Pays de fabrication",
        "poids_unitaire_kg": "Poids d'une paire (kg)",
        "profil_saisonnier": "Profil de saisonnalité des ventes (plat, ete, hiver, noel...)",
        "produit_sous_licence": "Vrai pour un produit sous licence (Disney, Pokémon...)",
        "annee_lancement": "Année de lancement du produit",
        "statut": "Statut du produit (Actif, Fin de série)",
        "taux_marge_theorique_pct": "Taux de marge théorique sur le prix HT (%)",
    },
    "dim_magasin": {
        "nom_magasin": "Nom du magasin",
        "region": "Région administrative française",
        "type_emplacement": "Format : Centre-ville, Centre commercial, Outlet, Gare / Aéroport, "
        "E-commerce",
        "surface_vente_m2": "Surface de vente (m²)",
        "loyer_annuel_eur": "Loyer annuel (€)",
        "nb_etp": "Effectif en équivalents temps plein",
        "capex_ouverture_eur": "Investissement d'ouverture (€)",
        "id_hub_rattachement": "Hub qui approvisionne le magasin",
        "distance_hub_km": "Distance au hub de rattachement (km)",
        "statut": "Statut du magasin (Ouvert, Fermé)",
        "date_fermeture": "Date de fermeture, vide si le magasin est ouvert",
        "canal": "Canal (Magasin physique, Digital)",
    },
    "dim_hub_logistique": {
        "nom_hub": "Nom du hub",
        "surface_m2": "Surface de l'entrepôt (m²)",
        "type_hub": "Type d'entrepôt",
        "capacite_palettes": "Capacité de stockage (palettes)",
    },
    "dim_zone_chalandise": {
        "population_ville_millions": "Population de la ville (millions d'habitants)",
        "population_zone_chalandise_millions": "Population de la zone de chalandise (millions)",
        "indice_revenu_ue100": "Indice de revenu de la zone (UE = 100)",
        # generate_data.py, section 9: min(100, 40 + 9 × population + N(0, 6)).
        "indice_frequentation_commerce": "Indice de fréquentation commerciale, sans unité, "
        "plafonné à 100 : 40 + 9 × population_ville_millions, plus un aléa d'écart-type 6 "
        "(pas une mesure observée)",
        "nb_centres_commerciaux": "Nombre de centres commerciaux de la zone",
        "part_touristes_pct": "Part des touristes dans la fréquentation (%)",
        "climat_temperature_moy_ete": "Température moyenne en été (°C)",
        "nb_points_vente_concurrents": "Points de vente des concurrents nommés dans la ville",
        "densite_concurrentielle_pour_100k_hab": "Points de vente concurrents pour 100 000 "
        "habitants de la ville",
        "zone_insulaire": "Vrai pour une ville sur une île (Las Palmas, Palma)",
    },
    "dim_concurrent": {
        "nom_concurrent": "Nom de la marque ou de l'enseigne",
        "type_acteur": "Type d'acteur (marque, distributeur, équipementier...)",
        "positionnement_prix": "Positionnement prix (Entrée, Moyen, Premium...)",
        "prix_moyen_eur": "Prix moyen d'une paire (€)",
        "pays_origine": "Pays d'origine de l'acteur",
    },
    "fact_ventes_france": {
        "id_vente": "Identifiant de la ligne de vente",
        "quantite_vendue": "Paires vendues",
        "ca_brut_ttc_eur": "Chiffre d'affaires TTC avant remise (€)",
        "ca_net_ttc_eur": "Chiffre d'affaires TTC après remise (€)",
        "ca_net_ht_eur": "Chiffre d'affaires HT après remise (€)",
        "cout_marchandises_eur": "Coût des marchandises vendues : coût débarqué, +2 % par an "
        "depuis 2023 (€)",
        "remise_eur": "Remises accordées : soldes, Black Friday, outlet, fins de série (€)",
        "marge_brute_eur": "Marge brute (€)",
        "quantite_retournee": "Paires retournées",
    },
    "fact_marche": {
        "segment": "Segment (Casual moulé & sandales, Chaussures total)",
        "taille_marche_meur": "Taille du marché (M€)",
        "taux_croissance_annuel_pct": "Croissance annuelle du marché (%)",
        "est_projection": "Vrai pour une projection (2026-2029), faux pour une observation",
    },
    "fact_parts_de_marche": {
        "part_marche_valeur_pct": "Part de marché en valeur (%)",
        "ca_estime_meur": "Chiffre d'affaires estimé de la marque dans le segment (M€)",
    },
    "fact_presence_concurrents": {
        "nb_points_de_vente": "Points de vente de l'acteur dans la ville",
        "dont_magasins_propres": "Dont magasins en propre",
    },
    "fact_immobilier": {
        "type_emplacement": "Type d'emplacement",
        "loyer_m2_an_eur": "Loyer (€/m²/an)",
        "charges_m2_an_eur": "Charges locatives (€/m²/an)",
        "taux_vacance_pct": "Taux de vacance commerciale (%)",
    },
    "fact_logistique": {
        "distance_route_km": "Distance routière du hub à la ville (km)",
        "delai_livraison_jours": "Délai de livraison (jours)",
        "cout_transport_palette_eur": "Coût de transport d'une palette (€)",
        "cout_transport_unitaire_eur": "Coût de transport par paire (€)",
        "frais_dedouanement_par_envoi_eur": "Frais de dédouanement par envoi (€)",
        "emissions_co2_kg_palette": "Émissions de CO₂ par palette (kg)",
    },
    "fact_fiscalite": {
        "taux_tva_standard_pct": "Taux normal de TVA (%)",
        "taux_tva_chaussures_enfant_pct": "Taux de TVA sur les chaussures enfant (%)",
        "taux_impot_societes_pct": "Taux de l'impôt sur les sociétés (%)",
        "taxe_locale_additionnelle_pct": "Taxe locale additionnelle (%)",
        "eco_contribution_par_paire_eur": "Éco-contribution par paire (€)",
        "droit_import_marchandise_origine_asie_via_fr_pct": "Droit d'import d'un produit "
        "fabriqué en Asie, expédié depuis la France (%)",
        "regime_douanier": "Régime douanier vis-à-vis de la France",
        "regime_rep": "Filière de responsabilité élargie du producteur (REP) applicable",
        "note": "Commentaire sur le régime douanier",
    },
    "fact_couts_exploitation": {
        "salaire_brut_mensuel_vendeur_eur": "Salaire brut mensuel d'un vendeur (€)",
        "taux_charges_patronales_pct": "Charges patronales (% du brut)",
        "salaire_minimum_mensuel_eur": "Salaire minimum mensuel (€)",
        "cout_amenagement_m2_eur": "Coût d'aménagement du magasin (€/m²)",
        "cout_energie_m2_an_eur": "Coût de l'énergie (€/m²/an)",
        "budget_marketing_lancement_eur": "Budget marketing de lancement par magasin (€)",
        "duree_hebdo_travail_h": "Durée hebdomadaire du travail (heures)",
        "cout_complet_annuel_etp_eur": "Coût complet annuel d'un ETP (€)",
        "annee_reference": "Année de référence des coûts",
    },
    "fact_prix_releves": {
        "id_releve": "Identifiant du relevé",
        "enseigne": "Site ou enseigne du relevé",
        "libelle_produit": "Libellé du produit relevé",
        "categorie": "Catégorie du produit",
        "prix_affiche_eur": "Prix affiché (€)",
        "prix_affiche_devise_locale": "Prix affiché dans la devise du pays",
        "en_promotion": "Vrai si le produit est en promotion au moment du relevé",
        "taux_remise_pct": "Remise appliquée (%)",
    },
    "fact_penetration_categories": {
        "categorie": "Catégorie de produit",
        "taux_penetration_pct": "Part des 18-65 ans ayant acheté la catégorie sur 12 mois (%)",
        "panier_moyen_categorie_eur": "Panier moyen dans la catégorie (€)",
        "taille_echantillon": "Taille de l'échantillon de l'enquête",
    },
    "fact_eligibilite_assortiment": {
        "eligible": "Vrai si le produit peut être vendu dans le pays",
        "motif": "Motif d'exclusion, ou « Éligible »",
        "indice_demande_locale": "Indice de demande locale pour le produit",
        "recommandation_assortiment": "Recommandation (Assortiment cœur, optionnel, Exclu)",
        "adaptation_requise": "Adaptation nécessaire (étiquetage, notice...), vide si aucune",
    },
    "fact_tendances_recherche": {
        "mot_cle": "Mot-clé recherché",
        "indice_interet": "Intérêt de recherche (0-100, 100 = pic de la période)",
    },
    "osm_villes": {
        "osm_relation_id": "Identifiant OSM de la limite administrative de la ville",
        "nom_osm": "Nom de la ville dans OSM",
        "niveau_administratif": "Niveau administratif OSM (4 ville-État, 6 ville-arrondissement, "
        "8 commune)",
        "code_communal": "Code officiel de la commune (AGS, 8 chiffres)",
        "population_osm": "Population indiquée dans OSM (comparaison seulement)",
        "annee_population_osm": "Année de la population OSM, quand le tag en donne une seule",
        "tag_annee_population_osm": "Tag OSM d'où vient l'année de la population",
        "source_population_osm": "Source de la population indiquée dans OSM",
        "nb_magasins_chaussures": "Magasins de chaussures (shop=shoes) dans la ville",
        "nb_magasins_avec_enseigne": "Dont magasins avec une enseigne (tag brand)",
    },
    "osm_magasins_chaussures": {
        "osm_type": "Type d'objet OSM (node, way, relation)",
        "osm_id": "Identifiant OSM de l'objet",
        "nom": "Nom du magasin (tag name), vide s'il manque",
        "enseigne": "Enseigne (tag brand), vide s'il manque",
    },
    "destatis_population_villes": {
        "code_communal": "Code officiel de la commune (AGS, 8 chiffres)",
        "cle_regionale": "Clé régionale officielle (ARS, 12 chiffres)",
        "nom_destatis": "Nom de la commune dans le classeur Destatis",
        "population": "Population officielle",
        "date_reference": "Date de référence de la population",
        "source_url": "Page Destatis du classeur",
        "date_consultation": "Jour du téléchargement du classeur",
    },
    "osrm_distances": {
        "commune_hub": "Commune du hub",
        "latitude_hub": "Latitude du hub géocodé (Nominatim)",
        "longitude_hub": "Longitude du hub géocodé (Nominatim)",
        "latitude_ville": "Latitude de la ville",
        "longitude_ville": "Longitude de la ville",
        "distance_route_km": "Distance routière (km)",
        "duree_h": "Durée du trajet en voiture (heures)",
        "ecart_route_hub_m": "Écart entre le hub et le point de route le plus proche (m)",
        "ecart_route_ville_m": "Écart entre la ville et le point de route le plus proche (m)",
    },
    "taxes_reference": {
        "taux_tva_standard_pct": "Taux normal de TVA (%)",
        "taux_tva_reduite_chaussures_enfant_pct": "Taux de TVA réduit sur les chaussures "
        "enfant (%) ; vide s'il n'en existe pas",
        "taux_impot_societes_pct": "Taux de l'impôt sur les sociétés (%) ; ce qu'il inclut est "
        "dans la note",
        "droit_douane_ue_chaussures_ch64_pct": "Droit de douane de pays tiers de l'UE sur les "
        "chaussures, code NC 6402 99 (%) ; vide hors union douanière",
        "source_url": "Pages officielles d'où viennent les valeurs, séparées par un point-virgule",
        "date_consultation": "Jour où les pages ont été lues",
        "note": "Ce que couvre chaque taux et pourquoi une cellule est vide",
    },
    "crocs_catalogue": {
        "site": "Site relevé (FR = crocs.fr, DE = crocs.de)",
        "categorie": "Page de catégorie où la référence est listée (Sabots, Sandales, Chaussures)",
        "code_modele": "Code modèle Crocs (identique sur les deux sites)",
        "nom": "Nom du modèle",
        "code_coloris": "Code coloris Crocs (identique sur les deux sites)",
        "coloris": "Nom du coloris",
    },
    "crocs_produits": {
        "site": "Site relevé (FR = crocs.fr, DE = crocs.de)",
        "code_modele": "Code modèle Crocs",
        "nom": "Nom du modèle",
        "code_coloris": "Code coloris Crocs",
        "coloris": "Nom du coloris",
        "categorie": "Catégorie exclusive du modèle : Sabots, sinon Sandales, sinon Chaussures",
        "silhouette": "Silhouette indiquée par le site (Clog, Sandal, Boot...)",
        "categorie_site": "Catégorie principale du modèle sur le site",
        "genre": "Cible indiquée par le site (unisex, womens, mens, kids)",
        "prix_affiche": "Prix affiché TTC, le plus bas des pointures du coloris (€)",
        "prix_barre": "Prix de référence barré, vide s'il n'y a pas de promotion (€)",
        "devise": "Devise du prix",
        "disponible": "Vrai si au moins une pointure du coloris est commandable",
        "url": "Page du produit, avec le coloris en paramètre (?cid=)",
    },
    "eurostat_pays": {
        "indicateur": "Nom de l'indicateur",
        "libelle_eurostat": "Libellés Eurostat des codes du filtre",
        "jeu_donnees": "Code du jeu de données Eurostat",
        "filtre": "Codes des dimensions retenues (dimension=code)",
        "annee": "Dernière année publiée, vide si aucune",
        "valeur": "Valeur publiée, vide si Eurostat n'en publie pas",
        "unite": "Unité de la valeur",
        "statut_eurostat": "Statut Eurostat (p provisoire, e estimé, d définition différente)",
        "note": "TODO quand Eurostat ne publie pas la série pour le pays",
    },
    "parametres_kpi": {
        "parametre": "Clé du paramètre dans config/hypotheses.yaml (sections jointes par un point)",
        "valeur": "Valeur numérique du paramètre",
    },
    "parametres_kpi_texte": {
        "parametre": "Clé du paramètre dans config/hypotheses.yaml (sections jointes par un point)",
        "valeur": "Valeur texte du paramètre",
    },
}

# --- Formulas -----------------------------------------------------------------------------
# table -> column -> (formula as written in the dictionary, SQL that returns the largest gap
# on the data, tolerance). The formulas come from generate_data.py and the README (2.5).
SALES_SEGMENT = "Casual moulé & sandales"
FORMULAS = {
    "dim_produit": {
        "prix_vente_ht_fr": (
            "prix_vente_ttc_fr ÷ 1,20",
            "max(abs(prix_vente_ht_fr - prix_vente_ttc_fr / 1.20))",
            0.011,
        ),
        "cout_fob_eur": (
            "cout_fob_usd × 0,92 (taux USD → EUR du générateur)",
            "max(abs(cout_fob_eur - cout_fob_usd * 0.92))",
            0.011,
        ),
        "droits_douane_ue_eur": (
            "(cout_fob_eur + cout_fret_unitaire_eur) × taux_droit_ue_pct ÷ 100",
            "max(abs(droits_douane_ue_eur - (cout_fob_eur + cout_fret_unitaire_eur)"
            " * taux_droit_ue_pct / 100))",
            0.011,
        ),
        "cout_debarque_eur": (
            "cout_fob_eur + cout_fret_unitaire_eur + droits_douane_ue_eur",
            "max(abs(cout_debarque_eur - (cout_fob_eur + cout_fret_unitaire_eur"
            " + droits_douane_ue_eur)))",
            0.011,
        ),
        "taux_marge_theorique_pct": (
            "(prix_vente_ht_fr − cout_debarque_eur) ÷ prix_vente_ht_fr × 100",
            "max(abs(taux_marge_theorique_pct - (prix_vente_ht_fr - cout_debarque_eur)"
            " / prix_vente_ht_fr * 100))",
            0.06,
        ),
    },
    "fact_ventes_france": {
        "ca_net_ht_eur": (
            "ca_net_ttc_eur ÷ 1,20",
            "max(abs(ca_net_ht_eur - ca_net_ttc_eur / 1.20))",
            0.011,
        ),
        "remise_eur": (
            "ca_brut_ttc_eur − ca_net_ttc_eur",
            "max(abs(remise_eur - (ca_brut_ttc_eur - ca_net_ttc_eur)))",
            0.011,
        ),
        "marge_brute_eur": (
            "ca_net_ht_eur − cout_marchandises_eur",
            "max(abs(marge_brute_eur - (ca_net_ht_eur - cout_marchandises_eur)))",
            0.011,
        ),
    },
    "dim_zone_chalandise": {
        "densite_concurrentielle_pour_100k_hab": (
            "nb_points_vente_concurrents ÷ (population_ville_millions × 10)",
            "max(abs(densite_concurrentielle_pour_100k_hab"
            " - nb_points_vente_concurrents / (population_ville_millions * 10)))",
            0.006,
        ),
    },
    "fact_couts_exploitation": {
        "cout_complet_annuel_etp_eur": (
            "salaire_brut_mensuel_vendeur_eur × 12,5 × (1 + taux_charges_patronales_pct ÷ 100)",
            "max(abs(cout_complet_annuel_etp_eur - salaire_brut_mensuel_vendeur_eur * 12.5"
            " * (1 + taux_charges_patronales_pct / 100)))",
            0.51,
        ),
    },
    "fact_logistique": {
        "cout_transport_unitaire_eur": (
            "cout_transport_palette_eur ÷ 180 (paires par palette)",
            "max(abs(cout_transport_unitaire_eur - cout_transport_palette_eur / 180))",
            0.0006,
        ),
    },
    "fact_parts_de_marche": {
        "ca_estime_meur": (
            f"part_marche_valeur_pct ÷ 100 × fact_marche.taille_marche_meur (segment "
            f"{SALES_SEGMENT}, même pays et même année)",
            "max(abs(p.ca_estime_meur - p.part_marche_valeur_pct / 100 * m.taille_marche_meur))"
            " FROM fact_parts_de_marche p JOIN fact_marche m ON m.code_pays = p.code_pays"
            f" AND m.annee = p.annee AND m.segment = '{SALES_SEGMENT}'",
            # The CA is computed on the unrounded share, then rounded to 0.1 M€: the gap adds
            # up to 0.05 M€ for that rounding and up to 0.005 point of share × ~1 300 M€.
            0.12,
        ),
    },
    "fact_prix_releves": {
        "prix_affiche_devise_locale": (
            "prix_affiche_eur × 0,85 au Royaume-Uni (GBP), prix_affiche_eur ailleurs",
            "max(abs(prix_affiche_devise_locale - prix_affiche_eur"
            " * CASE WHEN code_pays = 'GB' THEN 0.85 ELSE 1 END))",
            0.011,
        ),
    },
    "osm_villes": {
        "nb_magasins_chaussures": (
            "nombre de lignes de osm_magasins_chaussures de la ville",
            "max(abs(v.nb_magasins_chaussures - coalesce(n.nb, 0))) FROM osm_villes v"
            " LEFT JOIN (SELECT id_zone, count(*) AS nb FROM osm_magasins_chaussures"
            " GROUP BY id_zone) n ON n.id_zone = v.id_zone",
            0,
        ),
    },
}


def column_source(table: str, column: str) -> str:
    if column in ("source", "est_simule"):
        return PIPELINE
    spec = TABLES.get(table)
    origin = TABLE_INFO.get(table, (None, None))[1]
    if spec is not None and spec.simulated:
        return f"{SIMULATED}, calibré sur {origin}" if origin else SIMULATED
    return origin or TODO


def formula(con, table: str, column: str) -> str:
    """The formula once checked on the data, a TODO with the gap otherwise, or nothing."""
    if column not in FORMULAS.get(table, {}):
        return ""
    text, gap_sql, tolerance = FORMULAS[table][column]
    query = f"SELECT {gap_sql}" if " FROM " in gap_sql else f'SELECT {gap_sql} FROM "{table}"'
    gap = con.execute(query).fetchall()[0][0]
    if gap is not None and gap <= tolerance:
        return text
    return f"{TODO} : {text} ne tient pas sur les données (écart max {gap})"


def example(con, table: str, column: str) -> str:
    spec = TABLES.get(table)
    order = ", ".join(f'"{key}"' for key in spec.primary_key) if spec else "1"
    rows = con.execute(
        f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL ORDER BY {order} LIMIT 1'
    ).fetchall()
    if not rows:
        return "(toujours vide)"
    value = rows[0][0]
    if isinstance(value, float):
        value = f"{value:g}"
    text = str(value)
    if len(text) > EXAMPLE_MAX_LENGTH:
        text = text[: EXAMPLE_MAX_LENGTH - 1] + "…"
    return text


def cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def table_section(con, table: str) -> list[str]:
    description, _ = TABLE_INFO.get(table, (TODO, None))
    spec = TABLES.get(table)
    count = con.execute(f'SELECT count(*) FROM "{table}"').fetchall()[0][0]
    if spec is None:
        nature = "paramètres"
    else:
        nature = "simulée" if spec.simulated else "réelle"
    grain = ", ".join(spec.primary_key) if spec else "parametre"
    lines = [
        f"### `{table}`",
        "",
        f"{description} Table {nature}, {count:,} lignes. Grain : `{grain}`.".replace(
            f"{count:,}", f"{count:,}".replace(",", " ")
        ),
        "",
        "| Champ | Type | Description | Formule | Exemple | Source |",
        "|---|---|---|---|---|---|",
    ]
    columns = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns"
        " WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    for column, data_type in columns:
        text = FIELDS.get(table, {}).get(column) or COMMON.get(column) or TODO
        values = (
            f"`{column}`",
            TYPES.get(data_type, data_type),
            text,
            formula(con, table, column) or "—",
            example(con, table, column),
            column_source(table, column),
        )
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    return lines + [""]


def view_comment(view: str) -> str:
    """The header comment of the view's SQL file, or TODO."""
    path = SQL_DIR / f"{view}.sql"
    if not path.exists():
        return TODO
    comment = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("--"):
            break
        comment.append(line.lstrip("-").strip())
    return " ".join(comment) or TODO


def group_of(table: str) -> str:
    for title, prefix in GROUPS:
        if prefix and table.startswith(prefix):
            return title
    return "Tables réelles"


def build(warehouse: Path) -> str:
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        objects = con.execute(
            "SELECT table_name, table_type FROM information_schema.tables ORDER BY table_name"
        ).fetchall()
        tables = [name for name, kind in objects if kind == "BASE TABLE"]
        views = [name for name, kind in objects if kind == "VIEW"]
        undocumented = [table for table in tables if table not in TABLE_INFO]
        lines = [
            "# Dictionnaire des champs",
            "",
            "> Généré par `python -m src.collect.dictionnaire` à partir de l'entrepôt "
            "`data/gold/warehouse.duckdb` : ne pas modifier à la main, relancer le script. "
            "Types et exemples lus dans les données ; descriptions et sources tirées de "
            "`docs/DICTIONNAIRE_DONNEES.md`, du README et des scripts ; chaque formule est "
            "vérifiée sur les données. `TODO` = information manquante.",
            "",
            f"{len(tables)} tables et {len(views)} vues. "
            "Une table simulée porte `est_simule` = vrai sur toutes ses lignes ; "
            "« Source » donne alors la source publique sur laquelle la simulation est calibrée.",
            "",
        ]
        for title, _ in GROUPS:
            members = [table for table in tables if group_of(table) == title]
            ordered = [t for t in TABLE_INFO if t in members] + sorted(
                t for t in members if t not in TABLE_INFO
            )
            if not ordered:
                continue
            lines += [f"## {title}", ""]
            for table in ordered:
                lines += table_section(con, table)
        lines += [
            "## Vues (KPI, business case, scoring)",
            "",
            "Calculées par `make kpi` à partir des fichiers `sql/kpi/*.sql` ; leur définition "
            "est l'en-tête de chaque fichier.",
            "",
            "| Vue | Définition |",
            "|---|---|",
        ]
        lines += [f"| `{view}` | {cell(view_comment(view))} |" for view in views]
        if undocumented:
            lines += ["", f"{TODO} : tables à documenter : {', '.join(undocumented)}."]
        return "\n".join(lines) + "\n"
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    text = build(args.warehouse)
    args.output.write_text(text, encoding="utf-8")
    todos = text.count(TODO)
    print(f"{args.output} écrit : {text.count('### ')} tables, {todos} TODO")


if __name__ == "__main__":
    main()
