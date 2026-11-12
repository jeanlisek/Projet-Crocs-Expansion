"""Tests of the Destatis extractor, on a small workbook built for the purpose."""

import openpyxl
import pandas as pd
import pytest

from src.collect import destatis

SETTINGS = destatis.load_config()
TITLE = "Städte nach Fläche, Bevölkerung und Bevölkerungsdichte am 31.12.2024 (Jahr)"
HEADERS = [
    "Laufende Nummer",
    "Amtlicher Regionalschlüssel",
    "Stadt",
    "Postleitzahl ",
    "Fläche km² ¹⁾",
    "Bevölkerung auf Grundlage des ZENSUS 2022 ²⁾ insgesamt",
    "Bevölkerung auf Grundlage des ZENSUS 2022 ²⁾ männlich",
]
# Example rows with made-up populations: only the layout matters here.
ROWS = [
    ["1", "020000000000", "Hamburg, Freie und Hansestadt", "20038", 755.09, 1000, 490],
    ["2", "032410001001", "Hannover, Landeshauptstadt", "30159", 204.3, 500, 245],
    ["3", "053150000000", "Köln, Stadt", "50667", 405.02, 800, 390],
    [None, None, None, None, None, None, None],
    ["1) Fußnote", None, None, None, None, None, None],
]


def write_inputs(bronze_dir, rows=ROWS, codes=("02000000", "03241001")):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = destatis.SHEET
    for row in [[TITLE], HEADERS, *rows]:
        sheet.append(row)
    workbook.save(bronze_dir / SETTINGS["fichier"])
    cities = pd.DataFrame(
        {
            "id_zone": [f"Z{index:03d}" for index in range(1, len(codes) + 1)],
            "ville": [f"Ville {index}" for index in range(1, len(codes) + 1)],
            "code_communal": list(codes),
        }
    )
    cities.to_csv(
        bronze_dir / f"{destatis.OSM_CITIES_TABLE}.csv", index=False, encoding="utf-8-sig"
    )


def test_municipality_code_is_read_from_the_regional_key():
    assert destatis.municipality_code("053150000000") == "05315000"
    assert destatis.municipality_code("032410001001") == "03241001"  # with an association


def test_population_is_matched_on_the_municipality_code(tmp_path):
    write_inputs(tmp_path)
    population = destatis.extract(tmp_path)
    assert population["code_communal"].tolist() == ["02000000", "03241001"]  # leading zero kept
    assert population["nom_destatis"].tolist() == [
        "Hamburg, Freie und Hansestadt",
        "Hannover, Landeshauptstadt",
    ]
    assert population["population"].tolist() == [1000, 500]
    assert set(population["date_reference"]) == {"2024-12-31"}  # read from the sheet title
    assert set(population["source_url"]) == {SETTINGS["page_url"]}
    assert set(population["date_consultation"]) == {SETTINGS["date_consultation"]}
    written = pd.read_csv(
        tmp_path / f"{destatis.POPULATION_TABLE}.csv", encoding="utf-8-sig", dtype=str
    )
    assert written["code_communal"].tolist() == ["02000000", "03241001"]


def test_city_missing_from_the_workbook_stops_the_extraction(tmp_path):
    write_inputs(tmp_path, codes=("02000000", "99999999"))
    with pytest.raises(ValueError, match="99999999, found 0"):
        destatis.extract(tmp_path)


def test_city_present_twice_in_the_workbook_stops_the_extraction(tmp_path):
    write_inputs(tmp_path, rows=[ROWS[0], ROWS[0]], codes=("02000000",))
    with pytest.raises(ValueError, match="found 2"):
        destatis.extract(tmp_path)


def test_sheet_title_without_a_single_reference_date_is_rejected(tmp_path):
    write_inputs(tmp_path)
    workbook = openpyxl.load_workbook(tmp_path / SETTINGS["fichier"])
    workbook[destatis.SHEET]["A1"] = "Städte nach Fläche und Bevölkerung"
    workbook.save(tmp_path / SETTINGS["fichier"])
    with pytest.raises(ValueError, match="reference date"):
        destatis.extract(tmp_path)
