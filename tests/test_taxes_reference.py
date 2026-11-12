"""Tests of data/manual/taxes_reference.csv (T18), typed in by hand from official sources.

They check what a hand-typed file can get wrong: one row per country of dim_pays, a source
and a date on every row, plausible rates, and a note wherever a cell is left empty. They do
not check the values themselves: only the person who read the official page can.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.transform import bronze_to_silver as b2s

TAXES_FILE = Path(__file__).resolve().parents[1] / "data" / "manual" / "taxes_reference.csv"
SPEC = b2s.TABLES["taxes_reference"]
RATES = [column for column, kind in SPEC.columns.items() if column.endswith("_pct")]
REQUIRED_RATES = [column for column in RATES if column not in SPEC.expected_nulls]


@pytest.fixture(scope="module")
def taxes():
    return pd.read_csv(TAXES_FILE, encoding="utf-8", dtype="string", keep_default_na=False)


def test_columns_match_the_declared_table(taxes):
    assert list(taxes.columns) == list(SPEC.columns)


def test_one_row_per_country_of_dim_pays(taxes, tables):
    countries = list(taxes["code_pays"])
    assert len(countries) == len(set(countries))
    assert set(countries) == set(tables["dim_pays"]["code_pays"])


def test_every_row_has_its_official_sources_and_reading_date(taxes):
    for _, row in taxes.iterrows():
        urls = [url.strip() for url in row["source_url"].split(";") if url.strip()]
        assert urls and all(url.startswith("https://") for url in urls), row["code_pays"]
        assert pd.notna(pd.to_datetime(row["date_consultation"], format="%Y-%m-%d"))


def test_rates_are_percentages_and_required_ones_are_filled(taxes):
    for column in RATES:
        filled = taxes[column] != ""
        values = pd.to_numeric(taxes.loc[filled, column])
        assert values.between(0, 100).all(), column
        if column in REQUIRED_RATES:
            assert filled.all(), column


def test_an_empty_cell_is_explained_by_the_note(taxes):
    for column in SPEC.expected_nulls:
        empty = taxes[taxes[column] == ""]
        assert (empty["note"].str.len() > 0).all(), column
    assert (taxes["note"].str.len() > 0).all()
