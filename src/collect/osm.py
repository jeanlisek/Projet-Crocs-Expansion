"""Collect the shoe shops of the target cities from OpenStreetMap, through the Overpass API.

Usage (from the repository root):
    python -m src.collect.osm [--villes NAME ...] [--bronze DIR]

For each city of dim_zone_chalandise in the target country, one query returns the
administrative boundary of the city and every `shop=shoes` element inside it. The raw
answer is saved, dated, in data/bronze/; a city that already has a raw answer is never
asked for again. Two CSV tables are then rebuilt from the raw answers: one row per city
(osm_villes) and one row per shop (osm_magasins_chaussures).

Usage policy of the public instance (Overpass documentation and OSM wiki, read on
2026-11-12): a one-off use stays under 10,000 queries and 1 GB a day, sends a User-Agent,
runs no script in parallel, caches the answers and pauses 30 s after an HTTP 429 or 406.
This script sends one query per city, one at a time, spaced out by the project delay.

Data © OpenStreetMap contributors, ODbL (https://www.openstreetmap.org/copyright).
"""

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
DEFAULT_BRONZE_DIR = REPO_ROOT / "data" / "bronze"

# Identifies the client, as the usage policy asks: project name and public repository.
USER_AGENT = "Projet-Crocs-Expansion/1.0 (+https://github.com/jeanlisek/Projet-Crocs-Expansion)"
SOURCE = "OpenStreetMap via l'API Overpass ({url}) ; © les contributeurs d'OpenStreetMap, ODbL"

CITY_TABLE = "dim_zone_chalandise"
OSM_CITIES_TABLE = "osm_villes"
OSM_SHOPS_TABLE = "osm_magasins_chaussures"
RAW_FILE = "osm_overpass_{id_zone}_{day}.json"

# Name of the city boundary in OpenStreetMap when it differs from dim_zone_chalandise.
OSM_NAMES = {"Frankfurt": "Frankfurt am Main"}
# Administrative levels of a German city: 4 (city-state), 6 (independent city) or 8 (municipality).
CITY_ADMIN_LEVELS = "^(4|6|8)$"
SHOP_TAG = "shoes"
# Official German municipality code (AGS, 8 digits), used to match other official sources.
MUNICIPALITY_CODE_TAG = "de:amtlicher_gemeindeschluessel"
# A year, standing alone, in the tags that describe the population figure.
YEAR_PATTERN = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
POPULATION_YEAR_TAGS = ("population:date", "source:population")

# HTTP statuses after which the script waits before a new request: 406, 429 and 504 are
# named by the usage policy; 502 and 503 are transient errors of an overloaded server.
RETRY_STATUSES = (406, 429, 502, 503, 504)

QUERY = """[out:json][timeout:{timeout}];
area["ISO3166-1"="{country}"]["admin_level"="2"]->.pays;
rel(area.pays)["boundary"="administrative"]["name"="{name}"]["admin_level"~"{levels}"]->.limite;
.limite out tags;
.limite map_to_area->.ville;
nwr(area.ville)["shop"="{shop}"];
out tags center;
"""


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["collecte"]


def target_cities(bronze_dir: Path, country: str) -> pd.DataFrame:
    """Cities of the target country: id_zone and ville, read from the bronze layer."""
    cities = pd.read_csv(bronze_dir / f"{CITY_TABLE}.csv", encoding="utf-8-sig")
    return cities.loc[cities["code_pays"] == country, ["id_zone", "ville"]]


def build_query(city: str, country: str, timeout: int) -> str:
    return QUERY.format(
        timeout=timeout,
        country=country,
        name=OSM_NAMES.get(city, city),
        levels=CITY_ADMIN_LEVELS,
        shop=SHOP_TAG,
    )


def cached_answer(bronze_dir: Path, id_zone: str) -> Path | None:
    """Most recent raw answer already saved for a city, if any."""
    files = sorted(bronze_dir.glob(RAW_FILE.format(id_zone=id_zone, day="*")))
    return files[-1] if files else None


def fetch(query: str, settings: dict) -> dict:
    """Send one query; wait and retry as the usage policy asks, then give up."""
    overpass = settings["overpass"]
    for attempt in range(1, overpass["essais_max"] + 1):
        response = requests.post(
            overpass["url"],
            data={"data": query},
            headers={"User-Agent": USER_AGENT},
            timeout=overpass["delai_reponse_s"] + settings["delai_entre_requetes_s"],
        )
        if response.status_code not in RETRY_STATUSES:
            response.raise_for_status()
            return response.json()
        print(f"  HTTP {response.status_code}, essai {attempt} sur {overpass['essais_max']}")
        if attempt < overpass["essais_max"]:
            time.sleep(overpass["attente_apres_refus_s"])
    raise RuntimeError("Overpass refuse la requête : arrêt, sans autre tentative")


