"""Tests of the KPI views of T7 (sql/kpi/), one per KPI, on tiny datasets computed by hand.

Each test builds a small warehouse, runs only the SQL files it needs and compares the
result with the values worked out in the comments. The last test runs every view on the
generated dataset and checks the kpi_summary contract (docs/equipe/REGLES_COMMUNES.md).
"""

import math
from pathlib import Path

import duckdb
import pytest

from src.transform import build_gold, parametres_kpi, run_kpi

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "kpi"

# Same shape as the parametres_kpi table written by `make kpi`.
PARAMETERS = """
    CREATE TABLE parametres_kpi AS SELECT * FROM (VALUES
        ('kpi.annee_reference', 2025.0),
        ('kpi.tcam_annee_debut', 2022.0),
        ('kpi.tcam_annee_fin', 2025.0),
        ('go_no_go.tcam_segment_min_pct', 2.0),
        ('go_no_go.indice_prix_min', 95.0),
        ('go_no_go.indice_prix_max', 110.0),
        ('go_no_go.ecart_marge_vs_france_max_pts', 5.0),
        ('go_no_go.cout_occupation_max_pct_ca', 15.0),
        ('go_no_go.payback_pessimiste_max_mois', 36.0),
        ('go_no_go.catalogue_eligible_min_pct', 80.0)
    ) AS t(parametre, valeur);
"""

COUNTRIES = """
    CREATE TABLE dim_pays AS SELECT * FROM (VALUES
        ('FR', TRUE), ('DE', FALSE), ('ES', FALSE)
    ) AS t(code_pays, est_pays_reference);
"""

TAX = """
    CREATE TABLE fact_fiscalite AS SELECT * FROM (VALUES
        ('FR', 20.0, 20.0, 25.0, 0.0, 0.07, TRUE),
        ('DE', 19.0, 19.0, 29.9, 0.0, 0.0, TRUE)
    ) AS t(code_pays, taux_tva_standard_pct, taux_tva_chaussures_enfant_pct,
           taux_impot_societes_pct, droit_import_marchandise_origine_asie_via_fr_pct,
           eco_contribution_par_paire_eur, est_simule);
"""

# Two SKUs in both countries, one only in DE. P2 is a kids' product.
PRICES = """
    CREATE TABLE dim_produit AS SELECT * FROM (VALUES
        ('P1', 'Adulte', 30.0, 10.0, 2.0),
        ('P2', 'Enfant', 20.0, 8.0, 1.0),
        ('P3', 'Adulte', 10.0, 5.0, 1.0)
    ) AS t(id_produit, cible, cout_debarque_eur, cout_fob_eur, cout_fret_unitaire_eur);
    CREATE TABLE fact_prix_releves AS SELECT * FROM (VALUES
        ('FR', 'crocs.fr', 'P1', 120.0, FALSE, TRUE),
        ('FR', 'crocs.fr', 'P2', 60.0, FALSE, TRUE),
        ('DE', 'crocs.de', 'P1', 119.0, FALSE, TRUE),
        ('DE', 'crocs.de', 'P1', 50.0, TRUE, TRUE),
        ('DE', 'Zalando', 'P1', 80.0, FALSE, TRUE),
        ('DE', 'crocs.de', 'P2', 65.45, FALSE, TRUE),
        ('DE', 'crocs.de', 'P3', 40.0, FALSE, TRUE)
    ) AS t(code_pays, enseigne, id_produit, prix_affiche_eur, en_promotion, est_simule);
"""

# Z001, Z002 in DE; Z003 in ES is an island, Z004 in ES is not.
ZONES = """
    CREATE TABLE dim_zone_chalandise AS SELECT * FROM (VALUES
        ('Z001', 'DE', 'A', 0.5, 40, FALSE, TRUE),
        ('Z002', 'DE', 'B', 0.3, 20, FALSE, TRUE),
        ('Z003', 'ES', 'C', 0.2, 10, TRUE, TRUE),
        ('Z004', 'ES', 'D', 0.2, 30, FALSE, TRUE)
    ) AS t(id_zone, code_pays, ville, population_ville_millions, nb_points_vente_concurrents,
           zone_insulaire, est_simule);
"""


