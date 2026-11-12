"""Tests of the Eurostat collector. No test reaches the network."""

import pandas as pd
import pytest

from src.collect import eurostat

SETTINGS = {"pays": ["FR", "GB"], "annee_depuis": 2018}
SERIES = eurostat.Series("taux_chomage_pct", "une_rt_a", {"unit": "PC_ACT"}, "%")


def payload(values, status=None):
    """A JSON-stat 2.0 answer: unit x geo x time, as the API returns it."""
    return {
        "id": ["unit", "geo", "time"],
        "size": [1, 2, 2],
        "updated": "2026-11-06T23:00:00+0100",
        "dimension": {
            "unit": {"category": {"index": {"PC_ACT": 0}, "label": {"PC_ACT": "% labour force"}}},
            "geo": {"category": {"index": {"FR": 0, "UK": 1}, "label": {"FR": "France"}}},
            "time": {"category": {"index": {"2024": 0, "2025": 1}, "label": {}}},
        },
        "value": values,
        "status": status or {},
    }


def raw(answer):
    return {"url": "https://example.org", "day": "2026-11-12", "payload": answer}


def test_values_by_key_decodes_the_flat_index():
    cube = eurostat.values_by_key(payload({"0": 7.4, "1": 7.7, "2": 4.3}, {"1": "d"}))
    assert cube[("PC_ACT", "FR", "2025")] == (7.7, "d")
    assert cube[("PC_ACT", "UK", "2024")] == (4.3, None)


def test_series_rows_keeps_the_latest_year_and_maps_gb_to_uk():
    rows = eurostat.series_rows(SERIES, raw(payload({"0": 7.4, "1": 7.7, "2": 4.3})), SETTINGS)
    by_country = {row["code_pays"]: row for row in rows}
    assert (by_country["FR"]["annee"], by_country["FR"]["valeur"]) == (2025, 7.7)
    assert (by_country["GB"]["annee"], by_country["GB"]["valeur"]) == (2024, 4.3)
    assert by_country["FR"]["note"] is None


def test_series_rows_leaves_a_todo_when_a_country_has_no_value():
    rows = eurostat.series_rows(SERIES, raw(payload({"1": 7.7})), SETTINGS)
    gb = next(row for row in rows if row["code_pays"] == "GB")
    assert gb["valeur"] is None and gb["annee"] is None
    assert gb["note"].startswith("TODO")


def test_a_filter_code_missing_from_the_answer_stops_the_script():
    wrong = eurostat.Series("x", "une_rt_a", {"unit": "PC_POP"}, "%")
    with pytest.raises(ValueError, match="PC_POP"):
        eurostat.series_rows(wrong, raw(payload({"0": 1.0})), SETTINGS)


def test_every_series_filter_is_asked_for_in_the_query():
    params = eurostat.query("prc_ppp_ind_1", ["FR", "GB"], 2018)
    assert ("geo", "UK") in params and ("sinceTimePeriod", "2018") in params
    assert ("ppp_cat18", "A01") in params and ("ppp_cat18", "A010302") in params


def test_compare_with_simulated_converts_population_to_millions():
    table = pd.DataFrame(
        [{"code_pays": "FR", "indicateur": "population", "valeur": 69_112_309, "annee": 2026}]
    )
    simulated = pd.DataFrame([{"code_pays": "FR", "population_millions": 68.4}])
    gap = eurostat.compare_with_simulated(table, simulated).iloc[0]
    assert (gap["reel"], gap["ecart"]) == (69.11, 0.71)


def test_history_rows_keep_every_published_year_and_no_empty_one():
    rows = eurostat.history_rows(SERIES, raw(payload({"0": 7.4, "1": 7.7, "2": 4.3})), SETTINGS)
    assert [(row["code_pays"], row["annee"], row["valeur"]) for row in rows] == [
        ("FR", 2024, 7.4),
        ("FR", 2025, 7.7),
        ("GB", 2024, 4.3),  # 2025 is not published for GB: no row, nothing filled in
    ]


def test_latest_year_of_the_history_is_the_value_of_eurostat_pays():
    answer = raw(payload({"0": 7.4, "1": 7.7, "2": 4.3}))
    latest = {
        row["code_pays"]: row["valeur"] for row in eurostat.series_rows(SERIES, answer, SETTINGS)
    }
    history = eurostat.history_rows(SERIES, answer, SETTINGS)
    last = {row["code_pays"]: row["valeur"] for row in sorted(history, key=lambda r: r["annee"])}
    assert latest == last