def parse_answer(payload: dict) -> tuple[dict, list[dict]]:
    """Split a raw answer into the city boundary and the list of shops."""
    elements = payload["elements"]
    boundaries = [e for e in elements if e.get("tags", {}).get("boundary") == "administrative"]
    if len(boundaries) != 1:
        names = [(b["id"], b["tags"].get("admin_level")) for b in boundaries]
        raise ValueError(f"expected one city boundary, found {len(boundaries)}: {names}")
    shops = [e for e in elements if e.get("tags", {}).get("shop") == SHOP_TAG]
    return boundaries[0], shops


def population_year(tags: dict) -> tuple[int | None, str | None]:
    """Year of the OSM population figure and the tag it was read from.

    The year is only kept when the tag holds exactly one: nothing is guessed otherwise.
    """
    for tag in POPULATION_YEAR_TAGS:
        years = set(YEAR_PATTERN.findall(tags.get(tag, "")))
        if len(years) == 1:
            return int(years.pop()), tag
    return None, None


def city_row(city, boundary: dict, shops: list[dict], day: str, source: str) -> dict:
    tags = boundary["tags"]
    year, year_tag = population_year(tags)
    return {
        "id_zone": city.id_zone,
        "ville": city.ville,
        "osm_relation_id": boundary["id"],
        "nom_osm": tags.get("name"),
        "niveau_administratif": tags.get("admin_level"),
        "code_communal": tags.get(MUNICIPALITY_CODE_TAG),
        "population_osm": tags.get("population"),
        "annee_population_osm": year,
        "tag_annee_population_osm": year_tag,
        "source_population_osm": tags.get("source:population"),
        "nb_magasins_chaussures": len(shops),
        "nb_magasins_avec_enseigne": sum("brand" in shop["tags"] for shop in shops),
        "date_collecte": day,
        "source": source,
    }


def shop_rows(city, shops: list[dict], day: str, source: str) -> list[dict]:
    rows = []
    for shop in shops:
        position = shop.get("center", shop)  # nodes carry lat/lon, ways and relations a center
        rows.append(
            {
                "id_zone": city.id_zone,
                "osm_type": shop["type"],
                "osm_id": shop["id"],
                "nom": shop["tags"].get("name"),
                "enseigne": shop["tags"].get("brand"),
                "latitude": position.get("lat"),
                "longitude": position.get("lon"),
                "date_collecte": day,
                "source": source,
            }
        )
    return rows


def collect(bronze_dir: Path = DEFAULT_BRONZE_DIR, only: list[str] | None = None) -> pd.DataFrame:
    """Collect the cities (all, or those named in `only`); return the city table."""
    settings = load_config()
    source = SOURCE.format(url=settings["overpass"]["url"])
    cities = target_cities(bronze_dir, settings["pays_cible"])
    if only:
        unknown = sorted(set(only) - set(cities["ville"]))
        if unknown:
            raise ValueError(f"not a target city of {CITY_TABLE}: {unknown}")
        cities = cities[cities["ville"].isin(only)]

    city_table, shop_table, requests_sent = [], [], 0
    for city in cities.itertuples():
        raw_path = cached_answer(bronze_dir, city.id_zone)
        if raw_path is None:
            if requests_sent:
                time.sleep(settings["delai_entre_requetes_s"])
            query = build_query(
                city.ville, settings["pays_cible"], settings["overpass"]["delai_reponse_s"]
            )
            payload = fetch(query, settings)
            requests_sent += 1
            day = date.today().isoformat()
            raw_path = bronze_dir / RAW_FILE.format(id_zone=city.id_zone, day=day)
            raw_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            origin = "requête envoyée"
        else:
            payload = json.loads(raw_path.read_text(encoding="utf-8"))
            origin = "réponse déjà en cache"
        day = raw_path.stem.rsplit("_", 1)[-1]
        boundary, shops = parse_answer(payload)
        city_table.append(city_row(city, boundary, shops, day, source))
        shop_table.extend(shop_rows(city, shops, day, source))
        print(f"{city.ville:12s} {len(shops):>4d} magasins   {origin} ({raw_path.name})")

    cities_df = pd.DataFrame(city_table)
    cities_df.to_csv(bronze_dir / f"{OSM_CITIES_TABLE}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(shop_table).to_csv(
        bronze_dir / f"{OSM_SHOPS_TABLE}.csv", index=False, encoding="utf-8-sig"
    )
    print(
        f"\n{requests_sent} requête(s) envoyée(s) à Overpass, {len(cities_df)} ville(s) traitée(s)"
    )
    return cities_df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villes", nargs="+", help="limit the run to these cities")
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    args = parser.parse_args()
    collect(args.bronze, args.villes)


if __name__ == "__main__":
    main()
