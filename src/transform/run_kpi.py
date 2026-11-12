"""Run the SQL files of sql/kpi/ on the DuckDB warehouse.

Usage (from the repository root):
    python -m src.transform.run_kpi [--warehouse FILE] [--sql-dir DIR]

Each file holds one view, written as CREATE OR REPLACE VIEW so that the target can be
run again. A view may read another view: a file whose dependencies do not exist yet is
retried after the others, so file names do not have to follow the dependency order.
An empty directory is not an error.
"""

import argparse
from pathlib import Path

import duckdb

from src.transform.bronze_to_silver import REPO_ROOT
from src.transform.build_gold import DEFAULT_WAREHOUSE

DEFAULT_SQL_DIR = REPO_ROOT / "sql" / "kpi"


def run(warehouse_path: Path = DEFAULT_WAREHOUSE, sql_dir: Path = DEFAULT_SQL_DIR) -> list[str]:
    """Execute every .sql file of the directory; return their names in execution order."""
    pending = sorted(sql_dir.glob("*.sql"))
    if not pending:
        print(f"aucun fichier .sql dans {sql_dir} : rien à exécuter")
        return []
    if not warehouse_path.exists():
        raise FileNotFoundError(f"{warehouse_path} is missing: run `make gold` first")

    executed = []
    con = duckdb.connect(str(warehouse_path))
    try:
        while pending:
            waiting = {}
            for path in pending:
                try:
                    con.execute(path.read_text(encoding="utf-8"))
                except duckdb.CatalogException as error:
                    # Probably a view defined in a file that has not run yet: retry later.
                    waiting[path] = error
                except duckdb.Error as error:
                    raise RuntimeError(f"{path.name}: {error}") from error
                else:
                    executed.append(path.name)
                    print(f"exécuté : {path.name}")
            if len(waiting) == len(pending):
                path, error = next(iter(waiting.items()))
                raise RuntimeError(f"{path.name}: {error}") from error
            pending = list(waiting)
    finally:
        con.close()
    return executed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument("--sql-dir", type=Path, default=DEFAULT_SQL_DIR)
    args = parser.parse_args()
    run(args.warehouse, args.sql_dir)


if __name__ == "__main__":
    main()