def build(tmp_path, setup_sql):
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute(PARAMETERS + setup_sql)
    con.close()
    return path


def run_views(tmp_path, warehouse, views, query):
    """Copy only the given views into a fresh directory, run them, return the query rows."""
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    for view in views:
        (sql_dir / f"{view}.sql").write_text((SQL_DIR / f"{view}.sql").read_text(encoding="utf-8"))
    run_kpi.run(warehouse, sql_dir)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def test_parameters_come_from_the_go_no_go_and_kpi_sections():
    parameters = dict(parametres_kpi.load().itertuples(index=False))
    assert parameters["go_no_go.indice_prix_min"] == 95
    assert parameters["go_no_go.payback_pessimiste_max_mois"] == 36
    assert parameters["kpi.annee_reference"] == 2025


def test_sector_growth_is_the_cagr_of_observed_years(tmp_path):
    warehouse = build(
        tmp_path,
        """
        CREATE TABLE fact_marche AS SELECT * FROM (VALUES
            ('DE', 2022, 'Casual moulé & sandales', 100.0, FALSE, TRUE),
            ('DE', 2025, 'Casual moulé & sandales', 133.1, FALSE, TRUE),
            ('DE', 2025, 'Chaussures (total)', 999.0, FALSE, TRUE),
            ('DE', 2026, 'Casual moulé & sandales', 500.0, TRUE, TRUE)
        ) AS t(code_pays, annee, segment, taille_marche_meur, est_projection, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_croissance_secteur"],
        "SELECT code_pays, tcam_pct, origine_donnees FROM kpi_croissance_secteur",
    )
    # (133.1 / 100) ^ (1/3) - 1 = 10 %
    assert rows == [("DE", 10.0, "SIMULE")]


def test_market_share_is_recomputed_from_the_reference_year_sales(tmp_path):
    warehouse = build(
        tmp_path,
        """
        CREATE TABLE dim_concurrent AS SELECT * FROM (VALUES
            ('C00', 'Crocs'), ('C01', 'Birkenstock'))
            AS t(id_concurrent, nom_concurrent);
        CREATE TABLE fact_parts_de_marche AS SELECT * FROM (VALUES
            ('DE', 2025, 'C00', 99.0, 30.0, TRUE),
            ('DE', 2025, 'C01', 1.0, 90.0, TRUE),
            ('DE', 2024, 'C00', 50.0, 1000.0, TRUE)
        ) AS t(code_pays, annee, id_concurrent, part_marche_valeur_pct, ca_estime_meur, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_part_de_marche"],
        "SELECT id_concurrent, part_marche_pct FROM kpi_part_de_marche ORDER BY 1",
    )
    # 30 / 120 and 90 / 120: the stored percentages (99, 1) are not reused, 2024 is ignored
    assert rows == [("C00", 25.0), ("C01", 75.0)]


def test_price_index_compares_net_prices_on_the_shared_basket(tmp_path):
    warehouse = build(tmp_path, COUNTRIES + TAX + PRICES)
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_prix_crocs_ht", "kpi_indice_prix"],
        "SELECT code_pays, nb_sku_panier, indice_prix FROM kpi_indice_prix",
    )
    # P1: 119/1.19 = 100 vs 120/1.20 = 100 -> 1.0 (promotion and Zalando ignored)
    # P2: 65.45/1.19 = 55 vs 60/1.20 = 50 -> 1.1 ; P3 is not sold in FR -> out of the basket
    assert rows == [("DE", 2, 105.0)]


