"""Collect country indicators from the Eurostat dissemination API (task T4).

Usage (from the repository root):
    python -m src.collect.eurostat [--bronze DIR]

One request per dataset, filtered on the countries of dim_pays and on the codes below; the
raw JSON-stat answer is saved, dated, in data/bronze/, and a dataset already saved is never
asked for again. Two tables are rebuilt from the raw answers: eurostat_pays, one row per
country and indicator with the latest year published since `annee_depuis`, and
eurostat_series, one row per country, indicator and year (for growth rates). When Eurostat
publishes no value for a country (the United Kingdom left the EU statistical system in
2020), the row is kept with an empty value and a TODO note: nothing is filled in.

Dataset codes: found in the Eurostat table of contents
(https://ec.europa.eu/eurostat/api/dissemination/catalogue/toc/txt), then checked on
2026-11-12 against the dimension labels the API returns. The script checks every filter
code again on each run and stops if one is not in the answer.

robots.txt of ec.europa.eu, read on 2026-11-12: /eurostat/api/ is allowed (only the former
/eurostat/SDMX/diss-web/rest/ API is not). The script sends an explicit User-Agent and waits
the project delay between two requests. Data: © European Union, Eurostat (reuse authorised,
source acknowledged).
"""

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "hypotheses.yaml"
DEFAULT_BRONZE_DIR = REPO_ROOT / "data" / "bronze"

USER_AGENT = "Projet-Crocs-Expansion/1.0 (+https://github.com/jeanlisek/Projet-Crocs-Expansion)"
SOURCE = "Eurostat, jeu {dataset} ({url}), mis à jour le {updated}, relevé du {day}"
TABLE = "eurostat_pays"
SERIES_TABLE = "eurostat_series"
RAW_FILE = "eurostat_{dataset}_{day}.json"
SIMULATED_COUNTRIES = "dim_pays"
# Eurostat writes the United Kingdom UK (and Greece EL); the project uses ISO codes.
EUROSTAT_GEO = {"GB": "UK"}
NO_VALUE_NOTE = "TODO : aucune valeur publiée par Eurostat depuis {year}"


@dataclass(frozen=True)
class Series:
    indicator: str  # column-like name, as in dim_pays when the series is compared with it
    dataset: str
    filters: dict  # dimension -> code, besides geo and time
    unit: str


SERIES = [
    # tps00001 "Population on 1 January": indic_de=JAN "Population on 1 January - total".
    Series("population", "tps00001", {"indic_de": "JAN"}, "personnes"),
    # tec00114 "GDP per capita in PPS": "Volume indices of real expenditure per capita
    # (in PPS_EU27_2020=100)", category GDP.
    Series(
        "pib_habitant_spa_ue100",
        "tec00114",
        {"indic_ppp": "VI_PPS_EU27_2020_HAB", "ppp_cat18": "GDP"},
        "indice UE27 = 100",
    ),
    # une_rt_a "Unemployment by sex and age - annual data": percentage of the labour force,
    # 15 to 74 years (the ILO definition used by Eurostat), both sexes.
    Series(
        "taux_chomage_pct",
        "une_rt_a",
        {"age": "Y15-74", "sex": "T", "unit": "PC_ACT"},
        "% de la population active",
    ),
    # prc_ppp_ind_1 "Purchasing power parities, price level indices... based on COICOP 2018":
    # price level index (EU27_2020=100) of household consumption (A01 "Actual individual
    # consumption") and of footwear (A010302 "Footwear").
    Series(
        "indice_niveau_prix_conso_ue100",
        "prc_ppp_ind_1",
        {"indic_ppp": "PLI_EU27_2020", "ppp_cat18": "A01"},
        "indice UE27 = 100",
    ),
    Series(
        "indice_niveau_prix_chaussures_ue100",
        "prc_ppp_ind_1",
        {"indic_ppp": "PLI_EU27_2020", "ppp_cat18": "A010302"},
        "indice UE27 = 100",
    ),
    # nama_10_cp18 "Household final consumption expenditure by purpose (COICOP 2018)":
    # CP032 "Footwear", at current prices and as a share of the total.
    Series(
        "depenses_menages_chaussures_meur",
        "nama_10_cp18",
        {"coicop18": "CP032", "unit": "CP_MEUR"},
        "millions d'euros courants",
    ),
    Series(
        "depenses_menages_chaussures_pct",
        "nama_10_cp18",
        {"coicop18": "CP032", "unit": "PC_TOT"},
        "% de la consommation des ménages",
    ),
    # sbs_ovw_act "Enterprises by detailed NACE Rev. 2 activity and special aggregates":
    # G4772 "Retail sale of footwear and leather goods in specialised stores" (NACE 47.72:
    # footwear AND leather goods, not footwear alone).
    Series(
        "commerce_chaussures_nb_entreprises",
        "sbs_ovw_act",
        {"nace_r2": "G4772", "indic_sbs": "ENT_NR"},
        "entreprises",
    ),
    Series(
        "commerce_chaussures_nb_personnes_occupees",
        "sbs_ovw_act",
        {"nace_r2": "G4772", "indic_sbs": "EMP_NR"},
        "personnes",
    ),
    Series(
        "commerce_chaussures_ca_meur",
        "sbs_ovw_act",
        {"nace_r2": "G4772", "indic_sbs": "NETTUR_MEUR"},
        "millions d'euros",
    ),
]

