"""Tests of the German business case and city scoring views (T8), computed by hand."""

from pathlib import Path

import duckdb

from src.transform import parametres_kpi, run_kpi

SQL_DIR = Path(__file__).resolve().parents[1] / "sql" / "kpi"
BC = "business_case_allemagne"

TEXT_PARAMETERS = f"""
    CREATE TABLE parametres_kpi_texte AS SELECT * FROM (VALUES
        ('{BC}.formats_retenus.1', 'Centre commercial'),
        ('{BC}.emplacement_immobilier.Centre commercial', 'Centre commercial')
    ) AS t(parametre, valeur);
"""


def build(tmp_path, setup_sql):
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    con.execute(setup_sql)
    con.close()
    return path


def run_views(tmp_path, warehouse, views, query):
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    for view in views:
        (sql_dir / f"{view}.sql").write_text(
            (SQL_DIR / f"{view}.sql").read_text(encoding="utf-8"), encoding="utf-8"
        )
    run_kpi.run(warehouse, sql_dir)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


def test_nested_hypotheses_are_flattened_into_numbers_and_texts():
    numbers, texts = parametres_kpi.load()
    numbers = dict(numbers.itertuples(index=False))
    texts = dict(texts.itertuples(index=False))
    assert numbers[f"{BC}.scenarios.central.montee_en_charge.1"] == 0.7
    assert numbers["city_scoring.poids.potentiel"] == 40
    assert texts[f"{BC}.formats_retenus.1"] == "Centre commercial"
    assert texts[f"{BC}.emplacement_immobilier.Centre-ville"] == "Centre-ville (secondaire)"