def test_post_tax_margin_uses_sums_and_the_same_basket_as_the_reference(tmp_path):
    warehouse = build(
        tmp_path,
        COUNTRIES + TAX + PRICES + ZONES + """
        CREATE TABLE fact_logistique AS SELECT * FROM (VALUES
            ('H1', 'Z001', 1.0), ('H2', 'Z001', 5.0), ('H1', 'Z002', 3.0), ('H1', 'Z003', 100.0)
        ) AS t(id_hub, id_zone, cout_transport_unitaire_eur);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_prix_crocs_ht", "kpi_marge_post_taxe"],
        "SELECT code_pays, nb_sku_panier, transport_unitaire_eur, marge_post_taxe_pct, "
        "marge_reference_meme_panier_pct, ecart_vs_reference_pts "
        "FROM kpi_marge_post_taxe ORDER BY 1",
    )
    # DE transport: nearest hub 1.0 (Z001) and 3.0 (Z002) -> 2.0
    # DE: (100 - 30 - 2) + (55 - 20 - 2) = 101 over 155 = 65.16 %
    # FR: (100 - 30) + (50 - 20) = 100 over 150 = 66.67 % ; gap = -1.51 pt
    assert rows == [
        ("DE", 2, 2.0, 65.16, 66.67, -1.51),
        ("FR", 2, 0.0, 66.67, 66.67, 0.0),
    ]


def test_competitive_density_prefers_the_real_measure(tmp_path):
    warehouse = build(
        tmp_path,
        ZONES + """
        CREATE TABLE densite_concurrentielle AS SELECT * FROM (VALUES
            ('Z001', 50, 500000), ('Z002', 30, 300000)
        ) AS t(id_zone, nb_magasins_chaussures, population_destatis);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_densite_concurrentielle_pays"],
        "SELECT code_pays, origine_donnees, densite_pour_100k_hab, est_retenue "
        "FROM kpi_densite_concurrentielle_pays ORDER BY 1, 2",
    )
    # DE real: 80 / 800 000 -> 10 ; DE simulated: 60 / 800 000 -> 7.5 ; ES: 40 / 400 000 -> 10
    assert rows == [
        ("DE", "REEL", 10.0, True),
        ("DE", "SIMULE", 7.5, False),
        ("ES", "SIMULE", 10.0, True),
    ]


def test_hub_distance_averages_the_nearest_hub_and_skips_islands(tmp_path):
    warehouse = build(
        tmp_path,
        ZONES + """
        CREATE TABLE distance_hub AS SELECT * FROM (VALUES ('Z001', 200.0), ('Z002', 400.0))
            AS t(id_zone, distance_reelle_km);
        CREATE TABLE fact_logistique AS SELECT * FROM (VALUES
            ('H1', 'Z001', 210), ('H2', 'Z001', 500), ('H1', 'Z002', 390),
            ('H1', 'Z003', 50), ('H1', 'Z004', 100)
        ) AS t(id_hub, id_zone, distance_route_km);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_distance_hub_pays"],
        "SELECT code_pays, origine_donnees, nb_villes, distance_moyenne_km, est_retenue "
        "FROM kpi_distance_hub_pays ORDER BY 1, 2",
    )
    # DE real: (200 + 400) / 2 ; DE simulated: (210 + 390) / 2 ; ES: the island Z003 is left out
    assert rows == [
        ("DE", "REEL", 2, 300.0, True),
        ("DE", "SIMULE", 2, 300.0, False),
        ("ES", "SIMULE", 1, 100.0, True),
    ]


def test_cost_per_square_metre_adds_rent_and_service_charges(tmp_path):
    warehouse = build(
        tmp_path,
        ZONES + """
        CREATE TABLE fact_immobilier AS SELECT * FROM (VALUES
            ('Z001', 2025, 'Centre commercial', 300, 45, TRUE),
            ('Z001', 2024, 'Centre commercial', 280, 40, TRUE)
        ) AS t(id_zone, annee, type_emplacement, loyer_m2_an_eur, charges_m2_an_eur, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_cout_m2"],
        "SELECT code_pays, type_emplacement, cout_m2_an_eur FROM kpi_cout_m2",
    )
    assert rows == [("DE", "Centre commercial", 345)]


def test_taxes_give_one_row_per_tax(tmp_path):
    warehouse = build(tmp_path, TAX)
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_taxes"],
        "SELECT taxe, valeur, unite FROM kpi_taxes WHERE code_pays = 'DE' ORDER BY 1",
    )
    assert len(rows) == 5
    assert ("TVA standard", 19.0, "%") in rows
    assert ("Éco-contribution", 0.0, "€/paire") in rows