# dim_pays column compared with each Eurostat indicator, and the factor that puts the
# Eurostat value in the unit of dim_pays.
COMPARISONS = {
    "population": ("population_millions", 1e-6),
    "pib_habitant_spa_ue100": ("pib_habitant_spa_ue100", 1),
    "taux_chomage_pct": ("taux_chomage_pct", 1),
    "indice_niveau_prix_chaussures_ue100": ("indice_niveau_prix_chaussures_ue100", 1),
}


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)["collecte"]


def eurostat_geo(country: str) -> str:
    return EUROSTAT_GEO.get(country, country)


def dataset_filters(dataset: str) -> dict[str, list[str]]:
    """Every code asked for a dataset, per dimension (union of its series)."""
    filters: dict[str, list[str]] = {}
    for series in SERIES:
        if series.dataset == dataset:
            for dimension, code in series.filters.items():
                if code not in filters.setdefault(dimension, []):
                    filters[dimension].append(code)
    return filters


def query(dataset: str, countries: list[str], since: int) -> list[tuple[str, str]]:
    params = [("format", "JSON"), ("lang", "EN"), ("sinceTimePeriod", str(since))]
    params += [("geo", eurostat_geo(country)) for country in countries]
    for dimension, codes in dataset_filters(dataset).items():
        params += [(dimension, code) for code in codes]
    return params


def fetch(url: str, params: list[tuple[str, str]], timeout: float) -> dict:
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def values_by_key(payload: dict) -> dict[tuple, tuple[float, str | None]]:
    """JSON-stat 2.0 cube -> {(code of each dimension, in order): (value, status)}."""
    dimensions = payload["id"]
    sizes = payload["size"]
    codes = []
    for dimension in dimensions:
        index = payload["dimension"][dimension]["category"]["index"]
        ordered = sorted(index, key=index.get) if isinstance(index, dict) else list(index)
        codes.append(ordered)
    status = payload.get("status") or {}
    cube = {}
    for flat, value in payload.get("value", {}).items():
        position, key = int(flat), []
        for size, dimension_codes in zip(reversed(sizes), reversed(codes)):
            key.append(dimension_codes[position % size])
            position //= size
        cube[tuple(reversed(key))] = (value, status.get(flat))
    return cube


def check_codes(payload: dict, series: Series) -> str:
    """Stop if a filter code is not in the answer; return the Eurostat labels of the codes."""
    labels = []
    for dimension, code in series.filters.items():
        known = payload["dimension"].get(dimension, {}).get("category", {}).get("label", {})
        if code not in known:
            raise ValueError(f"{series.dataset}: code {dimension}={code} absent de la réponse")
        labels.append(known[code])
    return " ; ".join(labels)


def country_years(series: Series, raw: dict, country: str) -> dict[int, tuple]:
    """Every year Eurostat publishes for a series and a country: {year: (value, status)}."""
    payload = raw["payload"]
    cube = values_by_key(payload)
    dimensions = payload["id"]
    wanted = {**series.filters, "geo": eurostat_geo(country)}
    years = {}
    for key, (value, status) in cube.items():
        codes = dict(zip(dimensions, key))
        if value is not None and all(codes.get(dim) == code for dim, code in wanted.items()):
            years[int(codes["time"])] = (value, status)
    return years


def series_source(series: Series, raw: dict) -> str:
    return SOURCE.format(
        dataset=series.dataset,
        url=raw["url"],
        updated=raw["payload"].get("updated"),
        day=raw["day"],
    )


def series_filter(series: Series) -> str:
    return ";".join(f"{dim}={code}" for dim, code in series.filters.items())


def series_rows(series: Series, raw: dict, settings: dict) -> list[dict]:
    """One row per country: the latest year with a value, or an empty value and a TODO."""
    label = check_codes(raw["payload"], series)
    rows = []
    for country in settings["pays"]:
        years = country_years(series, raw, country)
        year = max(years) if years else None
        value, status = years[year] if years else (None, None)
        rows.append(
            {
                "code_pays": country,
                "indicateur": series.indicator,
                "libelle_eurostat": label,
                "jeu_donnees": series.dataset,
                "filtre": series_filter(series),
                "annee": year,
                "valeur": value,
                "unite": series.unit,
                "statut_eurostat": status,
                "note": None if years else NO_VALUE_NOTE.format(year=settings["annee_depuis"]),
                "date_collecte": raw["day"],
                "source": series_source(series, raw),
            }
        )
    return rows


