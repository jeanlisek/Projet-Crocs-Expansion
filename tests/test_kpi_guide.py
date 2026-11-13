"""Tests of the KPI guide (data/gold/exports/kpi_guide.csv), on the generated dataset."""

import duckdb
import pytest

from src.transform import build_gold, kpi_guide, parametres_kpi, run_kpi
from tests.test_kpi_t7 import CROCS_CATALOGUE, CROCS_PRICES

# Same real tables as the kpi_summary test of T7: empty or a few rows, enough for every view.
REAL_TABLES = """
    CREATE TABLE osm_villes (id_zone VARCHAR, ville VARCHAR, nb_magasins_chaussures INTEGER,
        population_osm BIGINT, annee_population_osm INTEGER);
    CREATE TABLE destatis_population_villes (id_zone VARCHAR, population BIGINT,
        date_reference DATE);
    CREATE TABLE osrm_distances (id_hub VARCHAR, id_zone VARCHAR, commune_hub VARCHAR,
        ville VARCHAR, distance_route_km DOUBLE, duree_h DOUBLE);
    CREATE TABLE taxes_reference (code_pays VARCHAR, taux_tva_standard_pct DOUBLE,
        taux_tva_reduite_chaussures_enfant_pct DOUBLE, taux_impot_societes_pct DOUBLE,
        droit_douane_ue_chaussures_ch64_pct DOUBLE, est_simule BOOLEAN);
    INSERT INTO taxes_reference VALUES ('DE', 19.0, NULL, 30.06, 16.8, FALSE);
    CREATE TABLE eurostat_series (code_pays VARCHAR, indicateur VARCHAR, annee INTEGER,
        valeur DOUBLE, statut_eurostat VARCHAR, est_simule BOOLEAN);
    INSERT INTO eurostat_series VALUES
        ('DE', 'depenses_menages_chaussures_meur', 2022, 1000.0, NULL, FALSE),
        ('DE', 'depenses_menages_chaussures_meur', 2025, 1331.0, 'p', FALSE);
"""


@pytest.fixture(scope="module")
def guide(silver, tmp_path_factory):
    """The guide built on every view of the generated dataset, with the KPI names."""
    warehouse = tmp_path_factory.mktemp("gold") / "warehouse.duckdb"
    build_gold.build(silver[0], warehouse)
    con = duckdb.connect(str(warehouse))
    con.execute(REAL_TABLES + CROCS_PRICES + CROCS_CATALOGUE)
    con.close()
    parametres_kpi.write(warehouse, parametres_kpi.load())
    run_kpi.run(warehouse)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        names = {row[0] for row in con.execute("SELECT DISTINCT kpi FROM kpi_summary").fetchall()}
        return kpi_guide.build(con), names
    finally:
        con.close()


def test_one_row_per_kpi_of_the_summary(guide):
    rows, names = guide
    listed = [row["nom"] for row in rows]
    assert len(listed) == len(set(listed)) and set(listed) == names
    assert list(rows[0]) == kpi_guide.COLUMNS


def test_every_kpi_is_described_without_placeholder(guide):
    rows, _ = guide
    for row in rows:
        for column in kpi_guide.COLUMNS:
            if column != "seuil":
                assert row[column], (row["nom"], column)
        text = " ".join(row.values())
        assert "TODO" not in text and "kpi." not in text, row["nom"]


def test_texts_come_from_the_readme_and_the_view_headers(guide):
    rows, _ = guide
    by_name = {row["nom"]: row for row in rows}
    growth = by_name["Croissance du secteur (TCAM 2022-2025)"]
    assert (
        growth["formule"]
        == kpi_guide.readme_table("### 2.3 KPIs", "KPI")["Croissance du secteur"]["Formule"]
    )
    assert growth["seuil"].startswith("≥ 2 %") and "README 4.2" in growth["seuil"]
    price = by_name["Indice prix relatif (HT, base pays de référence = 100)"]
    assert price["unite"] == "indice (HT)"
    assert "REEL (DE)" in price["origine"]
    payback = by_name["Payback (scénario pessimiste) : Centre commercial"]
    assert "scénario : pessimiste" in payback["perimetre"]
    assert "format : Centre commercial" in payback["perimetre"]


def test_a_kpi_without_family_stops_the_guide():
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE kpi_summary AS SELECT 'KPI inconnu' AS kpi, 'Marché' AS axe, '%' AS unite,
            NULL AS seuil, 'FR' AS pays, 'SIMULE' AS origine_donnees;
        CREATE TABLE parametres_kpi AS SELECT * FROM (VALUES
            ('kpi.annee_reference', 2025.0), ('kpi.tcam_annee_debut', 2022.0),
            ('kpi.tcam_annee_fin', 2025.0), ('business_case_allemagne.horizon_annees', 10.0)
        ) AS t(parametre, valeur);
        CREATE TABLE fact_prix_releves (id_date INTEGER);
        """)
    with pytest.raises(LookupError, match="KPI inconnu"):
        kpi_guide.build(con)