def test_business_case_inputs_come_from_the_french_network_and_german_costs(tmp_path):
    warehouse = build(
        tmp_path,
        TEXT_PARAMETERS + f"""
        CREATE TABLE parametres_kpi AS
        SELECT parametre, CAST(valeur AS DOUBLE) AS valeur FROM (VALUES
            ('{BC}.scenarios.central.ca_m2_vs_france_meme_format', 0.9),
            ('{BC}.scenarios.central.montee_en_charge.1', 0.7),
            ('{BC}.scenarios.central.montee_en_charge.2', 0.9),
            ('{BC}.scenarios.central.montee_en_charge.3', 1.0),
            ('{BC}.couts_additionnels_pct_ca.demarque', 1.0),
            ('{BC}.couts_additionnels_pct_ca.frais_siege', 4.0),
            ('{BC}.investissement.part_fixe_eur', 45000.0),
            ('{BC}.duree_amortissement_capex_ans', 7.0),
            ('{BC}.horizon_annees', 10.0)
        ) AS t(parametre, valeur);
        CREATE TABLE magasins_france_reference AS SELECT * FROM (VALUES
            ('Centre commercial', 100, 4.0, 600000.0, 420000.0),
            ('Centre commercial', 140, 6.0, 600000.0, 420000.0),
            ('Centre-ville', 90, 4.0, 700000.0, 490000.0)
        ) AS t(type_emplacement, surface_vente_m2, nb_etp, ca_ht_eur, marge_brute_eur);
        CREATE TABLE kpi_cout_m2 AS SELECT * FROM (VALUES
            ('DE', 'Centre commercial', 300, 40), ('DE', 'Centre commercial', 500, 60),
            ('FR', 'Centre commercial', 900, 90)
        ) AS t(code_pays, type_emplacement, loyer_m2_an_eur, charges_m2_an_eur);
        CREATE TABLE kpi_marge_post_taxe AS SELECT * FROM (VALUES ('DE', -2.0))
            AS t(code_pays, ecart_vs_reference_pts);
        CREATE TABLE fact_couts_exploitation AS SELECT * FROM (VALUES
            ('DE', 38000.0, 55.0, 1650.0, 55000.0, TRUE)
        ) AS t(code_pays, cout_complet_annuel_etp_eur, cout_energie_m2_an_eur,
               cout_amenagement_m2_eur, budget_marketing_lancement_eur, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["business_case_hypotheses"],
        "SELECT scenario, format, surface_m2, nb_etp, ca_m2_eur, round(taux_marge, 4), "
        "round(taux_couts_variables, 4), loyer_m2_an_eur, charges_m2_an_eur, montee_an1 "
        "FROM business_case_hypotheses",
    )
    # surface (100 + 140) / 2 ; ETP (4 + 6) / 2 ; CA/m² 1 200 000 / 240 x 0.9 ;
    # marge 840 000 / 1 200 000 - 2 pts ; coûts variables 1 + 4 % ; loyers des villes DE seulement
    assert rows == [
        ("central", "Centre commercial", 120.0, 5.0, 4500.0, 0.68, 0.05, 400.0, 50.0, 0.7)
    ]


# A store type worked out by hand. Central: cruising sales 100 m² x 5 000 = 500 000.
HYPOTHESES = """
    CREATE TABLE business_case_hypotheses AS SELECT * FROM (VALUES
        ('DE', 'central', 'CC', 100.0, 4.0, 5000.0, 0.70, 0.10, 300.0, 50.0, 40000.0, 50.0, 1500.0,
         50000.0, 50000.0, 5.0, 5, 0.5, 0.8, 1.0, 'SIMULE', 5000.0, 1.0),
        ('DE', 'pessimiste', 'CC', 100.0, 4.0, 2000.0, 0.70, 0.10, 300.0, 50.0, 40000.0, 50.0,
         1500.0, 50000.0, 50000.0, 5.0, 5, 0.5, 0.8, 1.0, 'SIMULE', 5000.0, 0.4)
    ) AS t(code_pays, scenario, format, surface_m2, nb_etp, ca_m2_eur, taux_marge,
           taux_couts_variables,
           loyer_m2_an_eur, charges_m2_an_eur, cout_complet_annuel_etp_eur, cout_energie_m2_an_eur,
           cout_amenagement_m2_eur, budget_marketing_lancement_eur, part_fixe_eur,
           duree_amortissement_ans, horizon_annees, montee_an1, montee_an2, montee_an3,
           origine_donnees, ca_m2_france_eur, ratio_ca_m2_vs_france);
"""


def test_yearly_income_statement_follows_the_ramp_up(tmp_path):
    warehouse = build(tmp_path, HYPOTHESES)
    rows = run_views(
        tmp_path,
        warehouse,
        ["business_case_annuel"],
        "SELECT annee, ca_ht_eur, ebitda_eur, amortissement_eur, tresorerie_cumulee_eur "
        "FROM business_case_annuel WHERE scenario = 'central' ORDER BY annee",
    )
    # fixed costs: rent 35 000 + staff 160 000 + energy 5 000 = 200 000 ; margin net of variable
    # costs = 60 % of sales ; investment 150 000 + 50 000 + 50 000 = 250 000, i.e. 50 000 a year
    assert rows == [
        (1, 250000.0, -50000.0, 50000.0, -300000.0),
        (2, 400000.0, 40000.0, 50000.0, -260000.0),
        (3, 500000.0, 100000.0, 50000.0, -160000.0),
        (4, 500000.0, 100000.0, 50000.0, -60000.0),
        (5, 500000.0, 100000.0, 50000.0, 40000.0),
    ]


def test_business_case_gives_payback_break_even_and_occupancy_cost(tmp_path):
    warehouse = build(tmp_path, HYPOTHESES)
    rows = run_views(
        tmp_path,
        warehouse,
        ["business_case_annuel", "business_case"],
        "SELECT scenario, ca_ht_croisiere_eur, ebitda_croisiere_eur, resultat_croisiere_eur, "
        "cout_occupation_pct, point_mort_ca_ht_eur, payback_mois "
        "FROM business_case ORDER BY scenario",
    )
    # payback: 4 years + 60 000 / 100 000 of the 5th year = 48 + 7.2 months
    # break-even: (35 000 + 160 000 + 5 000 + 50 000) / 0.6 ; occupancy: 35 000 / 500 000
    # pessimistic: 200 000 x 0.6 never covers 200 000 of fixed costs -> no payback
    assert rows == [
        ("central", 500000.0, 100000.0, 50000.0, 7.0, 416667.0, 55.2),
        ("pessimiste", 200000.0, -80000.0, -130000.0, 17.5, 416667.0, None),
    ]


def test_city_scoring_weights_criteria_scaled_from_0_to_100(tmp_path):
    warehouse = build(
        tmp_path,
        TEXT_PARAMETERS + f"""
        CREATE TABLE parametres_kpi AS
        SELECT parametre, CAST(valeur AS DOUBLE) AS valeur FROM (VALUES
            ('city_scoring.poids.potentiel', 40.0), ('city_scoring.poids.loyer', 25.0),
            ('city_scoring.poids.densite_concurrentielle', 15.0),
            ('city_scoring.poids.distance_hub', 20.0),
            ('{BC}.nb_magasins_cible_2029', 1.0)
        ) AS t(parametre, valeur);
        CREATE TABLE dim_zone_chalandise AS SELECT * FROM (VALUES
            ('Z1', 'DE', 'A', 9.0, 100, 1.0), ('Z2', 'DE', 'B', 9.0, 100, 1.0),
            ('Z3', 'DE', 'C', 1.0, 100, 8.0), ('Z9', 'ES', 'X', 9.0, 100, 1.0)
        ) AS t(id_zone, code_pays, ville, population_ville_millions, indice_revenu_ue100,
               densite_concurrentielle_pour_100k_hab);
        CREATE TABLE kpi_cout_m2 AS SELECT * FROM (VALUES
            ('Z1', 'Centre commercial', 1000), ('Z2', 'Centre commercial', 600),
            ('Z3', 'Centre commercial', 200), ('Z3', 'Outlet', 50), ('Z9', 'Centre commercial', 100)
        ) AS t(id_zone, type_emplacement, cout_m2_an_eur);
        CREATE TABLE destatis_population_villes AS SELECT * FROM (VALUES
            ('Z1', 4000000), ('Z2', 2000000)) AS t(id_zone, population);
        CREATE TABLE densite_concurrentielle AS SELECT * FROM (VALUES ('Z1', 10.0), ('Z2', 6.0))
            AS t(id_zone, densite_pour_100k_hab);
        CREATE TABLE distance_hub AS SELECT * FROM (VALUES
            ('Z1', 100.0), ('Z2', 300.0), ('Z3', 500.0))
            AS t(id_zone, distance_reelle_km);
        CREATE TABLE fact_logistique (id_zone VARCHAR, distance_route_km DOUBLE);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["city_scoring"],
        "SELECT ville, note_potentiel, note_loyer, note_densite, note_distance, score, rang, "
        "est_prioritaire FROM city_scoring ORDER BY rang",
    )
    # potential: Destatis 4 and 2 million (the simulated 9 is ignored), simulated 1 for C;
    # on a log scale: ln 4, ln 2, ln 1 -> 100, 50, 0 ; rent 1 000, 600, 200 -> 0, 50, 100
    # density: real 10 and 6, simulated 8 for C -> 0, 100, 50 ; distance 100, 300, 500 -> 100, 50, 0
    # A: (100x40 + 100x20) / 100 = 60 ; B: (50x40 + 50x25 + 100x15 + 50x20) / 100 = 57.5
    # C: (100x25 + 50x15) / 100 = 32.5 ; the outlet rent and the Spanish city are left out
    assert rows == [
        ("A", 100.0, 0.0, 0.0, 100.0, 60.0, 1, True),
        ("B", 50.0, 50.0, 100.0, 50.0, 57.5, 2, False),
        ("C", 0.0, 100.0, 50.0, 0.0, 32.5, 3, False),
    ]


