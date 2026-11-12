"""Tests of the OSRM collector. No test reaches the network: the HTTP layer is replaced."""

import pandas as pd
import pytest

from src.collect import osrm

SETTINGS = osrm.load_config()
DELAY = SETTINGS["delai_entre_requetes_s"]
WAIT_AFTER_REFUSAL = SETTINGS["osrm"]["attente_apres_refus_s"]
MAX_ATTEMPTS = SETTINGS["osrm"]["essais_max"]


def route_answer(distance_m=519015.1, duration_s=20246.5):
    return {
        "code": "Ok",
        "routes": [{"distance": distance_m, "duration": duration_s}],
        "waypoints": [{"distance": 24.4}, {"distance": 69.6}],
    }


@pytest.fixture
def bronze(tmp_path):
    """Two hubs, and two cities whose shoe shops were collected."""
    hubs = pd.DataFrame(
        {"id_hub": ["H01", "H02"], "ville": ["Hubville", "Hubstadt"], "code_pays": ["FR", "NL"]}
    )
    hubs.to_csv(tmp_path / f"{osrm.HUB_TABLE}.csv", index=False, encoding="utf-8-sig")
    cities = pd.DataFrame({"id_zone": ["Z001", "Z002"], "ville": ["A", "B"]})
    cities.to_csv(tmp_path / f"{osrm.OSM_CITIES_TABLE}.csv", index=False, encoding="utf-8-sig")
    shops = pd.DataFrame(
        {
            "id_zone": ["Z001", "Z001", "Z001", "Z002"],
            "latitude": [50.0, 50.2, 59.0, 48.0],  # 59.0 is far away: the median ignores it
            "longitude": [8.0, 8.2, 8.4, 11.0],
        }
    )
    shops.to_csv(tmp_path / f"{osrm.OSM_SHOPS_TABLE}.csv", index=False, encoding="utf-8-sig")
    return tmp_path


@pytest.fixture
def network(monkeypatch):
    """Replace get_json: one place per geocoding request, one route per routing request."""
    calls = []

    def fake_get_json(url, params, settings):
        calls.append((url, params))
        if url == settings["nominatim"]["url"]:
            return [{"display_name": f"{params['city']}, somewhere", "lat": "48.5", "lon": "2.5"}]
        return route_answer()

    monkeypatch.setattr(osrm, "get_json", fake_get_json)
    return calls


def test_city_is_located_at_the_median_point_of_its_shops(bronze):
    points = osrm.city_points(bronze).set_index("id_zone")
    assert points.loc["Z001", ["latitude", "longitude"]].tolist() == [50.2, 8.2]
    assert points.loc["Z002", ["latitude", "longitude"]].tolist() == [48.0, 11.0]


def test_collect_geocodes_each_hub_and_routes_every_hub_city_pair(bronze, network):
    distances = osrm.collect(bronze)
    geocoding = [call for call in network if call[0] == SETTINGS["nominatim"]["url"]]
    routing = [call for call in network if call[0] != SETTINGS["nominatim"]["url"]]
    assert [params["city"] for _, params in geocoding] == ["Hubville", "Hubstadt"]
    assert [params["countrycodes"] for _, params in geocoding] == ["fr", "nl"]
    assert len(routing) == 4  # 2 hubs x 2 cities
    # OSRM takes longitude first: hub (2.5, 48.5) then city Z001 (8.2, 50.2).
    assert routing[0][0].endswith("/2.5,48.5;8.2,50.2")
    assert distances[["id_hub", "id_zone"]].values.tolist() == [
        ["H01", "Z001"],
        ["H01", "Z002"],
        ["H02", "Z001"],
        ["H02", "Z002"],
    ]
    row = distances.iloc[0]
    assert row["distance_route_km"] == 519.0  # 519 015.1 m
    assert row["duree_h"] == 5.62  # 20 246.5 s
    assert (row["ecart_route_hub_m"], row["ecart_route_ville_m"]) == (24, 70)
    assert "hypothèse du scénario" in row["source"]


def test_collect_never_asks_again_for_what_is_already_in_cache(bronze, network):
    osrm.collect(bronze)
    requests_first_run = len(network)
    osrm.collect(bronze)
    assert len(network) == requests_first_run == 6  # 2 towns + 4 routes, sent once


def test_collect_can_be_limited_to_some_pairs(bronze, network):
    distances = osrm.collect(bronze, only=["H02:Z001"])
    assert distances[["id_hub", "id_zone"]].values.tolist() == [["H02", "Z001"]]
    with pytest.raises(ValueError, match="H09:Z001"):
        osrm.collect(bronze, only=["H09:Z001"])


@pytest.mark.parametrize("results", [[], [{"lat": "1", "lon": "1"}, {"lat": "2", "lon": "2"}]])
def test_town_without_exactly_one_geocoding_result_stops_the_run(bronze, monkeypatch, results):
    monkeypatch.setattr(osrm, "get_json", lambda url, params, settings: results)
    with pytest.raises(ValueError, match="expected one geocoding result"):
        osrm.collect(bronze)


def test_answer_without_a_route_is_rejected(bronze, network, monkeypatch):
    def no_route(url, params, settings):
        if url == settings["nominatim"]["url"]:
            return [{"display_name": "x", "lat": "48.5", "lon": "2.5"}]
        return {"code": "NoRoute", "routes": []}

    monkeypatch.setattr(osrm, "get_json", no_route)
    with pytest.raises(ValueError, match="no single route"):
        osrm.collect(bronze)


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise osrm.requests.HTTPError(str(self.status_code))

    def json(self):
        return route_answer()


@pytest.fixture
def http(monkeypatch):
    """Replace requests.get and the clock; the clock only moves when the script sleeps."""
    seen = {"headers": [], "pauses": [], "statuses": [], "now": 1000.0}

    def fake_get(url, params, headers, timeout):
        seen["headers"].append(headers)
        return FakeResponse(seen["statuses"].pop(0))

    def fake_sleep(seconds):
        seen["pauses"].append(seconds)
        seen["now"] += seconds

    monkeypatch.setattr(osrm.requests, "get", fake_get)
    monkeypatch.setattr(osrm.time, "sleep", fake_sleep)
    monkeypatch.setattr(osrm.time, "monotonic", lambda: seen["now"])
    monkeypatch.setitem(osrm._last_request, "at", None)
    return seen


def test_requests_are_spaced_out_by_the_project_delay(http):
    http["statuses"] = [200, 200]
    osrm.get_json("https://example.org", {}, SETTINGS)
    osrm.get_json("https://example.org", {}, SETTINGS)
    assert http["pauses"] == [
        DELAY
    ]  # nothing before the first request, the delay before the second


def test_request_identifies_the_project_without_any_personal_contact(http):
    http["statuses"] = [200]
    osrm.get_json("https://example.org", {}, SETTINGS)
    user_agent = http["headers"][0]["User-Agent"]
    assert "Projet-Crocs-Expansion" in user_agent
    assert "github.com" in user_agent
    assert "@" not in user_agent


def test_request_waits_then_retries_after_a_server_refusal(http):
    http["statuses"] = [429, 200]
    assert osrm.get_json("https://example.org", {}, SETTINGS)["code"] == "Ok"
    assert WAIT_AFTER_REFUSAL in http["pauses"]
    assert len(http["headers"]) == 2


def test_request_gives_up_after_the_maximum_number_of_attempts(http):
    http["statuses"] = [503] * MAX_ATTEMPTS
    with pytest.raises(RuntimeError, match="arrêt"):
        osrm.get_json("https://example.org", {}, SETTINGS)
    assert len(http["headers"]) == MAX_ATTEMPTS
