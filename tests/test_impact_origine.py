"""Test of the impact_origine view on a tiny warehouse whose results are computed by hand."""

from pathlib import Path

import duckdb

from src.transform import run_kpi

SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "kpi" / "impact_origine.sql"

# P1 (Vietnam) and P2 (China) are footwear of the code under study; P3 (Vietnam) is an accessory
# of another code, whose simulated duty is never touched. Customs value = FOB + freight = 10 for
# P1 and P2, 5 for P3. Simulated duty 20 % on P1 and P2, 5 % on P3; real third-country duty 10 %.
# 2025 sales in the store of the studied format: 100 units of each product, turnover 5 000.
# The 2024 sale and the store of another format are ignored.
WAREHOUSE = """
    CREATE TABLE parametres_kpi AS SELECT * FROM (VALUES
        ('impact_origine.droit_preferentiel_pct', 0.0),
        ('kpi.annee_reference', 2025.0),
        ('go_no_go.payback_pessimiste_max_mois', 36.0)
    ) AS t(parametre, valeur);
    CREATE TABLE parametres_kpi_texte AS SELECT * FROM (VALUES
        ('impact_origine.code_sh', '6402.99'),
        ('impact_origine.pays_preferentiel', 'Vietnam'),
        ('impact_origine.scenario', 'pessimiste'),
        ('impact_origine.format', 'CC')
    ) AS t(parametre, valeur);
    CREATE TABLE taxes_reference AS SELECT * FROM (VALUES ('DE', 10.0), ('FR', 10.0))
        AS t(code_pays, droit_douane_ue_chaussures_ch64_pct);
    CREATE TABLE dim_produit AS SELECT * FROM (VALUES
        ('P1', 'Vietnam', '6402.99', 9.0, 1.0, 12.0, 20.0),
        ('P2', 'Chine', '6402.99', 9.0, 1.0, 12.0, 20.0),
        ('P3', 'Vietnam', '3926.40', 4.0, 1.0, 5.25, 5.0)
    ) AS t(id_produit, pays_origine, code_sh, cout_fob_eur, cout_fret_unitaire_eur,
           cout_debarque_eur, taux_droit_ue_pct);
    CREATE TABLE dim_temps AS SELECT * FROM (VALUES (202401, 2024), (202501, 2025))
        AS t(id_date, annee);
    CREATE TABLE magasins_france_reference AS SELECT * FROM (VALUES ('M1', 'CC'), ('M2', 'CV'))
        AS t(id_magasin, type_emplacement);
    CREATE TABLE fact_ventes_france AS SELECT * FROM (VALUES
        ('M1', 'P1', 202501, 100, 2000.0),
        ('M1', 'P2', 202501, 100, 2000.0),
        ('M1', 'P3', 202501, 100, 1000.0),
        ('M1', 'P1', 202401, 999, 9999.0),
        ('M2', 'P1', 202501, 999, 9999.0)
    ) AS t(id_magasin, id_produit, id_date, quantite_vendue, ca_net_ht_eur);
    -- Store: turnover 1 000 a year from year 1, margin 50 %, variable costs 10 %, fixed costs 300
    -- (rent 100, staff 200), investment 300: EBITDA 100 a year, payback 36 months.
    CREATE TABLE business_case_hypotheses AS SELECT * FROM (VALUES
        ('DE', 'pessimiste', 'CC', 100.0, 10.0, 0.5, 0.1, 1.0, 0.0, 1.0, 200.0, 0.0, 0.0, 300.0,
         0.0, 10, 1.0, 1.0, 1.0)
    ) AS t(code_pays, scenario, format, surface_m2, ca_m2_eur, taux_marge, taux_couts_variables,
           loyer_m2_an_eur, charges_m2_an_eur, nb_etp, cout_complet_annuel_etp_eur,
           cout_energie_m2_an_eur, cout_amenagement_m2_eur, part_fixe_eur,
           budget_marketing_lancement_eur, horizon_annees, montee_an1, montee_an2, montee_an3);
"""


def test_duty_saving_by_origin_raises_the_margin_and_shortens_the_payback(tmp_path):
    warehouse = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(warehouse))
    con.execute(WAREHOUSE)
    con.close()
    sql_dir = tmp_path / "kpi"
    sql_dir.mkdir()
    (sql_dir / SQL_FILE.name).write_text(SQL_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    run_kpi.run(warehouse, sql_dir)

    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        rows = con.execute(
            "SELECT cas_origine, nb_produits_concernes, nb_produits_concernes_vietnam, "
            "cout_debarque_moyen_eur, taux_marge_pct, gain_marge_pts, ebitda_croisiere_eur, "
            "payback_mois, statut_go FROM impact_origine"
        ).fetchall()
    finally:
        con.close()
    # simule: no change. Landed cost (100 x 12 + 100 x 12 + 100 x 5.25) / 300 = 9.75.
    #   EBITDA 1 000 x (0.5 - 0.1) - 300 = 100: cash -200, -100, 0 -> payback 36 months.
    # droit_tiers_reel: P1 and P2 at 10 % -> landed cost 11, saving 1 a unit, 200 in all:
    #   + 200 / 5 000 = 4 points. EBITDA 140: cash -160, -20, +120 -> 24 + 20 / 140 x 12 = 25.7.
    # preference_vietnam: P1 at 0 % (saving 2), P2 at 10 % (saving 1): 300 -> + 6 points.
    #   Landed cost (1 000 + 1 100 + 525) / 300 = 8.75. EBITDA 160: cash -140, +20 -> 12 + 140 /
    #   160 x 12 = 22.5. P3 keeps its own 5 % duty in every case.
    assert rows == [
        ("simule", 2, 1, 9.75, 50.0, 0.0, 100.0, 36.0, "GO"),
        ("droit_tiers_reel", 2, 1, 9.08, 54.0, 4.0, 140.0, 25.7, "GO"),
        ("preference_vietnam", 2, 1, 8.75, 56.0, 6.0, 160.0, 22.5, "GO"),
    ]
