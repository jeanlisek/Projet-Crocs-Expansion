"""Tests of the OpenStreetMap collector. No test reaches the network: `fetch` is replaced."""

import json

import pandas as pd
import pytest

from src.collect import osm
from src.transform import bronze_to_silver as b2s
from src.transform import build_gold

SETTINGS = osm.load_config()
DELAY = SETTINGS["delai_entre_requetes_s"]
WAIT_AFTER_REFUSAL = SETTINGS["overpass"]["attente_apres_refus_s"]
MAX_ATTEMPTS = SETTINGS["overpass"]["essais_max"]


def answer(name="Teststadt", population="100000", source_population="Statistikamt (2023)"):
    """A minimal Overpass answer: one city boundary and three shoe shops."""
    boundary_tags = {
        "boundary": "administrative",
        "name": name,
        "admin_level": "6",
        osm.MUNICIPALITY_CODE_TAG: "02000000",
    }
    if population:
        boundary_tags["population"] = population
    if source_population:
        boundary_tags["source:population"] = source_population
    return {
        "elements": [
            {"type": "relation", "id": 1, "tags": boundary_tags},
            {
                "type": "node",
                "id": 10,
                "lat": 50.0,
                "lon": 8.0,
                "tags": {"shop": "shoes", "name": "Schuhhaus", "brand": "Deichmann"},
            },
            {
                "type": "way",
                "id": 11,
                "center": {"lat": 50.1, "lon": 8.1},
                "tags": {"shop": "shoes", "name": "Laden"},
            },
            {"type": "node", "id": 12, "lat": 50.2, "lon": 8.2, "tags": {"shop": "shoes"}},
        ]
    }


@pytest.fixture
def bronze(tmp_path):
    """A bronze directory holding two target cities and one city of another country."""
    cities = pd.DataFrame(
        {
            "id_zone": ["Z001", "Z002", "Z013"],
            "code_pays": [SETTINGS["pays_cible"], SETTINGS["pays_cible"], "ES"],
            "ville": ["Berlin", "Frankfurt", "Madrid"],
        }
    )
    cities.to_csv(tmp_path / f"{osm.CITY_TABLE}.csv", index=False, encoding="utf-8-sig")
    return tmp_path


@pytest.fixture
def network(monkeypatch):
    """Replace the network and the clock: record the queries sent and the pauses taken."""
    calls = {"queries": [], "pauses": []}

    def fake_fetch(query, settings):
        calls["queries"].append(query)
        return answer()

    monkeypatch.setattr(osm, "fetch", fake_fetch)
    monkeypatch.setattr(osm.time, "sleep", calls["pauses"].append)
    return calls


def test_query_uses_the_osm_name_of_the_city_and_the_shoe_shop_tag():
    query = osm.build_query("Frankfurt", "DE", 60)
    assert '["name"="Frankfurt am Main"]' in query
    assert '["shop"="shoes"]' in query
    assert '["ISO3166-1"="DE"]' in query


def test_answer_is_split_into_one_boundary_and_its_shops():
    boundary, shops = osm.parse_answer(answer())
    assert boundary["id"] == 1
    assert [shop["id"] for shop in shops] == [10, 11, 12]


@pytest.mark.parametrize("boundaries", [0, 2])
def test_answer_without_exactly_one_boundary_is_rejected(boundaries):
    payload = answer()
    shops = payload["elements"][1:]
    payload["elements"] = [payload["elements"][0]] * boundaries + shops
    with pytest.raises(ValueError, match="expected one city boundary"):
        osm.parse_answer(payload)


@pytest.mark.parametrize(
    "tags, expected",
    [
        ({"population:date": "2022-12-31"}, (2022, "population:date")),
        ({"source:population": "Stadt Köln (2023) - Statistik"}, (2023, "source:population")),
        (
            {"source:population": "https://example.org/SB_A01-05-00_2020h02_BE.pdf"},
            (2020, "source:population"),
        ),
        # Two different years, or none: the year is left empty rather than guessed.
        ({"source:population": "Zensus 2011, Fortschreibung 2022"}, (None, None)),
        ({"source:population": "Statistikamt"}, (None, None)),
        ({}, (None, None)),
    ],
)
def test_population_year_is_read_only_when_unambiguous(tags, expected):
    assert osm.population_year(tags) == expected


def test_collect_asks_once_per_target_city_and_spaces_the_requests(bronze, network):
    cities = osm.collect(bronze)
    assert cities["ville"].tolist() == ["Berlin", "Frankfurt"]  # Madrid is not a target city
    assert len(network["queries"]) == 2
    assert network["pauses"] == [DELAY]  # one pause, between the two requests
    assert cities["nb_magasins_chaussures"].tolist() == [3, 3]
    assert cities["nb_magasins_avec_enseigne"].tolist() == [1, 1]
    assert cities["annee_population_osm"].tolist() == [2023, 2023]
    assert len(list(bronze.glob("osm_overpass_Z00*_*.json"))) == 2


