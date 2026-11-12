# Project orchestration: `make all` rebuilds everything from scratch.
# Later tasks (collection, silver, gold, KPIs, AI, exports) add their target to `all`.

# Use the local virtualenv when it exists, otherwise the interpreter on the PATH (CI).
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

BRONZE_DIR := data/bronze
CODE_DIRS := src tests

.PHONY: all install simulate format lint test

all: simulate

install:
	$(PYTHON) -m pip install -r requirements.txt

# Deterministic (fixed seed): rewrites the simulated CSV files in the bronze layer.
simulate:
	$(PYTHON) src/simulate/generate_data.py $(BRONZE_DIR)

format:
	$(PYTHON) -m black $(CODE_DIRS)

# Same checks as the CI. Line length and exclusions live in pyproject.toml and .flake8.
lint:
	$(PYTHON) -m black --check $(CODE_DIRS)
	$(PYTHON) -m flake8 $(CODE_DIRS)

test:
	$(PYTHON) -m pytest -q
