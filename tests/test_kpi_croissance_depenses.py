"""Test of the Eurostat confirmation of sector growth, on a tiny dataset computed by hand."""

from pathlib import Path

import duckdb

from src.transform import run_kpi

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "kpi"
VIEW = "kpi_croissance_depenses_chaussures"


def test_household_footwear_spending_growth_is_a_cagr_of_eurostat_values(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(warehouse))
    con.execute("""
        CREATE TABLE parametres_kpi AS
        SELECT parametre, CAST(valeur AS DOUBLE) AS valeur FROM (VALUES
            ('kpi.tcam_annee_debut', 2022), ('kpi.tcam_annee_fin', 2025)
        ) AS t(parametre, valeur);
        CREATE TABLE eurostat_series AS SELECT * FROM (VALUES
            ('DE', 'depenses_menages_chaussures_meur', 2022, 10000.0, NULL, FALSE),
            ('DE', 'depenses_menages_chaussures_meur', 2024, 99999.0, NULL, FALSE),
            ('DE', 'depenses_menages_chaussures_meur', 2025, 13310.0, 'p', FALSE),
            ('DE', 'population', 2025, 83000000.0, NULL, FALSE),
            ('FR', 'depenses_menages_chaussures_meur', 2022, 8000.0, NULL, FALSE),
            ('FR', 'depenses_menages_chaussures_meur', 2025, 8000.0, NULL, FALSE),
            ('GB', 'depenses_menages_chaussures_meur', 2022, 5000.0, NULL, FALSE)
        ) AS t(code_pays, indicateur, annee, valeur, statut_eurostat, est_simule);
        """)
    con.close()
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / f"{VIEW}.sql").write_text(
        (SQL_DIR / f"{VIEW}.sql").read_text(encoding="utf-8"), encoding="utf-8"
    )
    run_kpi.run(warehouse, sql_dir)

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(
            f"SELECT code_pays, tcam_pct, statuts_eurostat, origine_donnees FROM {VIEW} ORDER BY 1"
        ).fetchall()
    finally:
        con.close()
    # DE: (13 310 / 10 000) ^ (1/3) - 1 = 10 % ; 2024 and other indicators ignored ;
    # the provisional flag is kept
    # FR: flat -> 0 % ; GB: no 2025 value published -> no row
    assert rows == [("DE", 10.0, "p", "REEL"), ("FR", 0.0, None, "REEL")]
