"""Test of the hub distance view on a tiny dataset computed by hand."""

from pathlib import Path

import duckdb
import pytest

from src.transform import run_kpi

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "kpi"
VIEW = "distance_hub"


@pytest.fixture
def warehouse(tmp_path):
    """Two cities and two hubs. For Z002, the nearest hub differs between real and simulated."""
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE osrm_distances (id_hub VARCHAR, id_zone VARCHAR, commune_hub VARCHAR,
            ville VARCHAR, distance_route_km DOUBLE, duree_h DOUBLE);
        INSERT INTO osrm_distances VALUES
            ('H01', 'Z001', 'Hubville', 'A', 500.0, 5.0),
            ('H02', 'Z001', 'Hubstadt', 'A', 220.0, 2.5),
            ('H01', 'Z002', 'Hubville', 'B', 300.0, 3.2),
            ('H02', 'Z002', 'Hubstadt', 'B', 330.0, 3.9);
        CREATE TABLE fact_logistique AS SELECT * FROM (VALUES
            ('H01', 'Z001', 480), ('H02', 'Z001', 200),
            ('H01', 'Z002', 320), ('H02', 'Z002', 300),
            ('H01', 'Z003', 100)
        ) AS t(id_hub, id_zone, distance_route_km);
        """)
    con.close()
    return path


def test_each_city_gets_its_nearest_hub_and_the_gap_with_the_simulated_distance(
    warehouse, tmp_path
):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / f"{VIEW}.sql").write_text(
        (SQL_DIR / f"{VIEW}.sql").read_text(encoding="utf-8"), encoding="utf-8"
    )
    run_kpi.run(warehouse, sql_dir)

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(
            f"SELECT id_zone, id_hub_le_plus_proche, commune_hub_le_plus_proche, "
            f"distance_reelle_km, "
            f"duree_conduite_h, id_hub_le_plus_proche_simule, distance_simulee_km, meme_hub, "
            f"ecart_km, ecart_pct FROM {VIEW} ORDER BY id_zone"
        ).fetchall()
    finally:
        con.close()
    assert rows == [
        # Nearest hub H02 in both: 220 - 200 = 20 km, 20 / 200 = 10 %
        ("Z001", "H02", "Hubstadt", 220.0, 2.5, "H02", 200, True, 20.0, 10.0),
        # Real: H01 at 300 km. Simulated: H02 at 300 km. Same distance, another hub.
        ("Z002", "H01", "Hubville", 300.0, 3.2, "H02", 300, False, 0.0, 0.0),
    ]  # Z003 has no real route: it is not in the view
