"""Tests of the runner that executes the KPI views of sql/kpi/ on the warehouse."""

import duckdb
import pytest

from src.transform import run_kpi


@pytest.fixture
def warehouse(tmp_path):
    """A tiny warehouse with one table of three rows."""
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE ventes AS SELECT * FROM (VALUES (10), (20), (30)) AS t(ca)")
    con.close()
    return path


def test_empty_directory_is_not_an_error(warehouse, tmp_path):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    assert run_kpi.run(warehouse, sql_dir) == []


def test_views_are_created_whatever_the_order_of_the_file_names(warehouse, tmp_path):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    # a_summary reads the view of b_total, although its file name comes first.
    (sql_dir / "a_summary.sql").write_text(
        "CREATE OR REPLACE VIEW a_summary AS SELECT total * 2 AS double_total FROM b_total"
    )
    (sql_dir / "b_total.sql").write_text(
        "CREATE OR REPLACE VIEW b_total AS SELECT sum(ca) AS total FROM ventes"
    )
    assert run_kpi.run(warehouse, sql_dir) == ["b_total.sql", "a_summary.sql"]
    # Running the target a second time must work as well.
    run_kpi.run(warehouse, sql_dir)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        assert con.execute("SELECT double_total FROM a_summary").fetchone()[0] == 120
    finally:
        con.close()


def test_a_view_on_a_missing_table_fails_with_the_file_name(warehouse, tmp_path):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / "broken.sql").write_text("CREATE OR REPLACE VIEW broken AS SELECT * FROM absente")
    with pytest.raises(RuntimeError, match="broken.sql"):
        run_kpi.run(warehouse, sql_dir)


def test_a_syntax_error_fails_with_the_file_name(warehouse, tmp_path):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / "typo.sql").write_text("CREATE OR REPLACE VIEW typo AS SELEC 1")
    with pytest.raises(RuntimeError, match="typo.sql"):
        run_kpi.run(warehouse, sql_dir)
