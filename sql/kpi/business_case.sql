-- Business case Allemagne (T8) : une ligne par scénario et par format.
-- Payback : mois au bout desquels l'EBITDA cumulé couvre l'investissement (montée en charge
-- comprise, interpolation linéaire dans l'année) ; vide s'il n'est pas atteint dans l'horizon.
-- Point mort : CA HT annuel qui couvre les coûts fixes (loyer et charges, personnel, énergie,
-- amortissement) avec le taux de marge sur coûts variables.
-- Coût d'occupation : (loyer + charges) ÷ CA HT de croisière.
CREATE OR REPLACE VIEW business_case AS
WITH annuel AS (
    SELECT
        *,
        ebitda_eur AS ebitda_annee,
        tresorerie_cumulee_eur - ebitda_eur AS tresorerie_debut_annee
    FROM business_case_annuel
),
payback AS (
    SELECT
        scenario,
        format,
        min((annee - 1) * 12 + (-tresorerie_debut_annee) * 12.0 / ebitda_annee) AS payback_mois
    FROM annuel
    WHERE tresorerie_debut_annee < 0 AND tresorerie_cumulee_eur >= 0
    GROUP BY scenario, format
),
croisiere AS (
    SELECT * FROM business_case_annuel
    WHERE annee = (SELECT max(annee) FROM business_case_annuel)
)
SELECT
    h.code_pays,
    h.scenario,
    h.format,
    round(h.surface_m2, 0) AS surface_m2,
    round(h.ca_m2_eur, 0) AS ca_m2_croisiere_eur,
    c.ca_ht_eur AS ca_ht_croisiere_eur,
    round(h.taux_marge * 100, 2) AS taux_marge_brute_pct,
    c.loyer_charges_eur,
    c.personnel_eur,
    c.energie_eur,
    c.couts_variables_eur,
    c.ebitda_eur AS ebitda_croisiere_eur,
    round(c.ebitda_eur - c.investissement_eur / h.duree_amortissement_ans, 0) AS resultat_croisiere_eur,
    c.investissement_eur,
    round(c.loyer_charges_eur * 100.0 / c.ca_ht_eur, 2) AS cout_occupation_pct,
    round((c.loyer_charges_eur + c.personnel_eur + c.energie_eur + c.investissement_eur / h.duree_amortissement_ans)
        / (h.taux_marge - h.taux_couts_variables), 0) AS point_mort_ca_ht_eur,
    round(payback.payback_mois, 1) AS payback_mois,
    h.horizon_annees,
    h.origine_donnees
FROM business_case_hypotheses AS h
JOIN croisiere AS c ON c.scenario = h.scenario AND c.format = h.format
LEFT JOIN payback ON payback.scenario = h.scenario AND payback.format = h.format;