def history_rows(series: Series, raw: dict, settings: dict) -> list[dict]:
    """One row per country and year published since `annee_depuis`: the time series that a
    growth rate needs (eurostat_pays keeps the latest year only). A year Eurostat does not
    publish has no row: nothing is filled in."""
    check_codes(raw["payload"], series)
    rows = []
    for country in settings["pays"]:
        for year, (value, status) in sorted(country_years(series, raw, country).items()):
            rows.append(
                {
                    "code_pays": country,
                    "indicateur": series.indicator,
                    "annee": year,
                    "valeur": value,
                    "unite": series.unit,
                    "statut_eurostat": status,
                    "jeu_donnees": series.dataset,
                    "filtre": series_filter(series),
                    "date_collecte": raw["day"],
                    "source": series_source(series, raw),
                }
            )
    return rows


def cached_answer(bronze_dir: Path, dataset: str) -> Path | None:
    files = sorted(bronze_dir.glob(RAW_FILE.format(dataset=dataset, day="*")))
    return files[-1] if files else None


def compare_with_simulated(table: pd.DataFrame, simulated: pd.DataFrame) -> pd.DataFrame:
    """Real value (in the unit of dim_pays) next to the simulated one, with the gap."""
    rows = []
    simulated = simulated.set_index("code_pays")
    for row in table.itertuples():
        if row.indicateur not in COMPARISONS or row.code_pays not in simulated.index:
            continue
        column, factor = COMPARISONS[row.indicateur]
        real = None if pd.isna(row.valeur) else round(row.valeur * factor, 2)
        fake = float(simulated.loc[row.code_pays, column])
        rows.append(
            {
                "code_pays": row.code_pays,
                "colonne_dim_pays": column,
                "simule": fake,
                "reel": real,
                "annee_reel": row.annee,
                "ecart": None if real is None else round(real - fake, 2),
                "ecart_pct": None if real is None else round(100 * (real - fake) / fake, 1),
            }
        )
    return pd.DataFrame(rows)


def collect(bronze_dir: Path = DEFAULT_BRONZE_DIR) -> pd.DataFrame:
    settings = load_config()
    eurostat = settings["eurostat"]
    raws, sent = {}, 0
    for dataset in dict.fromkeys(series.dataset for series in SERIES):
        path = cached_answer(bronze_dir, dataset)
        if path is None:
            if sent:
                time.sleep(settings["delai_entre_requetes_s"])
            url = eurostat["url"] + dataset
            params = query(dataset, eurostat["pays"], eurostat["annee_depuis"])
            payload = fetch(url, params, eurostat["delai_reponse_s"])
            sent += 1
            day = date.today().isoformat()
            full_url = requests.Request("GET", url, params=params).prepare().url
            raw = {"dataset": dataset, "url": full_url, "day": day, "payload": payload}
            path = bronze_dir / RAW_FILE.format(dataset=dataset, day=day)
            path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            origin = "requête envoyée"
        else:
            origin = "réponse déjà en cache"
        raws[dataset] = json.loads(path.read_text(encoding="utf-8"))
        print(f"{dataset:16s} {origin} ({path.name})")

    rows = []
    for series in SERIES:
        rows.extend(series_rows(series, raws[series.dataset], eurostat))
    table = pd.DataFrame(rows)
    table["annee"] = table["annee"].astype("Int64")
    table.to_csv(bronze_dir / f"{TABLE}.csv", index=False, encoding="utf-8-sig")
    history = pd.DataFrame(
        [row for series in SERIES for row in history_rows(series, raws[series.dataset], eurostat)]
    )
    history.to_csv(bronze_dir / f"{SERIES_TABLE}.csv", index=False, encoding="utf-8-sig")
    missing = table[table["valeur"].isna()]
    print(
        f"\n{sent} requête(s) envoyée(s) à Eurostat, {len(table)} ligne(s) dans {TABLE}.csv,"
        f" {len(history)} dans {SERIES_TABLE}.csv"
    )
    for row in missing.itertuples():
        print(f"  TODO {row.code_pays} {row.indicateur} : aucune valeur publiée")
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bronze", type=Path, default=DEFAULT_BRONZE_DIR)
    args = parser.parse_args()
    table = collect(args.bronze)
    simulated = pd.read_csv(
        args.bronze / f"{SIMULATED_COUNTRIES}.csv", encoding="utf-8-sig", dtype={"code_pays": str}
    )
    print("\nComparaison avec dim_pays simulé :")
    print(compare_with_simulated(table, simulated).to_string(index=False))


if __name__ == "__main__":
    main()
