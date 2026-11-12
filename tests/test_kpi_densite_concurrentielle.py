"""Test of the competitive density view on a tiny dataset computed by hand."""

from pathlib import Path

import duckdb
import pytest

from src.transform import run_kpi

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "kpi"
VIEW = "densite_concurrentielle"


@pytest.fixture
def warehouse(tmp_path):
    """Two cities: A has every population, B has no OSM population."""
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE osm_villes AS SELECT * FROM (VALUES
            ('Z001', 'A', 50, 400000, 2023),
            ('Z002', 'B', 30, NULL, NULL)
        ) AS t(id_zone, ville, nb_magasins_chaussures, population_osm, annee_population_osm);
        CREATE TABLE destatis_population_villes AS SELECT * FROM (VALUES
            ('Z001', 500000, DATE '2024-12-31'),
            ('Z002', 200000, DATE '2024-12-31')
        ) AS t(id_zone, population, date_reference);
        CREATE TABLE dim_zone_chalandise AS SELECT * FROM (VALUES
            ('Z001', 0.25, 6.5),
            ('Z002', 0.3, 7.0),
            ('Z003', 1.0, 5.0)
        ) AS t(id_zone, population_ville_millions, densite_concurrentielle_pour_100k_hab);
        """)
    con.close()
    return path


def test_density_is_shops_per_100000_inhabitants_of_the_official_population(warehouse, tmp_path):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / f"{VIEW}.sql").write_text(
        (SQL_DIR / f"{VIEW}.sql").read_text(encoding="utf-8"), encoding="utf-8"
    )
    run_kpi.run(warehouse, sql_dir)

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(
            f"SELECT id_zone, densite_pour_100k_hab, densite_population_osm, "
            f"densite_population_simulee, densite_simulee, origine_donnees "
            f"FROM {VIEW} ORDER BY id_zone"
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        # 50 / 500 000 = 10 ; 50 / 400 000 = 12.5 ; 50 / 250 000 = 20
        ("Z001", 10.0, 12.5, 20.0, 6.5, "REEL"),
        # 30 / 200 000 = 15 ; no OSM population ; 30 / 300 000 = 10
        ("Z002", 15.0, None, 10.0, 7.0, "REEL"),
    ]  # Z003 has no real data: it is not in the view
