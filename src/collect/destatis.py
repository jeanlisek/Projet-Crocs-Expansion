"""Extract the official population of the target cities from the Destatis workbook.

Usage (from the repository root):
    python -m src.collect.destatis [--bronze DIR]

Source: Statistisches Bundesamt (Destatis), Gemeindeverzeichnis, table "Städte nach
Fläche, Bevölkerung und Bevölkerungsdichte". The workbook is kept as downloaded in
data/bronze/ and versioned: this script makes no network call.

A city is found by its official municipality code (AGS), read from OpenStreetMap by
src/collect/osm.py, never by its name. The reference date is read from the title of the
sheet. A city whose code is missing from the workbook, or present twice, stops the script.
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

import openpyxl
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
DEFAULT_BRONZE_DIR = REPO_ROOT / "data" / "bronze"

OSM_CITIES_TABLE = "osm_villes"
POPULATION_TABLE = "destatis_population_villes"
SOURCE = "Statistisches Bundesamt (Destatis), Gemeindeverzeichnis : {title} ({url})"

# Layout of the workbook: one sheet of cities, its title, then one row of column headers.
SHEET = "Städte"
TITLE_ROW, HEADER_ROW = 1, 2
KEY_HEADER = "Amtlicher Regionalschlüssel"
NAME_HEADER = "Stadt"
POPULATION_HEADER = "insgesamt"
REFERENCE_DATE = re.compile(r"\d{2}\.\d{2}\.\d{4}")
REFERENCE_DATE_FORMAT = "%d.%m.%Y"
# The regional key (ARS, 12 digits) holds the municipality code (AGS, 8 digits): the first
# 5 digits (state, district) and the last 3 (municipality), around the 4 digits of the
# municipal association.
ARS_LENGTH = 12
AGS_HEAD, AGS_TAIL = slice(0, 5), slice(9, 12)


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["collecte"]["destatis"]


def municipality_code(regional_key: str) -> str:
    """Official municipality code (AGS) held in a regional key (ARS)."""
    return regional_key[AGS_HEAD] + regional_key[AGS_TAIL]


def read_workbook(path: Path) -> tuple[str, str, pd.DataFrame]:
    """Title of the sheet, its reference date (ISO) and one row per city."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(workbook[SHEET].iter_rows(values_only=True))
    workbook.close()

    title = str(rows[TITLE_ROW - 1][0]).strip()
    dates = set(REFERENCE_DATE.findall(title))
    if len(dates) != 1:
        raise ValueError(f"expected one reference date in the sheet title, found: {title!r}")
    reference_date = datetime.strptime(dates.pop(), REFERENCE_DATE_FORMAT).date().isoformat()

    headers = [str(cell).strip() if cell is not None else "" for cell in rows[HEADER_ROW - 1]]

    def column(marker: str, exact: bool = False) -> int:
        matches = [
            index
            for index, header in enumerate(headers)
            if (header == marker if exact else marker in header)
        ]
        if len(matches) != 1:
            raise ValueError(f"expected one column for {marker!r}, found {len(matches)}")
        return matches[0]

    key, name, population = (
        column(KEY_HEADER),
        column(NAME_HEADER, exact=True),
        column(POPULATION_HEADER),
    )
    cities = [
        {
            "cle_regionale": str(row[key]).strip(),
            "nom_destatis": str(row[name]).strip(),
            "population": row[population],
        }
        for row in rows[HEADER_ROW:]
        if row[key] is not None and len(str(row[key]).strip()) == ARS_LENGTH
    ]
    return title, reference_date, pd.DataFrame(cities)


def extract(bronze_dir: Path = DEFAULT_BRONZE_DIR) -> pd.DataFrame:
    """Write the population table of the target cities; return it."""
    settings = load_config()
    title, reference_date, workbook_cities = read_workbook(bronze_dir / settings["fichier"])
    workbook_cities["code_communal"] = workbook_cities["cle_regionale"].map(municipality_code)

    # Codes are text: a leading zero is part of the code (Hamburg is 02000000).
    targets = pd.read_csv(bronze_dir / f"{OSM_CITIES_TABLE}.csv", encoding="utf-8-sig", dtype=str)
    rows = []
    for city in targets.itertuples():
        found = workbook_cities[workbook_cities["code_communal"] == city.code_communal]
        if len(found) != 1:
            raise ValueError(
                f"{city.ville}: expected one row for code {city.code_communal}, found {len(found)}"
            )
        match = found.iloc[0]
        rows.append(
            {
                "id_zone": city.id_zone,
                "ville": city.ville,
                "code_communal": city.code_communal,
                "cle_regionale": match["cle_regionale"],
                "nom_destatis": match["nom_destatis"],
                "population": int(match["population"]),
                "date_reference": reference_date,
                "source_url": settings["page_url"],
                "date_consultation": settings["date_consultation"],
                "source": SOURCE.format(title=title, url=settings["page_url"]),
            }
        )
        print(
            f"{city.ville:12s} {rows[-1]['population']:>10,d} habitants   {match['nom_destatis']}"
        )

    population = pd.DataFrame(rows)
    population.to_csv(bronze_dir / f"{POPULATION_TABLE}.csv", index=False, encoding="utf-8-sig")
    print(f"\n{len(population)} ville(s), population au {reference_date} ({settings['fichier']})")
    return population


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    args = parser.parse_args()
    extract(args.bronze)


if __name__ == "__main__":
    main()