def test_payback_sensitivity_reads_as_a_go_frontier(tmp_path):
    warehouse = build(
        tmp_path,
        HYPOTHESES + """
        CREATE TABLE parametres_kpi AS
        SELECT parametre, CAST(valeur AS DOUBLE) AS valeur FROM (VALUES
            ('sensibilite_payback.etp_min', 3.0), ('sensibilite_payback.etp_pas', 0.5),
            ('sensibilite_payback.ca_m2_ratio_min', 1.0),
            ('sensibilite_payback.ca_m2_ratio_max', 1.2),
            ('sensibilite_payback.ca_m2_ratio_pas', 0.2),
            ('go_no_go.payback_pessimiste_max_mois', 36.0)
        ) AS t(parametre, valeur);
        CREATE TABLE parametres_kpi_texte AS SELECT * FROM (VALUES
            ('sensibilite_payback.scenario', 'central'), ('sensibilite_payback.format', 'CC')
        ) AS t(parametre, valeur);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["sensibilite_payback"],
        "SELECT nb_etp, ratio_ca_m2_vs_france, payback_mois, statut_go, ca_m2_ratio_min_go, "
        "etp_max_go, est_cas_business_case FROM sensibilite_payback ORDER BY 1, 2",
    )
    # fixed costs 40 000 + ETP x 40 000 ; margin net of variable costs 60 % ; investment 250 000
    # 3 ETP, 100 %: EBITDA -10, 80, 140, 140 k -> 36 + 40/140 x 12 = 39.4 months
    # 3 ETP, 120 %: 20, 128, 200 k -> 24 + 102/200 x 12 = 30.1
    # 3.5 ETP, 120 %: 0, 108, 180 k -> 24 + 142/180 x 12 = 33.5
    # 3.5 ETP, 100 %: -30, 60, 120, 120 k -> 46.0
    # 4 ETP, 120 %: -20, 88, 160, 160 k -> 36 + 22/160 x 12 = 37.65, rounded to 37.7
    # 4 ETP, 100 % is the business case itself (55.2 months)
    assert rows == [
        (3.0, 1.0, 39.4, "NO-GO", 1.2, None, False),
        (3.0, 1.2, 30.1, "GO", 1.2, 3.5, False),
        (3.5, 1.0, 46.0, "NO-GO", 1.2, None, False),
        (3.5, 1.2, 33.5, "GO", 1.2, 3.5, False),
        (4.0, 1.0, 55.2, "NO-GO", None, None, True),
        (4.0, 1.2, 37.7, "NO-GO", None, 3.5, False),
    ]


def test_france_comparison_uses_the_german_cost_perimeter(tmp_path):
    warehouse = build(
        tmp_path,
        TEXT_PARAMETERS + f"""
        CREATE TABLE parametres_kpi AS
        SELECT parametre, CAST(valeur AS DOUBLE) AS valeur FROM (VALUES
            ('{BC}.couts_additionnels_pct_ca.demarque', 1.0),
            ('{BC}.couts_additionnels_pct_ca.frais_siege', 4.0),
            ('{BC}.duree_amortissement_capex_ans', 5.0)
        ) AS t(parametre, valeur);
        CREATE TABLE kpi_cout_m2 AS SELECT * FROM (VALUES
            ('Centre commercial', 300, 30), ('Centre commercial', 100, 10), ('Outlet', 100, 90)
        ) AS t(type_emplacement, loyer_m2_an_eur, charges_m2_an_eur);
        CREATE TABLE magasins_france_reference AS SELECT * FROM (VALUES
            ('Centre commercial', 500000.0, 350000.0, 70000, 150000.0, 5000.0, 200000, TRUE),
            ('Centre commercial', 500000.0, 350000.0, 70000, 150000.0, 5000.0, 200000, TRUE),
            ('Centre-ville', 900000.0, 600000.0, 90000, 150000.0, 5000.0, 200000, TRUE)
        ) AS t(type_emplacement, ca_ht_eur, marge_brute_eur, loyer_annuel_eur, personnel_eur,
               energie_eur, capex_ouverture_eur, est_simule);
        """,
    )
    rows = run_views(
        tmp_path,
        warehouse,
        ["business_case_france"],
        "SELECT format, nb_magasins, loyer_charges_eur, ebitda_eur, resultat_eur, "
        "cout_occupation_pct, "
        "point_mort_ca_ht_eur, payback_mois FROM business_case_france",
    )
    # charges / rent = 40 / 400 = 10 % ; rent + charges 140 000 x 1.1 = 154 000 (77 000 a store)
    # EBITDA 700 000 - 5 % x 1 000 000 - 154 000 - 300 000 - 10 000 = 186 000 (93 000 a store)
    # depreciation 400 000 / 5 ; break-even (154 + 300 + 10 + 80) k / 2 / 0.65
    # payback 400 x 12 / 186
    # the city-centre store is not a format kept in the parameters
    assert rows == [("Centre commercial", 2, 77000.0, 93000.0, 53000.0, 15.4, 418462.0, 25.8)]
