"""Write the KPI parameters of config/hypotheses.yaml into the warehouse.

Usage (from the repository root):
    python -m src.transform.parametres_kpi [--warehouse FILE] [--config FILE]

The SQL views of sql/kpi/ read their thresholds and hypotheses from two tables, so that no
number is written twice:
- parametres_kpi: numeric values (thresholds, periods, scenarios, cost rates...);
- parametres_kpi_texte: text values (formats kept, location type of each format...).
Nested keys are flattened with a dot and list items are numbered from 1:
go_no_go.indice_prix_min, business_case_allemagne.scenarios.central.montee_en_charge.1...
Empty values (null) are left out.
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from src.transform.bronze_to_silver import CONFIG_PATH
from src.transform.build_gold import DEFAULT_WAREHOUSE

TABLE = "parametres_kpi"
TEXT_TABLE = "parametres_kpi_texte"
SECTIONS = ("go_no_go", "kpi", "business_case_allemagne", "city_scoring")


def flatten(value, prefix: str):
    """Yield (dotted key, leaf value) for every leaf of a nested YAML value."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from flatten(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for position, child in enumerate(value, start=1):
            yield from flatten(child, f"{prefix}.{position}")
    elif value is not None:
        yield prefix, value


def load(config_path: Path = CONFIG_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (numeric parameters, text parameters), each with columns parametre, valeur."""
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    leaves = [leaf for section in SECTIONS for leaf in flatten(config[section], section)]
    numbers = [
        (key, float(value))
        for key, value in leaves
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    texts = [(key, value) for key, value in leaves if isinstance(value, str)]
    columns = ["parametre", "valeur"]
    return pd.DataFrame(numbers, columns=columns), pd.DataFrame(texts, columns=columns)


def write(warehouse_path: Path, parameters: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """(Re)create both parameter tables in the warehouse."""
    numbers, texts = parameters
    con = duckdb.connect(str(warehouse_path))
    try:
        con.register("nombres", numbers)
        con.register("textes", texts)
        con.execute(f"CREATE OR REPLACE TABLE {TABLE} AS SELECT * FROM nombres")
        con.execute(
            f"CREATE OR REPLACE TABLE {TEXT_TABLE} AS "
            "SELECT parametre, CAST(valeur AS VARCHAR) AS valeur FROM textes"
        )
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    if not args.warehouse.exists():
        raise FileNotFoundError(f"{args.warehouse} is missing: run `make gold` first")
    parameters = load(args.config)
    write(args.warehouse, parameters)
    print(
        f"{TABLE} : {len(parameters[0])} paramètres, {TEXT_TABLE} : {len(parameters[1])} "
        f"paramètres écrits dans {args.warehouse}"
    )


if __name__ == "__main__":
    main()
