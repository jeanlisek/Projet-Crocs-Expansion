"""Collect the road distance from each logistics hub to each target city (OSRM).

Usage (from the repository root):
    python -m src.collect.osrm [--trajets ID_HUB:ID_ZONE ...] [--bronze DIR]

Origins: the 3 hubs of dim_hub_logistique. Each is located at the centre of its town,
geocoded once with Nominatim; the exact address of a hub is an assumption of the scenario.
Destinations: the target cities collected by src/collect/osm.py. Each is located at the
median point of its shoe shops, so no extra request is needed and the point sits in the
shopping centre of the city.

Usage policies (read on 2026-11-12):
- Nominatim (https://operations.osmfoundation.org/policies/nominatim/): at most 1 request
  per second, a single thread, an identifying User-Agent, results cached, no systematic
  queries.
- OSRM public server (https://routing.openstreetmap.de/about.html): at most 1 request per
  second, a valid User-Agent, no scraping, no heavy usage.
This script sends one request at a time, spaced out by the project delay, and never asks
again for a town or a route whose raw answer is already in data/bronze/.

Routes: OSRM. Data © OpenStreetMap contributors, ODbL.
"""

import argparse
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
DEFAULT_BRONZE_DIR = REPO_ROOT / "data" / "bronze"

USER_AGENT = "Projet-Crocs-Expansion/1.0 (+https://github.com/jeanlisek/Projet-Crocs-Expansion)"
SOURCE = (
    "Itinéraires : OSRM ({url}), données © les contributeurs d'OpenStreetMap, ODbL ; "
    "l'emplacement des hubs est une hypothèse du scénario (centre de la commune)"
)

HUB_TABLE = "dim_hub_logistique"
OSM_CITIES_TABLE = "osm_villes"
OSM_SHOPS_TABLE = "osm_magasins_chaussures"
DISTANCE_TABLE = "osrm_distances"
GEOCODE_FILE = "osrm_geocodage_{id_hub}_{day}.json"
ROUTE_FILE = "osrm_trajet_{id_hub}_{id_zone}_{day}.json"

# HTTP statuses after which the script waits before a new request (refusal or overload).
RETRY_STATUSES = (429, 502, 503, 504)
OSRM_OK = "Ok"
METRES_PER_KM = 1000
SECONDS_PER_HOUR = 3600

_last_request = {"at": None}


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["collecte"]


def get_json(url: str, params: dict, settings: dict):
    """One GET request, never closer than the project delay to the previous one."""
    osrm = settings["osrm"]
    for attempt in range(1, osrm["essais_max"] + 1):
        if _last_request["at"] is not None:
            elapsed = time.monotonic() - _last_request["at"]
            time.sleep(max(0.0, settings["delai_entre_requetes_s"] - elapsed))
        response = requests.get(
            url, params=params, headers={"User-Agent": USER_AGENT}, timeout=osrm["delai_reponse_s"]
        )
        _last_request["at"] = time.monotonic()
        if response.status_code not in RETRY_STATUSES:
            response.raise_for_status()
            return response.json()
        print(f"  HTTP {response.status_code}, essai {attempt} sur {osrm['essais_max']}")
        if attempt < osrm["essais_max"]:
            time.sleep(osrm["attente_apres_refus_s"])
    raise RuntimeError(f"{url} refuse la requête : arrêt, sans autre tentative")


def cached(bronze_dir: Path, pattern: str) -> Path | None:
    """Most recent raw answer matching the pattern, if any."""
    files = sorted(bronze_dir.glob(pattern))
    return files[-1] if files else None


def answer(bronze_dir: Path, name_template: str, fetch, **keys) -> tuple[object, str, bool]:
    """Raw answer from the cache, or fetched and saved; with its date and whether it was sent."""
    path = cached(bronze_dir, name_template.format(day="*", **keys))
    sent = path is None
    if sent:
        payload = fetch()
        path = bronze_dir / name_template.format(day=date.today().isoformat(), **keys)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, path.stem.rsplit("_", 1)[-1], sent


