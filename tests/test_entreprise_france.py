"""Test of the entreprise_france view on a tiny warehouse whose results are computed by hand."""

from pathlib import Path

import duckdb

from src.transform import run_kpi

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "kpi" / "entreprise_france.sql"

# Three physical stores (one closed) and the web shop; sales in 2025 and in 2024 (ignored).
WAREHOUSE = """
    CREATE TABLE parametres_kpi AS SELECT * FROM (VALUES ('kpi.annee_reference', 2025.0))
        AS t(parametre, valeur);
    CREATE TABLE dim_magasin AS SELECT * FROM (VALUES
        ('M1', 'Centre commercial', NULL, TRUE),
        ('M2', 'Centre-ville', DATE '2025-04-01', TRUE),
        ('M3', 'Outlet', NULL, TRUE),
        ('WEB', 'E-commerce', NULL, TRUE)
    ) AS t(id_magasin, type_emplacement, date_fermeture, est_simule);
    CREATE TABLE dim_temps AS SELECT * FROM (VALUES (202401, 2024), (202501, 2025), (202512, 2025))
        AS t(id_date, annee);
    CREATE TABLE fact_ventes_france AS SELECT * FROM (VALUES
        ('M1', 202501, 1200.0, 1000.0, TRUE),
        ('M2', 202501, 600.0, 500.0, TRUE),
        ('WEB', 202512, 2400.0, 2000.0, TRUE),
        ('M3', 202512, 600.0, 500.0, TRUE),
        ('M1', 202401, 9999.0, 9999.0, TRUE)
    ) AS t(id_magasin, id_date, ca_net_ttc_eur, ca_net_ht_eur, est_simule);
    CREATE TABLE dim_produit AS SELECT * FROM (VALUES ('P1', TRUE), ('P2', TRUE), ('P3', TRUE))
        AS t(id_produit, est_simule);
"""


def test_company_figures_are_computed_from_the_warehouse(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(warehouse))
    con.execute(WAREHOUSE)
    con.close()
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / SQL_FILE.name).write_text(SQL_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    run_kpi.run(warehouse, sql_dir)

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute("SELECT * FROM entreprise_france").fetchall()
    finally:
        con.close()
    # 3 physical stores (the web shop is not one), 2 without a closing date.
    # 2025 only: TTC 1 200 + 600 + 2 400 + 600 = 4 800 ; HT 1 000 + 500 + 2 000 + 500 = 4 000.
    # Web share of the HT turnover: 2 000 / 4 000 = 50 %. 3 SKUs.
    assert rows == [(2025, 3, 2, 4800.0, 4000.0, 50.0, 3, "SIMULE")]
