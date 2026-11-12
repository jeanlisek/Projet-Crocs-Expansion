"""Write the numeric KPI parameters of config/hypotheses.yaml into the warehouse.

Usage (from the repository root):
    python -m src.transform.parametres_kpi [--warehouse FILE] [--config FILE]

The SQL views of sql/kpi/ read their thresholds (section go_no_go) and periods (section
kpi) from the table parametres_kpi, one row per parameter, so that no number is written
twice. Keys are flattened with a dot: go_no_go.indice_prix_min, kpi.annee_reference...
"""

import argparse
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from src.transform.bronze_to_silver import CONFIG_PATH
from src.transform.build_gold import DEFAULT_WAREHOUSE

TABLE = "parametres_kpi"
SECTIONS = ("go_no_go", "kpi")


def load(config_path: Path = CONFIG_PATH) -> pd.DataFrame:
    """Return the numeric parameters of the KPI sections: columns parametre, valeur."""
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    rows = [
        (f"{section}.{key}", float(value))
        for section in SECTIONS
        for key, value in config[section].items()
    ]
    return pd.DataFrame(rows, columns=["parametre", "valeur"])


def write(warehouse_path: Path, parameters: pd.DataFrame) -> None:
    """(Re)create the parameter table in the warehouse."""
    con = duckdb.connect(str(warehouse_path))
    try:
        con.register("parametres", parameters)
        con.execute(f"CREATE OR REPLACE TABLE {TABLE} AS SELECT * FROM parametres")
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
    print(f"{TABLE} : {len(parameters)} paramètres écrits dans {args.warehouse}")


if __name__ == "__main__":
    main()
