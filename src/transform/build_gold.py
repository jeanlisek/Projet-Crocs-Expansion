"""Silver -> gold: load the Parquet tables into the DuckDB warehouse.

Usage (from the repository root):
    python -m src.transform.build_gold [--silver DIR] [--warehouse FILE]

The warehouse is rebuilt from scratch at each run. Every silver table becomes a gold
table with its primary key; the relationships of the constellation model (README,
section 3.2) are declared as foreign keys, so DuckDB itself rejects a duplicate or an
orphan key. Real tables are loaded next to the simulated ones, under their own name,
and are never merged into them.
"""

import argparse
from pathlib import Path

import duckdb

from src.transform.bronze_to_silver import (
    DEFAULT_SILVER_DIR,
    REAL_TABLES,
    REPO_ROOT,
    SIMULATED_TABLES,
    TableSpec,
)

DEFAULT_WAREHOUSE = REPO_ROOT / "data" / "gold" / "warehouse.duckdb"

# Constellation model of the README, section 3.2: (table, column, dimension).
# The column points to the primary key of the dimension, whatever its own name.
# dim_zone_chalandise -> dim_pays and dim_magasin -> dim_hub_logistique are the
# snowflaked branches.
RELATIONSHIPS = [
    ("fact_marche", "code_pays", "dim_pays"),
    ("fact_parts_de_marche", "code_pays", "dim_pays"),
    ("fact_fiscalite", "code_pays", "dim_pays"),
    ("fact_couts_exploitation", "code_pays", "dim_pays"),
    ("fact_prix_releves", "code_pays", "dim_pays"),
    ("fact_eligibilite_assortiment", "code_pays", "dim_pays"),
    ("fact_penetration_categories", "code_pays", "dim_pays"),
    ("fact_tendances_recherche", "code_pays", "dim_pays"),
    ("dim_zone_chalandise", "code_pays", "dim_pays"),
    ("fact_ventes_france", "id_date", "dim_temps"),
    ("fact_prix_releves", "id_date", "dim_temps"),
    ("fact_tendances_recherche", "id_date", "dim_temps"),
    ("fact_ventes_france", "id_produit", "dim_produit"),
    ("fact_eligibilite_assortiment", "id_produit", "dim_produit"),
    ("fact_ventes_france", "id_magasin", "dim_magasin"),
    ("fact_immobilier", "id_zone", "dim_zone_chalandise"),
    ("fact_logistique", "id_zone", "dim_zone_chalandise"),
    ("fact_presence_concurrents", "id_zone", "dim_zone_chalandise"),
    ("fact_logistique", "id_hub", "dim_hub_logistique"),
    ("dim_magasin", "id_hub_rattachement", "dim_hub_logistique"),
    ("fact_parts_de_marche", "id_concurrent", "dim_concurrent"),
    ("fact_presence_concurrents", "id_concurrent", "dim_concurrent"),
    ("fact_prix_releves", "id_concurrent", "dim_concurrent"),
]

# Relationships of the real tables, applied only when the table has been collected.
REAL_RELATIONSHIPS = [
    ("osm_villes", "id_zone", "dim_zone_chalandise"),
    ("osm_magasins_chaussures", "id_zone", "osm_villes"),
    ("destatis_population_villes", "id_zone", "dim_zone_chalandise"),
    ("osrm_distances", "id_hub", "dim_hub_logistique"),
    ("osrm_distances", "id_zone", "dim_zone_chalandise"),
    ("eurostat_pays", "code_pays", "dim_pays"),
]

# Silver only knows dates (no time of day): they are stored as DATE in the warehouse.
SILVER_DATE_TYPE = "TIMESTAMP"
GOLD_DATE_TYPE = "DATE"


def quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def dimension_key(specs: dict[str, TableSpec], dimension: str) -> str:
    """Primary key column of a dimension; a relationship needs it to be a single column."""
    key = specs[dimension].primary_key
    if len(key) != 1:
        raise ValueError(f"{dimension}: a dimension must have a single-column primary key")
    return key[0]