def test_collect_never_asks_again_for_a_city_already_in_cache(bronze, network):
    osm.collect(bronze)
    osm.collect(bronze)
    assert len(network["queries"]) == 2


def test_collect_writes_one_row_per_shop(bronze, network):
    osm.collect(bronze, only=["Berlin"])
    shops = pd.read_csv(bronze / f"{osm.OSM_SHOPS_TABLE}.csv", encoding="utf-8-sig")
    assert shops["osm_id"].tolist() == [10, 11, 12]
    assert shops["enseigne"].fillna("").tolist() == ["Deichmann", "", ""]
    assert shops["latitude"].tolist() == [50.0, 50.1, 50.2]  # a way is located by its center
    assert shops["source"].str.contains("OpenStreetMap").all()


def test_collect_rejects_a_city_that_is_not_a_target(bronze, network):
    with pytest.raises(ValueError, match="Madrid"):
        osm.collect(bronze, only=["Madrid"])
    assert network["queries"] == []


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise osm.requests.HTTPError(str(self.status_code))

    def json(self):
        return answer()


def stub_http(monkeypatch, statuses):
    """Make requests.post answer with the given statuses; record headers and pauses."""
    seen = {"headers": [], "pauses": []}
    remaining = list(statuses)

    def fake_post(url, data, headers, timeout):
        seen["headers"].append(headers)
        return FakeResponse(remaining.pop(0))

    monkeypatch.setattr(osm.requests, "post", fake_post)
    monkeypatch.setattr(osm.time, "sleep", seen["pauses"].append)
    return seen


def test_fetch_identifies_the_project_without_any_personal_contact(monkeypatch):
    seen = stub_http(monkeypatch, [200])
    osm.fetch("query", SETTINGS)
    user_agent = seen["headers"][0]["User-Agent"]
    assert "Projet-Crocs-Expansion" in user_agent
    assert "github.com" in user_agent
    assert "@" not in user_agent


def test_fetch_waits_then_retries_after_a_server_refusal(monkeypatch):
    seen = stub_http(monkeypatch, [502, 429, 200])
    assert osm.fetch("query", SETTINGS)["elements"]
    assert seen["pauses"] == [WAIT_AFTER_REFUSAL, WAIT_AFTER_REFUSAL]


def test_fetch_gives_up_after_the_maximum_number_of_attempts(monkeypatch):
    seen = stub_http(monkeypatch, [502] * MAX_ATTEMPTS)
    with pytest.raises(RuntimeError, match="arrêt"):
        osm.fetch("query", SETTINGS)
    assert len(seen["headers"]) == MAX_ATTEMPTS


def test_fetch_does_not_retry_an_error_that_is_not_a_refusal(monkeypatch):
    seen = stub_http(monkeypatch, [400])
    with pytest.raises(osm.requests.HTTPError):
        osm.fetch("query", SETTINGS)
    assert len(seen["headers"]) == 1


def test_collected_tables_go_through_silver_and_gold(silver, tmp_path, monkeypatch):
    # Collect into a private bronze directory, from the generated list of cities.
    bronze_dir = tmp_path / "bronze"
    bronze_dir.mkdir()
    silver_dir = tmp_path / "silver"
    cities = pd.read_parquet(silver[0] / f"{osm.CITY_TABLE}.parquet")
    cities[["id_zone", "code_pays", "ville"]].to_csv(
        bronze_dir / f"{osm.CITY_TABLE}.csv", index=False, encoding="utf-8-sig"
    )
    monkeypatch.setattr(osm, "fetch", lambda query, settings: json.loads(json.dumps(answer())))
    monkeypatch.setattr(osm.time, "sleep", lambda seconds: None)
    collected = osm.collect(bronze_dir, only=["Berlin"])

    real = {name: b2s.REAL_TABLES[name] for name in (osm.OSM_CITIES_TABLE, osm.OSM_SHOPS_TABLE)}
    report = b2s.run(bronze_dir, silver_dir, tmp_path / "manual", real)
    assert set(report["statut"]) <= {b2s.STATUS_EXPECTED}  # only the optional name and brand

    # Gold: the simulated tables come from the shared silver layer, the real ones from here.
    for path in silver[0].glob("*.parquet"):
        (silver_dir / path.name).write_bytes(path.read_bytes())
    rows = build_gold.build(silver_dir, tmp_path / "warehouse.duckdb")
    assert rows[osm.OSM_CITIES_TABLE] == len(collected) == 1
    assert rows[osm.OSM_SHOPS_TABLE] == 3
