"""Tests of the CSV exports read by the dashboard, on a tiny warehouse written by hand."""

import csv

import duckdb
import pytest

from src.transform import export_gold

REQUIRED = ("villes", "synthese")
OPTIONAL = ("commentaires",)


@pytest.fixture
def warehouse(tmp_path):
    """One table and one view; the optional object is not there yet."""
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute("""
        CREATE TABLE villes AS SELECT * FROM (VALUES
            ('Z002', 'Köln', 1.09, DATE '2024-12-31', FALSE),
            ('Z001', 'Orléans', NULL, DATE '2024-12-31', TRUE)
        ) AS t(id_zone, ville, population_millions, date_reference, est_simule);
        CREATE VIEW synthese AS
            SELECT 'Prix' AS axe, '≥ 95' AS seuil, count(*) AS nb_villes FROM villes;
        """)
    con.close()
    return path


def read(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def test_each_object_is_written_with_the_column_names_of_the_warehouse(warehouse, tmp_path):
    exports = tmp_path / "exports"
    written = export_gold.export(warehouse, exports, REQUIRED, OPTIONAL)
    assert written == {"villes": 2, "synthese": 1}
    # Rows are sorted, a missing value is an empty cell, dates are ISO.
    assert read(exports / "villes.csv") == [
        ["id_zone", "ville", "population_millions", "date_reference", "est_simule"],
        ["Z001", "Orléans", "", "2024-12-31", "True"],
        ["Z002", "Köln", "1.09", "2024-12-31", "False"],
    ]
    assert read(exports / "synthese.csv") == [["axe", "seuil", "nb_villes"], ["Prix", "≥ 95", "2"]]


def test_files_are_utf8_without_bom_and_with_lf_line_ends(warehouse, tmp_path):
    exports = tmp_path / "exports"
    export_gold.export(warehouse, exports, REQUIRED, OPTIONAL)
    content = (exports / "villes.csv").read_bytes()
    assert "Köln".encode("utf-8") in content
    assert not content.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in content


def test_missing_optional_object_is_skipped_and_its_previous_export_is_kept(warehouse, tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    previous = exports / "commentaires.csv"
    previous.write_text("page,commentaire\n", encoding="utf-8")
    written = export_gold.export(warehouse, exports, REQUIRED, OPTIONAL)
    assert "commentaires" not in written
    assert previous.read_text(encoding="utf-8") == "page,commentaire\n"


def test_optional_object_is_exported_as_soon_as_it_exists(warehouse, tmp_path):
    con = duckdb.connect(str(warehouse))
    con.execute("CREATE TABLE commentaires AS SELECT 'Synthèse' AS page, 'Go' AS commentaire")
    con.close()
    exports = tmp_path / "exports"
    written = export_gold.export(warehouse, exports, REQUIRED, OPTIONAL)
    assert written["commentaires"] == 1
    assert read(exports / "commentaires.csv") == [["page", "commentaire"], ["Synthèse", "Go"]]


def test_missing_required_object_stops_the_export_and_names_it(warehouse, tmp_path):
    exports = tmp_path / "exports"
    with pytest.raises(LookupError, match="kpi_summary"):
        export_gold.export(warehouse, exports, (*REQUIRED, "kpi_summary"), OPTIONAL)
    assert not exports.exists()  # nothing is written when the export cannot be complete


def test_missing_warehouse_names_the_target_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="make gold"):
        export_gold.export(tmp_path / "absent.duckdb", tmp_path / "exports")


def test_ai_commentary_file_is_copied_byte_for_byte_when_it_exists(tmp_path):
    source = tmp_path / "gold" / "ai_commentary.csv"
    source.parent.mkdir()
    content = "page,valeur_filtre,commentaire\nSynthèse,DE,« GO conditionnel »\r\n".encode("utf-8")
    source.write_bytes(content)
    exports = tmp_path / "exports"
    assert export_gold.copy_ai_commentary(source, exports)
    assert (exports / "ai_commentary.csv").read_bytes() == content


def test_missing_ai_commentary_file_is_not_an_error(tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    assert not export_gold.copy_ai_commentary(tmp_path / "ai_commentary.csv", exports)
    assert list(exports.iterdir()) == []
