"""First data-quality checks on the simulated CSV files of the bronze layer.

The `tables` fixture (tests/conftest.py) holds the freshly generated dataset.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
HYPOTHESES = REPO_ROOT / "config" / "hypotheses.yaml"

# Primary key of each dimension table.
DIMENSION_KEYS = {
    "dim_pays": "code_pays",
    "dim_temps": "id_date",
    "dim_produit": "id_produit",
    "dim_magasin": "id_magasin",
    "dim_hub_logistique": "id_hub",
    "dim_zone_chalandise": "id_zone",
    "dim_concurrent": "id_concurrent",
}
FACT_TABLES = [
    "fact_ventes_france",
    "fact_marche",
    "fact_parts_de_marche",
    "fact_presence_concurrents",
    "fact_immobilier",
    "fact_logistique",
    "fact_fiscalite",
    "fact_couts_exploitation",
    "fact_prix_releves",
    "fact_penetration_categories",
    "fact_eligibilite_assortiment",
    "fact_tendances_recherche",
]
SALES_GRAIN = ["id_date", "id_magasin", "id_produit"]
# Foreign key of fact_ventes_france -> dimension that must contain it.
SALES_FOREIGN_KEYS = {
    "id_date": "dim_temps",
    "id_magasin": "dim_magasin",
    "id_produit": "dim_produit",
}
REFERENCE_COUNTRY = "FR"
PHYSICAL_STORE_CHANNEL = "Magasin physique"
# Amounts are stored rounded to the cent.
ROUNDING_TOLERANCE_EUR = 0.01


def test_all_expected_tables_are_generated_and_not_empty(tables):
    assert set(tables) == set(DIMENSION_KEYS) | set(FACT_TABLES)
    empty_tables = [name for name, df in tables.items() if df.empty]
    assert empty_tables == []


@pytest.mark.parametrize("table, key", DIMENSION_KEYS.items())
def test_dimension_primary_key_is_unique_and_not_null(tables, table, key):
    keys = tables[table][key]
    assert keys.notna().all()
    assert keys.is_unique


def test_sales_are_unique_at_month_store_product_grain(tables):
    sales = tables["fact_ventes_france"]
    assert not sales.duplicated(SALES_GRAIN).any()


@pytest.mark.parametrize("key, dimension", SALES_FOREIGN_KEYS.items())
def test_sales_have_no_orphan_key(tables, key, dimension):
    sales = tables["fact_ventes_france"]
    orphans = ~sales[key].isin(tables[dimension][key])
    assert not orphans.any()


def test_sales_amounts_are_consistent(tables):
    sales = tables["fact_ventes_france"]
    taxes = tables["fact_fiscalite"]
    vat_rate = (
        taxes.loc[taxes["code_pays"] == REFERENCE_COUNTRY, "taux_tva_standard_pct"].item() / 100
    )
    gaps = {
        "ca_net_ht = ca_net_ttc / (1 + vat)": (
            sales["ca_net_ht_eur"] - sales["ca_net_ttc_eur"] / (1 + vat_rate)
        ),
        "remise = ca_brut_ttc - ca_net_ttc": (
            sales["remise_eur"] - (sales["ca_brut_ttc_eur"] - sales["ca_net_ttc_eur"])
        ),
        "marge_brute = ca_net_ht - cout_marchandises": (
            sales["marge_brute_eur"] - (sales["ca_net_ht_eur"] - sales["cout_marchandises_eur"])
        ),
    }
    rows_out_of_tolerance = {
        rule: int((gap.abs() > ROUNDING_TOLERANCE_EUR).sum()) for rule, gap in gaps.items()
    }
    assert rows_out_of_tolerance == {rule: 0 for rule in gaps}


def test_physical_store_count_matches_hypotheses(tables):
    with HYPOTHESES.open(encoding="utf-8") as file:
        hypotheses = yaml.safe_load(file)
    stores = tables["dim_magasin"]
    physical_stores = stores[stores["canal"] == PHYSICAL_STORE_CHANNEL]
    assert len(physical_stores) == hypotheses["reseau_france"]["nb_magasins"]
