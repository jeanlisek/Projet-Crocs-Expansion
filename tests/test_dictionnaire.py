"""Tests of the field dictionary generator (T12)."""

import duckdb
import pytest

from src.collect import dictionnaire
from src.transform import bronze_to_silver as b2s
from src.transform import build_gold


@pytest.fixture(scope="module")
def warehouse(silver, tmp_path_factory):
    """The warehouse built from the generated dataset, as `make gold` builds it."""
    silver_dir, _ = silver
    path = tmp_path_factory.mktemp("gold") / "warehouse.duckdb"
    build_gold.build(silver_dir, path)
    return path


def test_every_formula_holds_on_the_generated_data(warehouse):
    text = dictionnaire.build(warehouse)
    assert "ne tient pas" not in text


def test_every_declared_table_has_a_description_and_every_column_a_definition():
    # Every table the pipeline can load is described, real ones included (even when their
    # file is not collected yet), so that a rerun never leaves a table without description.
    assert set(b2s.TABLES) <= set(dictionnaire.TABLE_INFO)
    for name, spec in b2s.TABLES.items():
        for column in spec.columns:
            known = dictionnaire.FIELDS.get(name, {}).get(column) or dictionnaire.COMMON.get(column)
            assert known, f"{name}.{column} sans description"


def test_a_formula_that_does_not_hold_becomes_a_todo():
    con = duckdb.connect()
    con.execute("CREATE TABLE dim_produit (prix_vente_ttc_fr DOUBLE, prix_vente_ht_fr DOUBLE)")
    con.execute("INSERT INTO dim_produit VALUES (60.0, 50.0)")
    assert (
        dictionnaire.formula(con, "dim_produit", "prix_vente_ht_fr") == "prix_vente_ttc_fr ÷ 1,20"
    )
    con.execute("INSERT INTO dim_produit VALUES (60.0, 55.0)")
    assert dictionnaire.formula(con, "dim_produit", "prix_vente_ht_fr").startswith("TODO")
    assert dictionnaire.formula(con, "dim_produit", "prix_vente_ttc_fr") == ""


def test_cells_are_escaped_for_markdown():
    assert dictionnaire.cell("a | b\nc") == "a \\| b c"
