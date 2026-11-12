"""Bronze -> silver: load, type, check and write every table as Parquet.

Usage: python src/transform/bronze_to_silver.py [--bronze DIR] [--manual DIR] [--silver DIR]

Bronze is never modified: each CSV file is read as raw text, cast to the schema declared
in its TableSpec, checked (duplicates, nulls, IQR outliers), labelled (est_simule, source)
and written to the silver layer. Tables typed in by hand from official sources live in
data/manual/ (versioned) and go through exactly the same steps.

The checks only report, in data/silver/rapport_controles.csv. Changing the data is a
deliberate decision: it is registered in CORRECTIONS and logged in
docs/JOURNAL_NETTOYAGE.md (anomaly, number of rows, decision, business justification).
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
DEFAULT_BRONZE_DIR = REPO_ROOT / "data" / "bronze"
DEFAULT_MANUAL_DIR = REPO_ROOT / "data" / "manual"
DEFAULT_SILVER_DIR = REPO_ROOT / "data" / "silver"
REPORT_FILE = "rapport_controles.csv"

# Where the CSV file of a table lives: generated or collected files in data/bronze/
# (not versioned), values typed in by hand from official sources in data/manual/ (versioned).
BRONZE, MANUAL = "bronze", "manual"

# Column types of the silver layer.
STR, INT, FLOAT, BOOL, DATE = "string", "integer", "float", "boolean", "date"
BOOLEAN_VALUES = {"True": True, "False": False}
DATE_FORMAT = "%Y-%m-%d"

# Labels carried by every silver table: simulated data is always flagged as such.
SIMULATED_COLUMN = "est_simule"
SOURCE_COLUMN = "source"
SIMULATED_SOURCE = "Générateur Python src/simulate/generate_data.py (seed {seed})"

# Check report: one row per finding.
REPORT_COLUMNS = ["table", "controle", "colonne", "nb_lignes", "detail", "statut"]
CHECK_DUPLICATES = "doublons"
CHECK_NULLS = "valeurs_nulles"
CHECK_OUTLIERS = "valeurs_aberrantes_iqr"
STATUS_EXPECTED = "attendu"
STATUS_TO_REVIEW = "a_examiner"
LOWER_QUARTILE, UPPER_QUARTILE = 0.25, 0.75

# A correction runs either on the raw text (format fixes that make the cast possible)
# or on the typed table (deduplication, outliers...).
STAGE_RAW, STAGE_TYPED = "raw", "typed"


@dataclass(frozen=True)
class TableSpec:
    """Schema and checks of one input table (a CSV file of data/bronze/ or data/manual/)."""

    # Column name -> silver type. Must match the CSV file exactly.
    columns: dict[str, str]
    # Grain of the table: no two rows may share these values.
    primary_key: tuple[str, ...]
    # Columns where a null is a documented business fact, not an anomaly.
    expected_nulls: tuple[str, ...] = ()
    # Numeric column -> columns to group by before computing the quartiles, so that a value
    # is only compared with comparable ones (same store format, same product...).
    outlier_checks: dict[str, tuple[str, ...]] = field(default_factory=dict)
    simulated: bool = True
    # Written to the `source` column when the file has none. Simulated tables default to
    # SIMULATED_SOURCE; a real table must say where its values come from (URL of the dated
    # bronze file, or how the manual file is sourced).
    source: str | None = None
    # BRONZE or MANUAL: the directory that holds <table name>.csv.
    directory: str = BRONZE


@dataclass(frozen=True)
class Correction:
    """One change applied to the data, logged in docs/JOURNAL_NETTOYAGE.md."""

    journal_id: str  # identifier of the journal entry, e.g. "N-001"
    table: str
    stage: str  # STAGE_RAW or STAGE_TYPED
    apply: Callable[[pd.DataFrame], pd.DataFrame]


# --------------------------------------------------------------------------------------
# Simulated tables: the 19 CSV files written by src/simulate/generate_data.py
# --------------------------------------------------------------------------------------
SIMULATED_TABLES: dict[str, TableSpec] = {
    "dim_pays": TableSpec(
        columns={
            "code_pays": STR,
            "nom_pays": STR,
            "devise": STR,
            "taux_change_vs_eur": FLOAT,
            "population_millions": FLOAT,
            "pib_habitant_spa_ue100": INT,
            "taux_chomage_pct": FLOAT,
            "indice_niveau_prix_chaussures_ue100": INT,
            "indice_confiance_conso": INT,
            "langue_principale": STR,
            "membre_ue": BOOL,
            "union_douaniere_avec_fr": BOOL,
            "est_pays_reference": BOOL,
        },
        primary_key=("code_pays",),
    ),
    "dim_temps": TableSpec(
        columns={
            "id_date": INT,
            "date_debut_mois": DATE,
            "annee": INT,
            "trimestre": STR,
            "mois": INT,
            "nom_mois": STR,
            "saison": STR,
            "periode_soldes_fr": BOOL,
            "black_friday": BOOL,
            "est_historique": BOOL,
        },
        primary_key=("id_date",),
    ),
    "dim_produit": TableSpec(
        columns={
            "id_produit": STR,
            "sku": STR,
            "marque": STR,
            "categorie": STR,
            "sous_categorie": STR,
            "modele": STR,
            "coloris": STR,
            "cible": STR,
            "prix_vente_ttc_fr": FLOAT,
            "prix_vente_ht_fr": FLOAT,
            "cout_fob_usd": FLOAT,
            "cout_fob_eur": FLOAT,
            "cout_fret_unitaire_eur": FLOAT,
            "droits_douane_ue_eur": FLOAT,
            "cout_debarque_eur": FLOAT,
            # Customs code, not a number: a numeric read turns "6402.20" into 6402.2.
            "code_sh": STR,
            "taux_droit_ue_pct": FLOAT,
            "taux_droit_uk_pct": FLOAT,
            "pays_origine": STR,
            "poids_unitaire_kg": FLOAT,
            "profil_saisonnier": STR,
            "produit_sous_licence": BOOL,
            "annee_lancement": INT,
            "statut": STR,
            "taux_marge_theorique_pct": FLOAT,
        },
        primary_key=("id_produit",),
        outlier_checks={
            "prix_vente_ttc_fr": ("categorie",),
            "taux_marge_theorique_pct": ("categorie",),
        },
    ),
    "dim_magasin": TableSpec(
        columns={
            "id_magasin": STR,
            "nom_magasin": STR,
            "ville": STR,
            "region": STR,
            "code_pays": STR,
            "latitude": FLOAT,
            "longitude": FLOAT,
            "type_emplacement": STR,
            "surface_vente_m2": INT,
            "annee_ouverture": INT,
            "loyer_annuel_eur": INT,
            "nb_etp": FLOAT,
            "capex_ouverture_eur": INT,
            "id_hub_rattachement": STR,
            "distance_hub_km": FLOAT,
            "statut": STR,
            "date_fermeture": DATE,
            "canal": STR,
        },
        primary_key=("id_magasin",),
        # T2 : vide pour les magasins ouverts (seuls quelques magasins ont fermé)
        expected_nulls=("date_fermeture",),
        outlier_checks={
            "surface_vente_m2": ("type_emplacement",),
            "loyer_annuel_eur": ("type_emplacement",),
        },
    ),
    "dim_hub_logistique": TableSpec(
        columns={
            "id_hub": STR,
            "nom_hub": STR,
            "ville": STR,
            "code_pays": STR,
            "latitude": FLOAT,
            "longitude": FLOAT,
            "surface_m2": INT,
            "type_hub": STR,
            "annee_ouverture": INT,
            "capacite_palettes": INT,
        },
        primary_key=("id_hub",),
    ),
    "dim_zone_chalandise": TableSpec(
        columns={
            "id_zone": STR,
            "code_pays": STR,
            "ville": STR,
            "latitude": FLOAT,
            "longitude": FLOAT,
            "population_ville_millions": FLOAT,
            "population_zone_chalandise_millions": FLOAT,
            "indice_revenu_ue100": INT,
            "indice_frequentation_commerce": FLOAT,
            "nb_centres_commerciaux": INT,
            "part_touristes_pct": FLOAT,
            "climat_temperature_moy_ete": FLOAT,
            "nb_points_vente_concurrents": INT,
            "densite_concurrentielle_pour_100k_hab": FLOAT,
            "zone_insulaire": BOOL,
        },
        primary_key=("id_zone",),
    ),
    "dim_concurrent": TableSpec(
        columns={
            "id_concurrent": STR,
            "nom_concurrent": STR,
            "type_acteur": STR,
            "positionnement_prix": STR,
            "prix_moyen_eur": INT,
            "pays_origine": STR,
        },
        primary_key=("id_concurrent",),
    ),
    "fact_ventes_france": TableSpec(
        columns={
            "id_vente": INT,
            "id_date": INT,
            "id_magasin": STR,
            "id_produit": STR,
            "quantite_vendue": INT,
            "ca_brut_ttc_eur": FLOAT,
            "ca_net_ttc_eur": FLOAT,
            "ca_net_ht_eur": FLOAT,
            "cout_marchandises_eur": FLOAT,
            "remise_eur": FLOAT,
            "marge_brute_eur": FLOAT,
            "quantite_retournee": INT,
        },
        primary_key=("id_date", "id_magasin", "id_produit"),
        # A product in a store is compared with its own monthly history.
        outlier_checks={"quantite_vendue": ("id_magasin", "id_produit")},
    ),
    "fact_marche": TableSpec(
        columns={
            "code_pays": STR,
            "annee": INT,
            "segment": STR,
            "taille_marche_meur": FLOAT,
            "taux_croissance_annuel_pct": FLOAT,
            "est_projection": BOOL,
            "source": STR,
        },
        primary_key=("code_pays", "annee", "segment"),
        # First year of each series: there is no previous year to compute a growth rate.
        expected_nulls=("taux_croissance_annuel_pct",),
    ),
    "fact_parts_de_marche": TableSpec(
        columns={
            "code_pays": STR,
            "annee": INT,
            "id_concurrent": STR,
            "part_marche_valeur_pct": FLOAT,
            "ca_estime_meur": FLOAT,
        },
        primary_key=("code_pays", "annee", "id_concurrent"),
    ),
    "fact_presence_concurrents": TableSpec(
        columns={
            "id_zone": STR,
            "id_concurrent": STR,
            "nb_points_de_vente": INT,
            "dont_magasins_propres": INT,
        },
        primary_key=("id_zone", "id_concurrent"),
    ),
    "fact_immobilier": TableSpec(
        columns={
            "id_zone": STR,
            "annee": INT,
            "type_emplacement": STR,
            "loyer_m2_an_eur": INT,
            "charges_m2_an_eur": INT,
            "taux_vacance_pct": FLOAT,
        },
        primary_key=("id_zone", "annee", "type_emplacement"),
        outlier_checks={"loyer_m2_an_eur": ("type_emplacement",)},
    ),
    "fact_logistique": TableSpec(
        columns={
            "id_hub": STR,
            "id_zone": STR,
            "distance_route_km": INT,
            "delai_livraison_jours": FLOAT,
            "cout_transport_palette_eur": FLOAT,
            "cout_transport_unitaire_eur": FLOAT,
            "frais_dedouanement_par_envoi_eur": FLOAT,
            "emissions_co2_kg_palette": FLOAT,
        },
        primary_key=("id_hub", "id_zone"),
        outlier_checks={"cout_transport_palette_eur": ()},
    ),
    "fact_fiscalite": TableSpec(
        columns={
            "code_pays": STR,
            "taux_tva_standard_pct": FLOAT,
            "taux_tva_chaussures_enfant_pct": FLOAT,
            "taux_impot_societes_pct": FLOAT,
            "taxe_locale_additionnelle_pct": FLOAT,
            "eco_contribution_par_paire_eur": FLOAT,
            "droit_import_marchandise_origine_asie_via_fr_pct": FLOAT,
            "regime_douanier": STR,
            "regime_rep": STR,
            "note": STR,
        },
        primary_key=("code_pays",),
    ),
    "fact_couts_exploitation": TableSpec(
        columns={
            "code_pays": STR,
            "salaire_brut_mensuel_vendeur_eur": INT,
            "taux_charges_patronales_pct": FLOAT,
            "salaire_minimum_mensuel_eur": FLOAT,
            "cout_amenagement_m2_eur": INT,
            "cout_energie_m2_an_eur": INT,
            "budget_marketing_lancement_eur": INT,
            "duree_hebdo_travail_h": INT,
            "cout_complet_annuel_etp_eur": FLOAT,
            "annee_reference": INT,
        },
        primary_key=("code_pays", "annee_reference"),
        # No statutory minimum wage in Italy (docs/AUDIT_JEU_DE_DONNEES_V1.md).
        expected_nulls=("salaire_minimum_mensuel_eur",),
    ),
    "fact_prix_releves": TableSpec(
        columns={
            "id_releve": INT,
            "id_date": INT,
            "code_pays": STR,
            "enseigne": STR,
            "id_concurrent": STR,
            "id_produit": STR,
            "libelle_produit": STR,
            "categorie": STR,
            "prix_affiche_eur": FLOAT,
            "prix_affiche_devise_locale": FLOAT,
            "en_promotion": BOOL,
            "taux_remise_pct": FLOAT,
        },
        primary_key=("id_releve",),
        # Competitor products are not in the Crocs catalogue (docs/AUDIT_JEU_DE_DONNEES_V1.md).
        expected_nulls=("id_produit",),
        outlier_checks={"prix_affiche_eur": ("libelle_produit",)},
    ),
    "fact_penetration_categories": TableSpec(
        columns={
            "code_pays": STR,
            "annee": INT,
            "categorie": STR,
            "taux_penetration_pct": FLOAT,
            "panier_moyen_categorie_eur": FLOAT,
            "taille_echantillon": INT,
            "source": STR,
        },
        primary_key=("code_pays", "annee", "categorie"),
    ),
    "fact_eligibilite_assortiment": TableSpec(
        columns={
            "code_pays": STR,
            "id_produit": STR,
            "eligible": BOOL,
            "motif": STR,
            "indice_demande_locale": FLOAT,
            "recommandation_assortiment": STR,
            "adaptation_requise": STR,
        },
        primary_key=("code_pays", "id_produit"),
        # Left empty by the generator for the products excluded from the assortment.
        expected_nulls=("adaptation_requise",),
    ),
    "fact_tendances_recherche": TableSpec(
        columns={
            "code_pays": STR,
            "id_date": INT,
            "mot_cle": STR,
            "indice_interet": INT,
        },
        primary_key=("code_pays", "id_date", "mot_cle"),
    ),
}

# --------------------------------------------------------------------------------------
# Real tables: collected by src/collect/ into data/bronze/, or typed in by hand in data/manual/
# --------------------------------------------------------------------------------------
# File names and columns are only known once a collector has run: they are not guessed
# here. A real table is optional: while its file does not exist, it is skipped by the
# pipeline and the simulated tables are used alone. To plug a real table in, add a TableSpec with
# simulated=False and `source` set to the URL of the dated bronze file (or a `source`
# column in the file itself), then log its anomalies in docs/JOURNAL_NETTOYAGE.md.
# A table typed in by hand is declared the same way, with directory=MANUAL: its file is
# then read from data/manual/ instead of data/bronze/.
# A CSV file without a TableSpec is listed as ignored at the end of the run.
REAL_TABLES: dict[str, TableSpec] = {
    # T16: OpenStreetMap, collected by src/collect/osm.py (`make collect`). Both files carry
    # their own `source` column. Data © OpenStreetMap contributors, ODbL.
    "osm_villes": TableSpec(
        columns={
            "id_zone": STR,
            "ville": STR,
            "osm_relation_id": INT,
            "nom_osm": STR,
            "niveau_administratif": INT,
            "code_communal": STR,
            "population_osm": INT,
            "annee_population_osm": INT,
            "tag_annee_population_osm": STR,
            "source_population_osm": STR,
            "nb_magasins_chaussures": INT,
            "nb_magasins_avec_enseigne": INT,
            "date_collecte": DATE,
            "source": STR,
        },
        primary_key=("id_zone",),
        # The population tags are optional in OSM and missing for most cities: the density
        # uses the official Destatis population, the OSM figure is kept for comparison.
        expected_nulls=(
            "population_osm",
            "annee_population_osm",
            "tag_annee_population_osm",
            "source_population_osm",
        ),
        simulated=False,
    ),
    "osm_magasins_chaussures": TableSpec(
        columns={
            "id_zone": STR,
            "osm_type": STR,
            "osm_id": INT,
            "nom": STR,
            "enseigne": STR,
            "latitude": FLOAT,
            "longitude": FLOAT,
            "date_collecte": DATE,
            "source": STR,
        },
        primary_key=("osm_type", "osm_id"),
        # `name` and `brand` are optional OSM tags: a shop without them is still a shop.
        expected_nulls=("nom", "enseigne"),
        simulated=False,
    ),
    # T16: official population of the target cities, extracted by src/collect/destatis.py
    # from the Destatis workbook saved in data/bronze/.
    "destatis_population_villes": TableSpec(
        columns={
            "id_zone": STR,
            "ville": STR,
            "code_communal": STR,
            "cle_regionale": STR,
            "nom_destatis": STR,
            "population": INT,
            "date_reference": DATE,
            "source_url": STR,
            "date_consultation": DATE,
            "source": STR,
        },
        primary_key=("id_zone",),
        simulated=False,
    ),
    # T17: road distance and driving time from each hub to each target city, collected by
    # src/collect/osrm.py (OSRM public server; Nominatim for the towns of the hubs).
    "osrm_distances": TableSpec(
        columns={
            "id_hub": STR,
            "id_zone": STR,
            "commune_hub": STR,
            "ville": STR,
            "latitude_hub": FLOAT,
            "longitude_hub": FLOAT,
            "latitude_ville": FLOAT,
            "longitude_ville": FLOAT,
            "distance_route_km": FLOAT,
            "duree_h": FLOAT,
            "ecart_route_hub_m": INT,
            "ecart_route_ville_m": INT,
            "date_collecte": DATE,
            "source": STR,
        },
        primary_key=("id_hub", "id_zone"),
        simulated=False,
    ),
    # T3: public pages of crocs.fr and crocs.de, collected by src/collect/scrape_crocs.py
    # (`make collect`). Several dated snapshots: the dated raw files of data/bronze/ keep every
    # reading; these two tables hold the latest one (date in `date_collecte`).
    "crocs_catalogue": TableSpec(
        columns={
            "site": STR,
            "categorie": STR,
            "code_modele": STR,
            "nom": STR,
            "code_coloris": STR,
            "coloris": STR,
            "date_collecte": DATE,
            "source": STR,
        },
        # A model can be listed on several category pages: the category is part of the key.
        primary_key=("site", "categorie", "code_modele", "code_coloris"),
        simulated=False,
    ),
    "crocs_produits": TableSpec(
        columns={
            "site": STR,
            "code_modele": STR,
            "nom": STR,
            "code_coloris": STR,
            "coloris": STR,
            "categorie": STR,
            "silhouette": STR,
            "categorie_site": STR,
            "genre": STR,
            "prix_affiche": FLOAT,
            "prix_barre": FLOAT,
            "devise": STR,
            "disponible": BOOL,
            "url": STR,
            "date_collecte": DATE,
            "source": STR,
        },
        primary_key=("site", "code_modele", "code_coloris"),
        # No crossed-out price when the colour is not on promotion.
        expected_nulls=("prix_barre",),
        outlier_checks={"prix_affiche": ("categorie",)},
        simulated=False,
    ),
    # T4: Eurostat dissemination API, collected by src/collect/eurostat.py (`make collect`).
    # One row per country and indicator (latest year published); the dataset code and the
    # filter of each row say exactly which Eurostat series it comes from.
    "eurostat_pays": TableSpec(
        columns={
            "code_pays": STR,
            "indicateur": STR,
            "libelle_eurostat": STR,
            "jeu_donnees": STR,
            "filtre": STR,
            "annee": INT,
            "valeur": FLOAT,
            "unite": STR,
            "statut_eurostat": STR,
            "note": STR,
            "date_collecte": DATE,
            "source": STR,
        },
        primary_key=("code_pays", "indicateur"),
        # No value when Eurostat publishes none for a country (TODO in `note`); no flag when
        # the value is final; no note when there is a value.
        expected_nulls=("annee", "valeur", "statut_eurostat", "note"),
        simulated=False,
    ),
    # T4, same raw answers: every year published since `annee_depuis`, for growth rates (the
    # sector growth KPI is a CAGR). A year Eurostat does not publish has no row.
    "eurostat_series": TableSpec(
        columns={
            "code_pays": STR,
            "indicateur": STR,
            "annee": INT,
            "valeur": FLOAT,
            "unite": STR,
            "statut_eurostat": STR,
            "jeu_donnees": STR,
            "filtre": STR,
            "date_collecte": DATE,
            "source": STR,
        },
        primary_key=("code_pays", "indicateur", "annee"),
        # No flag when the value is final.
        expected_nulls=("statut_eurostat",),
        simulated=False,
    ),
    # T18: tax reference typed in by hand from the official sources (Commission européenne
    # TEDB and TARIC, OECD, national texts), one row per country. The URLs of each row are in
    # its `source_url` column, separated by a semicolon; `note` says what each rate covers.
    "taxes_reference": TableSpec(
        columns={
            "code_pays": STR,
            "taux_tva_standard_pct": FLOAT,
            "taux_tva_reduite_chaussures_enfant_pct": FLOAT,
            "taux_impot_societes_pct": FLOAT,
            "droit_douane_ue_chaussures_ch64_pct": FLOAT,
            "source_url": STR,
            "date_consultation": DATE,
            "note": STR,
        },
        primary_key=("code_pays",),
        # No reduced VAT rate on children's footwear in most countries, and no EU customs duty
        # for a country outside the EU customs union (GB): the cell is empty, the note says why.
        expected_nulls=(
            "taux_tva_reduite_chaussures_enfant_pct",
            "droit_douane_ue_chaussures_ch64_pct",
        ),
        simulated=False,
        source="Saisie manuelle depuis les sources officielles, URL par ligne dans source_url",
        directory=MANUAL,
    ),
    # TODO: decide with T3 / T4 how a table made of several dated snapshots is loaded.
}

TABLES: dict[str, TableSpec] = {**SIMULATED_TABLES, **REAL_TABLES}

# No correction yet: the v1 simulated tables are written to silver as they are.
# TODO T5: one entry per decision of docs/JOURNAL_NETTOYAGE.md (same identifier).
CORRECTIONS: list[Correction] = []


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_raw(path: Path) -> pd.DataFrame:
    """Read a bronze CSV file as text only: an empty cell is the only null value."""
    return pd.read_csv(
        path, dtype="string", encoding="utf-8-sig", keep_default_na=False, na_values=[""]
    )


def cast_column(raw: pd.Series, kind: str) -> pd.Series:
    """Cast a text column to its silver type; raise ValueError on any invalid value."""
    if kind == STR:
        return raw.astype("string")
    if kind == INT:
        return pd.to_numeric(raw, errors="raise").astype("Int64")
    if kind == FLOAT:
        return pd.to_numeric(raw, errors="raise").astype("Float64")
    if kind == BOOL:
        values = raw.map(BOOLEAN_VALUES)
        if (values.isna() & raw.notna()).any():
            raise ValueError(f"expected one of {sorted(BOOLEAN_VALUES)}")
        return values.astype("boolean")
    if kind == DATE:
        return pd.to_datetime(raw, format=DATE_FORMAT, errors="raise")
    raise ValueError(f"unknown column type: {kind}")


def cast_table(name: str, raw: pd.DataFrame, spec: TableSpec) -> pd.DataFrame:
    """Check that the columns match the spec, then cast each of them."""
    missing = [column for column in spec.columns if column not in raw.columns]
    unexpected = [column for column in raw.columns if column not in spec.columns]
    if missing or unexpected:
        raise ValueError(
            f"{name}: columns differ from its TableSpec "
            f"(missing: {missing}, unexpected: {unexpected})"
        )
    typed = {}
    for column, kind in spec.columns.items():
        try:
            typed[column] = cast_column(raw[column], kind)
        except (ValueError, TypeError) as error:
            raise ValueError(f"{name}.{column}: cannot cast to {kind} ({error})") from error
    return pd.DataFrame(typed)


def add_labels(name: str, df: pd.DataFrame, spec: TableSpec, seed: int) -> pd.DataFrame:
    """Add the est_simule and source columns (an existing source column is kept)."""
    labelled = df.copy()
    if SOURCE_COLUMN not in labelled.columns:
        source = spec.source
        if source is None and spec.simulated:
            source = SIMULATED_SOURCE.format(seed=seed)
        if source is None:
            raise ValueError(f"{name}: a real table needs the URL of its dated bronze file")
        labelled[SOURCE_COLUMN] = pd.Series(source, index=labelled.index, dtype="string")
    labelled[SIMULATED_COLUMN] = pd.Series(spec.simulated, index=labelled.index, dtype="boolean")
    return labelled


def count_duplicates(df: pd.DataFrame, key: tuple[str, ...]) -> int:
    """Number of rows that repeat an earlier row on the key."""
    return int(df.duplicated(list(key)).sum())


def count_nulls(df: pd.DataFrame) -> dict[str, int]:
    """Number of nulls of each column that has at least one."""
    counts = df.isna().sum()
    return {column: int(count) for column, count in counts.items() if count > 0}


def iqr_outliers(
    df: pd.DataFrame, column: str, groups: tuple[str, ...], multiplier: float
) -> pd.Series:
    """Flag the values outside [Q1 - multiplier x IQR, Q3 + multiplier x IQR].

    With `groups`, the quartiles are computed within each group of rows.
    """
    values = df[column].astype("float64")
    if groups:
        keys = list(groups)
        quartiles = (
            values.groupby([df[key] for key in keys])
            .quantile([LOWER_QUARTILE, UPPER_QUARTILE])
            .unstack()
        )
        bounds = df[keys].join(quartiles, on=keys)
        q1, q3 = bounds[LOWER_QUARTILE], bounds[UPPER_QUARTILE]
    else:
        q1, q3 = values.quantile(LOWER_QUARTILE), values.quantile(UPPER_QUARTILE)
    margin = (q3 - q1) * multiplier
    return (values < q1 - margin) | (values > q3 + margin)


def check_table(name: str, df: pd.DataFrame, spec: TableSpec, iqr_multiplier: float) -> list[dict]:
    """Run the three checks on a typed table; return one report row per finding."""
    findings = []

    def add(check: str, column: str, rows: int, detail: str, status: str) -> None:
        findings.append(dict(zip(REPORT_COLUMNS, [name, check, column, rows, detail, status])))

    duplicates = count_duplicates(df, spec.primary_key)
    if duplicates:
        key = ", ".join(spec.primary_key)
        add(CHECK_DUPLICATES, key, duplicates, "clé primaire répétée", STATUS_TO_REVIEW)

    for column, nulls in count_nulls(df).items():
        status = STATUS_EXPECTED if column in spec.expected_nulls else STATUS_TO_REVIEW
        add(CHECK_NULLS, column, nulls, f"sur {len(df)} lignes", status)

    for column, groups in spec.outlier_checks.items():
        outliers = int(iqr_outliers(df, column, groups, iqr_multiplier).sum())
        if outliers:
            scope = f"par {', '.join(groups)}" if groups else "sur toute la table"
            detail = f"hors Q1/Q3 ± {iqr_multiplier} × IQR, {scope}"
            add(CHECK_OUTLIERS, column, outliers, detail, STATUS_TO_REVIEW)

    return findings


def apply_corrections(name: str, df: pd.DataFrame, stage: str) -> pd.DataFrame:
    """Apply the registered corrections of a table for one stage, in order."""
    for correction in CORRECTIONS:
        if correction.table == name and correction.stage == stage:
            rows_before = len(df)
            df = correction.apply(df)
            print(f"  correction {correction.journal_id} : {rows_before} -> {len(df)} lignes")
    return df


def run(
    bronze_dir: Path = DEFAULT_BRONZE_DIR,
    silver_dir: Path = DEFAULT_SILVER_DIR,
    manual_dir: Path = DEFAULT_MANUAL_DIR,
    tables: dict[str, TableSpec] = TABLES,
):
    """Build the silver layer; return the check report as a DataFrame."""
    config = load_config()
    iqr_multiplier = config["nettoyage"]["iqr_multiplicateur"]
    silver_dir.mkdir(parents=True, exist_ok=True)
    input_dirs = {BRONZE: bronze_dir, MANUAL: manual_dir}

    findings = []
    for name, spec in tables.items():
        path = input_dirs[spec.directory] / f"{name}.csv"
        if not path.exists():
            if spec.simulated:
                raise FileNotFoundError(f"{path} is missing: run `make simulate` first")
            # A real table is optional: it only exists once it has been collected or typed in.
            print(f"{name:32s} absente : {path} n'existe pas encore (table réelle)")
            continue
        raw = apply_corrections(name, load_raw(path), STAGE_RAW)
        typed = cast_table(name, raw, spec)
        table_findings = check_table(name, typed, spec, iqr_multiplier)
        findings.extend(table_findings)
        corrected = apply_corrections(name, typed, STAGE_TYPED)
        silver = add_labels(name, corrected, spec, config["seed"])
        silver.to_parquet(silver_dir / f"{name}.parquet", index=False)
        to_review = sum(row["statut"] == STATUS_TO_REVIEW for row in table_findings)
        print(f"{name:32s} {len(silver):>8,d} lignes   {to_review} constat(s) à examiner")

    for layer, directory in input_dirs.items():
        for path in sorted(directory.glob("*.csv")) if directory.exists() else []:
            if path.stem not in tables or tables[path.stem].directory != layer:
                print(f"ignoré (aucun TableSpec déclaré) : {path}")

    report = pd.DataFrame(findings, columns=REPORT_COLUMNS)
    report.to_csv(silver_dir / REPORT_FILE, index=False, encoding="utf-8")
    print(f"\nTables Parquet et {REPORT_FILE} écrits dans : {silver_dir.resolve()}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL_DIR)
    parser.add_argument("--silver", type=Path, default=DEFAULT_SILVER_DIR)
    args = parser.parse_args()
    run(args.bronze, args.silver, args.manual)


if __name__ == "__main__":
    main()