def load_order(names: list[str], relationships: list[tuple[str, str, str]]) -> list[str]:
    """Order the tables so that a dimension is created before the tables pointing to it."""
    parents = {
        name: {parent for child, _, parent in relationships if child == name} for name in names
    }
    ordered: list[str] = []
    while len(ordered) < len(names):
        ready = [name for name in names if name not in ordered and parents[name] <= set(ordered)]
        if not ready:
            raise ValueError("the relationships between tables are circular")
        ordered.extend(ready)
    return ordered


def create_table(
    con: duckdb.DuckDBPyConnection,
    name: str,
    spec: TableSpec,
    parquet_path: Path,
    foreign_keys: list[tuple[str, str, str]],
) -> int:
    """Create one gold table with its keys, fill it from Parquet; return its row count.

    `foreign_keys` lists (column, dimension, key column of the dimension).
    """
    source = f"read_parquet({literal(parquet_path)})"
    definitions = []
    for column, column_type, *_ in con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall():
        gold_type = GOLD_DATE_TYPE if column_type.startswith(SILVER_DATE_TYPE) else column_type
        definitions.append(f"{quote(column)} {gold_type}")
    key = ", ".join(quote(column) for column in spec.primary_key)
    definitions.append(f"PRIMARY KEY ({key})")
    for column, dimension, key_column in foreign_keys:
        definitions.append(
            f"FOREIGN KEY ({quote(column)}) REFERENCES {quote(dimension)} ({quote(key_column)})"
        )
    con.execute(f"CREATE TABLE {quote(name)} ({', '.join(definitions)})")
    con.execute(f"INSERT INTO {quote(name)} SELECT * FROM {source}")
    return con.execute(f"SELECT count(*) FROM {quote(name)}").fetchone()[0]


def build(
    silver_dir: Path = DEFAULT_SILVER_DIR,
    warehouse_path: Path = DEFAULT_WAREHOUSE,
    simulated: dict[str, TableSpec] = SIMULATED_TABLES,
    real: dict[str, TableSpec] = REAL_TABLES,
) -> dict[str, int]:
    """Rebuild the warehouse from the silver layer; return the row count of each table."""
    shared_names = sorted(set(simulated) & set(real))
    if shared_names:
        raise ValueError(f"real tables must not reuse a simulated table name: {shared_names}")
    for name in simulated:
        if not (silver_dir / f"{name}.parquet").exists():
            raise FileNotFoundError(f"{name}.parquet is missing in {silver_dir}: run `make silver`")
    # A real table is optional: it is loaded only when it reached the silver layer.
    collected = {
        name: spec for name, spec in real.items() if (silver_dir / f"{name}.parquet").exists()
    }
    for name in sorted(set(real) - set(collected)):
        print(f"{name:32s} absente : table réelle pas encore collectée")
    specs = {**simulated, **collected}

    relationships = RELATIONSHIPS + [
        relationship for relationship in REAL_RELATIONSHIPS if relationship[0] in collected
    ]
    for child, _, parent in relationships:
        unknown = [name for name in (child, parent) if name not in specs]
        if unknown:
            raise ValueError(f"relationship on a table that is not loaded: {unknown}")

    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    warehouse_path.unlink(missing_ok=True)
    rows = {}
    con = duckdb.connect(str(warehouse_path))
    try:
        for name in load_order(list(specs), relationships):
            path = silver_dir / f"{name}.parquet"
            foreign_keys = [
                (column, dimension, dimension_key(specs, dimension))
                for table, column, dimension in relationships
                if table == name
            ]
            rows[name] = create_table(con, name, specs[name], path, foreign_keys)
            origin = "réelle" if name in collected else "simulée"
            print(f"{name:32s} {rows[name]:>8,d} lignes   table {origin}")
    finally:
        con.close()
    print(
        f"\n{len(rows)} tables et {len(relationships)} relations dans : {warehouse_path.resolve()}"
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--silver", type=Path, default=DEFAULT_SILVER_DIR)
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_WAREHOUSE)
    args = parser.parse_args()
    build(args.silver, args.warehouse)


if __name__ == "__main__":
    main()
