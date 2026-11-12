"""Export the gold tables and views read by the dashboard as CSV files.

Usage (from the repository root):
    python -m src.transform.export_gold [--warehouse FILE] [--exports DIR]

One file per table or view, named after it, with the same column names. The files are
UTF-8 without BOM, comma-separated, with a header line, a dot as decimal separator and ISO
dates; an empty cell is a missing value. They are versioned: rows are sorted and lines end
with LF, so that the same warehouse gives the same bytes on every system.

An object of OPTIONAL that is not in the warehouse yet is skipped with a message, and its
previous export, if any, is left as it is. A missing object of REQUIRED stops the export.
"""

import argparse
import csv
from pathlib import Path

import duckdb

from src.transform.bronze_to_silver import REPO_ROOT
from src.transform.build_gold import DEFAULT_WAREHOUSE

DEFAULT_EXPORTS_DIR = REPO_ROOT / "data" / "gold" / "exports"

# Views and tables the dashboard reads today: all of them must be in the warehouse.
REQUIRED = (
    "kpi_summary",
    "densite_concurrentielle",
    "distance_hub",
    "dim_pays",
    "dim_zone_chalandise",
    "dim_concurrent",
    "dim_produit",
    "dim_temps",
    "fact_marche",
    "fact_parts_de_marche",
    "fact_immobilier",
    "fact_prix_releves",
    "sensibilite_payback",
    "eurostat_series",
    "crocs_produits",
)
# Delivered by later tasks (T8 business case and city scoring, T9 AI commentary).
OPTIONAL = ("business_case", "city_scoring", "ai_commentary")


def existing_objects(con: duckdb.DuckDBPyConnection) -> set[str]:
    """Names of the tables and views of the warehouse."""
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall()
    return {row[0] for row in rows}


def write_csv(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> int:
    """Write one table or view as a CSV file; return its number of rows."""
    # ORDER BY ALL: a view has no row order of its own, and the files are versioned.
    result = con.execute(f'SELECT * FROM "{name}" ORDER BY ALL')
    header = [column[0] for column in result.description]
    rows = result.fetchall()
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def export(
    warehouse_path: Path = DEFAULT_WAREHOUSE,
    exports_dir: Path = DEFAULT_EXPORTS_DIR,
    required: tuple[str, ...] = REQUIRED,
    optional: tuple[str, ...] = OPTIONAL,
) -> dict[str, int]:
    """Write every available object as <name>.csv; return the row count of each file."""
    if not warehouse_path.exists():
        raise FileNotFoundError(f"{warehouse_path} is missing: run `make gold` first")

    written = {}
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        # One thread: a parallel sum of floats may change its last digit from one run to
        # the next, which would show up as a difference in the versioned files.
        con.execute("SET threads = 1")
        available = existing_objects(con)
        missing = [name for name in required if name not in available]
        if missing:
            raise LookupError(f"missing from {warehouse_path}: {missing}; run `make kpi` first")

        exports_dir.mkdir(parents=True, exist_ok=True)
        for name in (*required, *optional):
            if name not in available:
                print(f"{name:32s} absent de l'entrepôt : non exporté")
                continue
            written[name] = write_csv(con, name, exports_dir / f"{name}.csv")
            print(f"{name:32s} {written[name]:>8,d} lignes   {name}.csv")
    finally:
        con.close()
    print(f"\n{len(written)} fichier(s) CSV écrit(s) dans : {exports_dir.resolve()}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--exports", type=Path, default=DEFAULT_EXPORTS_DIR)
    args = parser.parse_args()
    export(args.warehouse, args.exports)


if __name__ == "__main__":
    main()
