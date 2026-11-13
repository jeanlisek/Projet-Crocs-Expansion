# Project orchestration: `make all` rebuilds everything from scratch.
# Later tasks (collection, silver, gold, KPIs, AI, exports) add their target to `all`.

# Use the local virtualenv when it exists, otherwise the interpreter on the PATH (CI).
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

BRONZE_DIR := data/bronze
MANUAL_DIR := data/manual
SILVER_DIR := data/silver
WAREHOUSE := data/gold/warehouse.duckdb
SQL_KPI_DIR := sql/kpi
EXPORTS_DIR := data/gold/exports
AI_COMMENTARY := data/gold/ai_commentary.csv
CODE_DIRS := src tests

.PHONY: all install simulate collect silver gold kpi exports ai slides format lint test

all: simulate silver gold kpi exports

install:
	$(PYTHON) -m pip install -r requirements.txt

# Deterministic (fixed seed): rewrites the simulated CSV files in the bronze layer.
simulate:
	$(PYTHON) src/simulate/generate_data.py $(BRONZE_DIR)

# Collects the real data from open services (network needed, not part of `all`). Answers
# are cached in the bronze layer: what was already collected is never asked for again.
collect:
	$(PYTHON) -m src.collect.osm --bronze $(BRONZE_DIR)
	$(PYTHON) -m src.collect.destatis --bronze $(BRONZE_DIR)
	$(PYTHON) -m src.collect.osrm --bronze $(BRONZE_DIR)
	$(PYTHON) -m src.collect.scrape_crocs --bronze $(BRONZE_DIR)
	$(PYTHON) -m src.collect.eurostat --bronze $(BRONZE_DIR)

# Types and checks the bronze and manual tables, writes them as Parquet with the check report.
silver:
	$(PYTHON) src/transform/bronze_to_silver.py --bronze $(BRONZE_DIR) --manual $(MANUAL_DIR) --silver $(SILVER_DIR)

# Rebuilds the DuckDB warehouse from the silver tables, with primary and foreign keys.
gold:
	$(PYTHON) -m src.transform.build_gold --silver $(SILVER_DIR) --warehouse $(WAREHOUSE)

# Creates the KPI views: runs every sql/kpi/*.sql file on the warehouse (none is not an error).
kpi:
	$(PYTHON) -m src.transform.parametres_kpi --warehouse $(WAREHOUSE)
	$(PYTHON) -m src.transform.run_kpi --warehouse $(WAREHOUSE) --sql-dir $(SQL_KPI_DIR)

# Writes the tables and views read by the dashboard as CSV files (UTF-8, versioned). The
# views of later tasks (business case, city scoring, AI commentary) are skipped until they exist.
# data/gold/ai_commentary.csv (T9) is copied as it is when it exists.
exports:
	$(PYTHON) -m src.transform.export_gold --warehouse $(WAREHOUSE) --exports $(EXPORTS_DIR) --ai-commentary $(AI_COMMENTARY)
	$(PYTHON) -m src.transform.kpi_guide --warehouse $(WAREHOUSE) --out $(EXPORTS_DIR)/kpi_guide.csv

# T9: generates the AI commentary with the language model, then rewrites the exports. Needs
# the key in .env and the network: like `collect`, it is not part of `all`. Run it after `all`.
ai:
	$(PYTHON) -m src.ai.commentary --warehouse $(WAREHOUSE) --out $(AI_COMMENTARY)
	$(PYTHON) -m src.transform.export_gold --warehouse $(WAREHOUSE) --exports $(EXPORTS_DIR) --ai-commentary $(AI_COMMENTARY)

# T13: the slides of the oral, every figure read in the exports and in config/hypotheses.yaml.
# Writes slides/*.pptx, then the PDF and the PNG previews when LibreOffice is installed.
# Not part of `all`.
slides:
	$(PYTHON) slides/build_slides.py

format:
	$(PYTHON) -m black $(CODE_DIRS)

# Same checks as the CI. Line length and exclusions live in pyproject.toml and .flake8.
lint:
	$(PYTHON) -m black --check $(CODE_DIRS)
	$(PYTHON) -m flake8 $(CODE_DIRS)

test:
	$(PYTHON) -m pytest -q
