"""Quality tests of the gold layer: the DuckDB warehouse is queried in SQL."""

import shutil

import duckdb
import pandas as pd
import pytest

from src.transform import bronze_to_silver as b2s
from src.transform import build_gold

# Every column holding a price: it must be filled and strictly positive.
PRICE_COLUMNS = [
    ("dim_produit", "prix_vente_ttc_fr"),
    ("dim_produit", "prix_vente_ht_fr"),
    ("dim_concurrent", "prix_moyen_eur"),
    ("fact_prix_releves", "prix_affiche_eur"),
    ("fact_prix_releves", "prix_affiche_devise_locale"),
]
COUNTRY_COLUMN = "code_pays"
COUNTRY_DIMENSION = "dim_pays"
GRAINS = [(name, spec.primary_key) for name, spec in b2s.SIMULATED_TABLES.items()]


@pytest.fixture(scope="session")
def gold(silver, tmp_path_factory):
    """Build the warehouse once from the generated dataset; yield a read-only connection."""
    silver_dir, _ = silver
    warehouse = tmp_path_factory.mktemp("gold") / "warehouse.duckdb"
    build_gold.build(silver_dir, warehouse)
    con = duckdb.connect(str(warehouse), read_only=True)
    yield con
    con.close()


def count(con, query):
    return con.execute(query).fetchone()[0]


def test_every_table_is_loaded_with_all_its_rows(gold, tables):
    loaded = {name for (name,) in gold.execute("SHOW TABLES").fetchall()}
    assert loaded == set(tables)
    for name, bronze in tables.items():
        assert count(gold, f'SELECT count(*) FROM "{name}"') == len(bronze), name


@pytest.mark.parametrize("table, grain", GRAINS)
def test_table_is_unique_at_its_grain(gold, table, grain):
    key = ", ".join(f'"{column}"' for column in grain)
    duplicated_keys = count(
        gold,
        f'SELECT count(*) FROM (SELECT {key} FROM "{table}" GROUP BY {key} HAVING count(*) > 1)',
    )
    assert duplicated_keys == 0


@pytest.mark.parametrize("table, column, dimension", build_gold.RELATIONSHIPS)
def test_relationship_has_no_orphan_key(gold, table, column, dimension):
    # A missing key counts as an orphan: every relationship of the model is mandatory.
    key = build_gold.dimension_key(b2s.SIMULATED_TABLES, dimension)
    orphans = count(
        gold,
        f'SELECT count(*) FROM "{table}" AS child '
        f'LEFT JOIN "{dimension}" AS parent ON child."{column}" = parent."{key}" '
        f'WHERE parent."{key}" IS NULL',
    )
    assert orphans == 0


@pytest.mark.parametrize("table, column", PRICE_COLUMNS)
def test_price_is_filled_and_strictly_positive(gold, table, column):
    invalid = count(
        gold, f'SELECT count(*) FROM "{table}" WHERE "{column}" IS NULL OR "{column}" <= 0'
    )
    assert invalid == 0


def test_every_country_code_exists_in_dim_pays(gold):
    tables_with_country = [
        name
        for (name,) in gold.execute(
            "SELECT table_name FROM information_schema.columns WHERE column_name = ?",
            [COUNTRY_COLUMN],
        ).fetchall()
        if name != COUNTRY_DIMENSION
    ]
    assert tables_with_country, "no table with a country code was found"
    unknown = {
        name: count(
            gold,
            f'SELECT count(*) FROM "{name}" WHERE "{COUNTRY_COLUMN}" IS NULL '
            f'OR "{COUNTRY_COLUMN}" NOT IN (SELECT "{COUNTRY_COLUMN}" FROM "{COUNTRY_DIMENSION}")',
        )
        for name in tables_with_country
    }
    assert unknown == {name: 0 for name in tables_with_country}


def test_model_is_declared_as_keys_in_the_warehouse(gold):
    constraints = dict(
        gold.execute(
            "SELECT constraint_type, count(*) FROM duckdb_constraints() GROUP BY constraint_type"
        ).fetchall()
    )
    assert constraints["PRIMARY KEY"] == len(b2s.SIMULATED_TABLES)
    assert constraints["FOREIGN KEY"] == len(build_gold.RELATIONSHIPS)


def test_warehouse_rejects_an_orphan_key(silver, tmp_path):
    silver_dir, _ = silver
    warehouse = tmp_path / "warehouse.duckdb"
    build_gold.build(silver_dir, warehouse)
    con = duckdb.connect(str(warehouse))
    try:
        with pytest.raises(duckdb.ConstraintException):
            con.execute(
                "INSERT INTO fact_presence_concurrents "
                "SELECT * REPLACE ('Z999' AS id_zone) FROM fact_presence_concurrents LIMIT 1"
            )
    finally:
        con.close()


def test_real_table_is_loaded_next_to_the_simulated_ones(silver, tmp_path):
    # Work on a private copy of the silver layer: the shared one must stay as generated.
    silver_dir = tmp_path / "silver"
    shutil.copytree(silver[0], silver_dir)
    # A stand-in for a future real table: its own name, its own file, flagged as not simulated.
    name = "reel_exemple"
    spec = b2s.TableSpec(
        columns={"code_pays": b2s.STR, "valeur": b2s.FLOAT},
        primary_key=("code_pays",),
        simulated=False,
        source="https://example.org/fichier-date.csv",
    )
    typed = pd.DataFrame({"code_pays": ["FR", "DE"], "valeur": [1.0, 2.0]})
    b2s.add_labels(name, typed, spec, seed=0).to_parquet(silver_dir / f"{name}.parquet")

    warehouse = tmp_path / "warehouse.duckdb"
    rows = build_gold.build(silver_dir, warehouse, real={name: spec})
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        assert rows[name] == 2
        assert count(con, f'SELECT count(*) FROM "{name}" WHERE NOT est_simule') == 2
        # The simulated country dimension is untouched: nothing was merged into it.
        assert rows[COUNTRY_DIMENSION] == count(con, f'SELECT count(*) FROM "{COUNTRY_DIMENSION}"')
        assert (
            count(con, f'SELECT count(*) FROM "{COUNTRY_DIMENSION}" WHERE est_simule')
            == rows[COUNTRY_DIMENSION]
        )
    finally:
        con.close()


def test_real_table_cannot_reuse_a_simulated_table_name(silver, tmp_path):
    silver_dir, _ = silver
    spec = b2s.SIMULATED_TABLES[COUNTRY_DIMENSION]
    with pytest.raises(ValueError, match="must not reuse"):
        build_gold.build(silver_dir, tmp_path / "warehouse.duckdb", real={COUNTRY_DIMENSION: spec})
