"""Tests of the bronze -> silver step: typing, checks and Parquet output."""

import pandas as pd
import pytest

from src.transform import bronze_to_silver as b2s

IQR_MULTIPLIER = 1.5


def test_cast_column_rejects_a_value_that_does_not_fit_the_type():
    prices = pd.Series(["49.99", "49,99 €"], dtype="string")
    with pytest.raises(ValueError):
        b2s.cast_column(prices, b2s.FLOAT)
    flags = pd.Series(["True", "oui"], dtype="string")
    with pytest.raises(ValueError):
        b2s.cast_column(flags, b2s.BOOL)


def test_cast_table_rejects_columns_that_differ_from_the_spec():
    spec = b2s.TableSpec(columns={"id": b2s.STR, "prix": b2s.FLOAT}, primary_key=("id",))
    raw = pd.DataFrame({"id": ["a"], "price": ["1.0"]}, dtype="string")
    with pytest.raises(ValueError, match="missing: \\['prix'\\], unexpected: \\['price'\\]"):
        b2s.cast_table("t", raw, spec)


def test_count_duplicates_counts_the_rows_repeating_a_key():
    df = pd.DataFrame({"id": ["a", "a", "a", "b"], "mois": [1, 1, 2, 1]})
    assert b2s.count_duplicates(df, ("id", "mois")) == 1
    assert b2s.count_duplicates(df, ("id",)) == 2


def test_count_nulls_only_lists_columns_with_nulls():
    df = pd.DataFrame({"a": [1, None, None], "b": ["x", "y", "z"]})
    assert b2s.count_nulls(df) == {"a": 2}


def test_iqr_outliers_flags_values_outside_the_fences():
    # Q1 = 2, Q3 = 4, IQR = 2: the fences are -1 and 7.
    df = pd.DataFrame({"x": [1, 2, 3, 4, 100]})
    flagged = b2s.iqr_outliers(df, "x", (), IQR_MULTIPLIER)
    assert flagged.tolist() == [False, False, False, False, True]


def test_iqr_outliers_compares_values_within_their_group():
    # 100 is an outlier among the small values of group "a", not among those of group "b".
    df = pd.DataFrame({"g": ["a"] * 5 + ["b"] * 5, "x": [1, 2, 3, 4, 100, 98, 99, 100, 101, 102]})
    flagged = b2s.iqr_outliers(df, "x", ("g",), IQR_MULTIPLIER)
    assert flagged.tolist() == [False] * 4 + [True] + [False] * 5


def test_check_table_separates_expected_nulls_from_those_to_review():
    spec = b2s.TableSpec(
        columns={"id": b2s.STR, "a": b2s.FLOAT, "b": b2s.FLOAT},
        primary_key=("id",),
        expected_nulls=("a",),
    )
    df = pd.DataFrame({"id": ["x", "x"], "a": [None, 1.0], "b": [None, 2.0]})
    findings = b2s.check_table("t", df, spec, IQR_MULTIPLIER)
    statuses = {(row["controle"], row["colonne"]): row["statut"] for row in findings}
    assert statuses == {
        (b2s.CHECK_DUPLICATES, "id"): b2s.STATUS_TO_REVIEW,
        (b2s.CHECK_NULLS, "a"): b2s.STATUS_EXPECTED,
        (b2s.CHECK_NULLS, "b"): b2s.STATUS_TO_REVIEW,
    }


def test_every_bronze_table_is_written_to_silver_with_its_labels(silver, tables):
    silver_dir, _ = silver
    assert {path.stem for path in silver_dir.glob("*.parquet")} == set(tables)
    for name, bronze in tables.items():
        table = pd.read_parquet(silver_dir / f"{name}.parquet")
        assert len(table) == len(bronze), name
        assert table[b2s.SIMULATED_COLUMN].all(), name
        assert table[b2s.SOURCE_COLUMN].notna().all(), name


def test_customs_codes_keep_their_trailing_zero(silver):
    silver_dir, _ = silver
    products = pd.read_parquet(silver_dir / "dim_produit.parquet")
    assert "6402.20" in set(products["code_sh"])


def test_simulated_dataset_has_no_duplicate_and_no_unexpected_null(silver):
    _, report = silver
    to_review = report[report["statut"] == b2s.STATUS_TO_REVIEW]
    assert set(to_review["controle"]) <= {b2s.CHECK_OUTLIERS}


# A stand-in for a table typed in by hand: example values, not real ones.
MANUAL_EXAMPLE = "saisie_exemple"
MANUAL_EXAMPLE_SPEC = b2s.TableSpec(
    columns={
        "code_pays": b2s.STR,
        "taux_exemple_pct": b2s.FLOAT,
        "source_url": b2s.STR,
        "date_consultation": b2s.DATE,
    },
    primary_key=("code_pays",),
    simulated=False,
    source="Saisie manuelle : URL de chaque ligne dans source_url",
    directory=b2s.MANUAL,
)
MANUAL_EXAMPLE_CSV = (
    "code_pays,taux_exemple_pct,source_url,date_consultation\n"
    "FR,10.0,https://example.org/fr,2026-11-12\n"
    "DE,,https://example.org/de,2026-11-12\n"
)


def test_manual_table_is_read_from_the_manual_directory(tmp_path):
    bronze_dir, manual_dir, silver_dir = (
        tmp_path / name for name in ("bronze", "manual", "silver")
    )
    bronze_dir.mkdir()
    manual_dir.mkdir()
    (manual_dir / f"{MANUAL_EXAMPLE}.csv").write_text(MANUAL_EXAMPLE_CSV, encoding="utf-8")

    tables = {MANUAL_EXAMPLE: MANUAL_EXAMPLE_SPEC}
    report = b2s.run(bronze_dir, silver_dir, manual_dir, tables)

    table = pd.read_parquet(silver_dir / f"{MANUAL_EXAMPLE}.parquet")
    assert table["code_pays"].tolist() == ["FR", "DE"]
    assert not table[b2s.SIMULATED_COLUMN].any()
    assert table[b2s.SOURCE_COLUMN].notna().all()
    assert str(table["date_consultation"].dt.date.iloc[0]) == "2026-11-12"
    # The empty rate is reported like any other missing value.
    nulls = report[report["controle"] == b2s.CHECK_NULLS]
    assert nulls[["colonne", "nb_lignes", "statut"]].values.tolist() == [
        ["taux_exemple_pct", 1, b2s.STATUS_TO_REVIEW]
    ]


def test_manual_table_is_not_looked_for_in_the_bronze_directory(tmp_path):
    bronze_dir, manual_dir, silver_dir = (
        tmp_path / name for name in ("bronze", "manual", "silver")
    )
    bronze_dir.mkdir()
    manual_dir.mkdir()
    # The file sits in bronze, but the table is declared as a manual one.
    (bronze_dir / f"{MANUAL_EXAMPLE}.csv").write_text(MANUAL_EXAMPLE_CSV, encoding="utf-8")
    report = b2s.run(bronze_dir, silver_dir, manual_dir, {MANUAL_EXAMPLE: MANUAL_EXAMPLE_SPEC})
    # A real table whose file is missing is skipped, not read from the other directory.
    assert not (silver_dir / f"{MANUAL_EXAMPLE}.parquet").exists()
    assert report.empty


def test_missing_simulated_table_stops_the_run(tmp_path):
    spec = b2s.SIMULATED_TABLES["dim_pays"]
    with pytest.raises(FileNotFoundError, match="make simulate"):
        b2s.run(tmp_path / "bronze", tmp_path / "silver", tmp_path / "manual", {"dim_pays": spec})