def test_category_penetration_keeps_the_reference_year(tmp_path):
    warehouse = build(
        tmp_path,
        """
        CREATE TABLE fact_penetration_categories AS SELECT * FROM (VALUES
            ('DE', 2025, 'Sabots', 12.5, 1000, TRUE),
            ('DE', 2024, 'Sabots', 10.0, 1000, TRUE)
        ) AS t(code_pays, annee, categorie, taux_penetration_pct, taille_echantillon, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_penetration_categories"],
        "SELECT code_pays, categorie, taux_penetration_pct FROM kpi_penetration_categories",
    )
    assert rows == [("DE", "Sabots", 12.5)]


def test_eligible_catalogue_is_counted_against_the_whole_catalogue(tmp_path):
    warehouse = build(
        tmp_path,
        """
        CREATE TABLE dim_produit AS SELECT * FROM (VALUES ('P1'), ('P2'), ('P3'), ('P4'))
            AS t(id_produit);
        CREATE TABLE fact_eligibilite_assortiment AS SELECT * FROM (VALUES
            ('DE', 'P1', TRUE, TRUE), ('DE', 'P2', TRUE, TRUE), ('DE', 'P3', TRUE, TRUE),
            ('DE', 'P4', FALSE, TRUE)
        ) AS t(code_pays, id_produit, eligible, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["kpi_catalogue_eligible"],
        "SELECT code_pays, nb_sku_eligibles, catalogue_eligible_pct FROM kpi_catalogue_eligible",
    )
    assert rows == [("DE", 3, 75.0)]


# Two stores open the whole of 2025 (M001, M004), one closed in 2025, one opened in 2025,
# and the web shop: only M001 and M004 count.
FRENCH_STORES = """
    CREATE TABLE dim_temps AS SELECT * FROM (VALUES (202403, 2024), (202503, 2025), (202506, 2025))
        AS t(id_date, annee);
    CREATE TABLE fact_couts_exploitation AS SELECT * FROM (VALUES ('FR', 40000.0, 50.0))
        AS t(code_pays, cout_complet_annuel_etp_eur, cout_energie_m2_an_eur);
    CREATE TABLE dim_magasin AS SELECT * FROM (VALUES
        ('M001', 'FR', 'Centre commercial', 'Magasin physique', 100, 2020, NULL, 75000, 4.0,
         220000, TRUE),
        ('M002', 'FR', 'Centre commercial', 'Magasin physique', 100, 2020, DATE '2025-03-31',
         75000, 4.0,
         220000, TRUE),
        ('M003', 'FR', 'Centre commercial', 'Magasin physique', 100, 2025, NULL, 75000, 4.0,
         220000, TRUE),
        ('M004', 'FR', 'Centre-ville', 'Magasin physique', 80, 2019, NULL, 88000, 3.0,
         170000, TRUE),
        ('WEB', 'FR', 'E-commerce', 'Digital', 0, 2012, NULL, 0, 14.0, 0, TRUE)
    ) AS t(id_magasin, code_pays, type_emplacement, canal, surface_vente_m2, annee_ouverture,
           date_fermeture, loyer_annuel_eur, nb_etp, capex_ouverture_eur, est_simule);
    CREATE TABLE fact_ventes_france AS SELECT * FROM (VALUES
        (202503, 'M001', 200000.0, 140000.0, TRUE), (202506, 'M001', 300000.0, 210000.0, TRUE),
        (202403, 'M001', 999999.0, 1.0, TRUE),
        (202503, 'M002', 50000.0, 35000.0, TRUE), (202506, 'M003', 50000.0, 35000.0, TRUE),
        (202503, 'M004', 400000.0, 280000.0, TRUE), (202503, 'WEB', 900000.0, 600000.0, TRUE)
    ) AS t(id_date, id_magasin, ca_net_ht_eur, marge_brute_eur, est_simule);
"""
# M001: CA 500 000, margin 350 000, fixed costs 75 000 + 4 x 40 000 + 100 x 50 = 240 000
# M004: CA 400 000, margin 280 000, fixed costs 88 000 + 3 x 40 000 + 80 x 50 = 212 000
FRENCH_VIEWS = ["magasins_france_reference", "kpi_cout_occupation", "kpi_point_mort", "kpi_payback"]


def test_occupancy_cost_is_rent_over_sales_of_full_year_stores(tmp_path):
    warehouse = build(tmp_path, FRENCH_STORES)
    rows = run_views(
        tmp_path,
        warehouse,
        FRENCH_VIEWS,
        "SELECT type_emplacement, nb_magasins, cout_occupation_pct FROM kpi_cout_occupation "
        "ORDER BY 1",
    )
    # 75 000 / 500 000 ; 88 000 / 400 000 ; 163 000 / 900 000
    assert rows == [
        ("Centre commercial", 1, 15.0),
        ("Centre-ville", 1, 22.0),
        ("Tous formats", 2, 18.11),
    ]


def test_break_even_is_fixed_costs_over_the_margin_rate(tmp_path):
    warehouse = build(tmp_path, FRENCH_STORES)
    rows = run_views(
        tmp_path,
        warehouse,
        FRENCH_VIEWS,
        "SELECT type_emplacement, point_mort_ca_ht_eur FROM kpi_point_mort ORDER BY 1",
    )
    # 240 000 / 0.7 ; 212 000 / 0.7 ; (452 000 / 2) / (630 000 / 900 000)
    assert rows == [
        ("Centre commercial", 342857.0),
        ("Centre-ville", 302857.0),
        ("Tous formats", 322857.0),
    ]


def test_payback_is_capex_over_annual_result_in_months(tmp_path):
    warehouse = build(tmp_path, FRENCH_STORES)
    rows = run_views(
        tmp_path,
        warehouse,
        FRENCH_VIEWS,
        "SELECT type_emplacement, payback_mois FROM kpi_payback ORDER BY 1",
    )
    # 220 000 x 12 / 110 000 ; 170 000 x 12 / 68 000 ; 390 000 x 12 / 178 000
    assert rows == [("Centre commercial", 24.0), ("Centre-ville", 30.0), ("Tous formats", 26.3)]


@pytest.fixture(scope="module")
def summary(silver, tmp_path_factory):
    """Every view on the generated dataset. Real tables absent: the simulated ones are used."""
    silver_dir, _ = silver
    warehouse = tmp_path_factory.mktemp("gold") / "warehouse.duckdb"
    build_gold.build(silver_dir, warehouse)
    con = duckdb.connect(str(warehouse))
    con.execute("""
        CREATE TABLE osm_villes (id_zone VARCHAR, ville VARCHAR, nb_magasins_chaussures INTEGER,
            population_osm BIGINT, annee_population_osm INTEGER);
        CREATE TABLE destatis_population_villes (id_zone VARCHAR, population BIGINT,
            date_reference DATE);
        CREATE TABLE osrm_distances (id_hub VARCHAR, id_zone VARCHAR, commune_hub VARCHAR,
            ville VARCHAR, distance_route_km DOUBLE, duree_h DOUBLE);
        """)
    con.close()
    parametres_kpi.write(warehouse, parametres_kpi.load())
    run_kpi.run(warehouse)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        frame = con.execute("SELECT * FROM kpi_summary").df()
        countries = {row[0] for row in con.execute("SELECT code_pays FROM dim_pays").fetchall()}
    finally:
        con.close()
    return frame, countries


def test_summary_follows_the_contract(summary):
    frame, countries = summary
    assert list(frame.columns) == [
        "kpi",
        "axe",
        "pays",
        "valeur",
        "unite",
        "seuil",
        "statut_go",
        "statut_epistemique",
        "origine_donnees",
    ]
    assert set(frame["axe"]) == {
        "Marché",
        "Prix",
        "Réseau",
        "Logistique",
        "Assortiment",
        "Rentabilité",
    }
    assert set(frame["pays"]) == countries
    assert set(frame["statut_go"]) <= {"GO", "NO-GO", "INFO"}
    assert set(frame["statut_epistemique"]) <= {"FAIT", "CALCUL", "HYPOTHÈSE", "CONVENTION"}
    assert set(frame["origine_donnees"]) <= {"REEL", "SIMULE", "MIXTE"}
    assert frame["valeur"].map(math.isfinite).all()
    # a GO / NO-GO verdict always shows the threshold it was judged against
    judged = frame[frame["statut_go"] != "INFO"]
    assert not judged.empty and judged["seuil"].notna().all()


def test_summary_has_no_duplicate_kpi_per_country(summary):
    frame, _ = summary
    assert not frame.duplicated(["kpi", "pays"]).any()