def hub_points(bronze_dir: Path, settings: dict) -> tuple[pd.DataFrame, int]:
    """Hubs with the coordinates of the centre of their town (Nominatim); requests sent."""
    hubs = pd.read_csv(bronze_dir / f"{HUB_TABLE}.csv", encoding="utf-8-sig")
    rows, requests_sent = [], 0
    for hub in hubs.itertuples():
        params = {
            "city": hub.ville,
            "countrycodes": hub.code_pays.lower(),
            "format": "jsonv2",
            "limit": 1,
        }
        results, _, sent = answer(
            bronze_dir,
            GEOCODE_FILE,
            lambda params=params: get_json(settings["nominatim"]["url"], params, settings),
            id_hub=hub.id_hub,
        )
        requests_sent += sent
        if len(results) != 1:
            raise ValueError(f"{hub.ville}: expected one geocoding result, found {len(results)}")
        place = results[0]
        rows.append(
            {
                "id_hub": hub.id_hub,
                "commune_hub": hub.ville,
                "nom_geocode": place["display_name"],
                "latitude": float(place["lat"]),
                "longitude": float(place["lon"]),
            }
        )
    return pd.DataFrame(rows), requests_sent


def city_points(bronze_dir: Path) -> pd.DataFrame:
    """Target cities located at the median point of their shoe shops (data of T16)."""
    shops = pd.read_csv(bronze_dir / f"{OSM_SHOPS_TABLE}.csv", encoding="utf-8-sig")
    cities = pd.read_csv(bronze_dir / f"{OSM_CITIES_TABLE}.csv", encoding="utf-8-sig")
    points = shops.groupby("id_zone")[["latitude", "longitude"]].median().reset_index()
    return cities[["id_zone", "ville"]].merge(points, on="id_zone", validate="one_to_one")


def route_row(hub, city, payload: dict, day: str, source: str) -> dict:
    if payload.get("code") != OSRM_OK or len(payload.get("routes", [])) != 1:
        raise ValueError(f"{hub.id_hub} -> {city.id_zone}: no single route in the answer")
    route, (start, end) = payload["routes"][0], payload["waypoints"]
    return {
        "id_hub": hub.id_hub,
        "id_zone": city.id_zone,
        "commune_hub": hub.commune_hub,
        "ville": city.ville,
        "latitude_hub": hub.latitude,
        "longitude_hub": hub.longitude,
        "latitude_ville": city.latitude,
        "longitude_ville": city.longitude,
        "distance_route_km": round(route["distance"] / METRES_PER_KM, 1),
        "duree_h": round(route["duration"] / SECONDS_PER_HOUR, 2),
        # Distance between each requested point and the road it was snapped to.
        "ecart_route_hub_m": round(start["distance"]),
        "ecart_route_ville_m": round(end["distance"]),
        "date_collecte": day,
        "source": source,
    }


def collect(bronze_dir: Path = DEFAULT_BRONZE_DIR, only: list[str] | None = None) -> pd.DataFrame:
    """Collect the routes (all hub x city pairs, or those listed as ID_HUB:ID_ZONE)."""
    settings = load_config()
    source = SOURCE.format(url=settings["osrm"]["url"])
    hubs, requests_sent = hub_points(bronze_dir, settings)
    cities = city_points(bronze_dir)
    pairs = [(hub, city) for hub in hubs.itertuples() for city in cities.itertuples()]
    if only:
        known = {f"{hub.id_hub}:{city.id_zone}" for hub, city in pairs}
        unknown = sorted(set(only) - known)
        if unknown:
            raise ValueError(f"not a hub x target city pair: {unknown}")
        pairs = [(hub, city) for hub, city in pairs if f"{hub.id_hub}:{city.id_zone}" in only]

    rows = []
    for hub, city in pairs:
        url = (
            f"{settings['osrm']['url']}/"
            f"{hub.longitude},{hub.latitude};{city.longitude},{city.latitude}"
        )
        payload, day, sent = answer(
            bronze_dir,
            ROUTE_FILE,
            lambda url=url: get_json(url, {"overview": "false"}, settings),
            id_hub=hub.id_hub,
            id_zone=city.id_zone,
        )
        requests_sent += sent
        rows.append(route_row(hub, city, payload, day, source))
        origin = "requête envoyée" if sent else "réponse déjà en cache"
        print(
            f"{hub.commune_hub:24s} -> {city.ville:12s} "
            f"{rows[-1]['distance_route_km']:>7.1f} km  {rows[-1]['duree_h']:>5.2f} h   {origin}"
        )

    distances = pd.DataFrame(rows)
    distances.to_csv(bronze_dir / f"{DISTANCE_TABLE}.csv", index=False, encoding="utf-8-sig")
    print(f"\n{requests_sent} requête(s) envoyée(s), {len(distances)} trajet(s)")
    return distances


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trajets", nargs="+", help="limit the run to these ID_HUB:ID_ZONE pairs")
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    args = parser.parse_args()
    collect(args.bronze, args.trajets)


if __name__ == "__main__":
    main()
