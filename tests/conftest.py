"""Fixtures shared by the test modules.

The dataset is rebuilt in a temporary directory by running the generator, exactly as
`make simulate` does for data/bronze/. The tests therefore run on a fresh clone and in
the CI, where data/bronze/ is not versioned, and never write into data/.
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.transform import bronze_to_silver

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "src" / "simulate" / "generate_data.py"


@pytest.fixture(scope="session")
def bronze_dir(tmp_path_factory):
    """Run the generator once per test session and return its output directory."""
    out_dir = tmp_path_factory.mktemp("bronze")
    subprocess.run(
        [sys.executable, str(GENERATOR), str(out_dir)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return out_dir


@pytest.fixture(scope="session")
def tables(bronze_dir):
    """Every generated CSV file, loaded as a DataFrame and indexed by table name."""
    return {
        path.stem: pd.read_csv(path, encoding="utf-8-sig")
        for path in sorted(bronze_dir.glob("*.csv"))
    }


@pytest.fixture(scope="session")
def silver(bronze_dir, tmp_path_factory):
    """Run bronze -> silver once on the generated dataset: (silver directory, check report)."""
    silver_dir = tmp_path_factory.mktemp("silver")
    # Empty manual directory, like the temporary bronze one: this fixture covers the
    # generated dataset alone. Without it, `run` reads the repository's own data/manual/,
    # whose files are versioned, and every test comparing the silver layer with the
    # generated tables breaks as soon as a manual table exists (T18). The manual table has
    # its own tests in test_taxes_reference.py.
    manual_dir = tmp_path_factory.mktemp("manual")
    report = bronze_to_silver.run(bronze_dir, silver_dir, manual_dir)
    return silver_dir, report
