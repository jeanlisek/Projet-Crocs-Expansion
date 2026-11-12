-- Business case Allemagne (T8), compte de résultat d'un magasin type, année par année,
-- par scénario et par format : montée en charge les 3 premières années, croisière ensuite.
-- EBITDA = marge brute - loyer et charges - personnel - énergie - coûts variables
--          (démarque, frais bancaires, frais de siège, logistique).
-- Résultat = EBITDA - amortissement de l'investissement.
-- Investissement = aménagement x surface + part fixe + marketing de lancement.
CREATE OR REPLACE VIEW business_case_annuel AS
WITH annees AS (
    SELECT h.*, a.annee
    FROM business_case_hypotheses AS h,
        LATERAL (SELECT unnest(range(1, h.horizon_annees + 1)) AS annee) AS a
),
lignes AS (
    SELECT
        code_pays,
        scenario,
        format,
        annee,
        surface_m2 * ca_m2_eur * CASE annee
            WHEN 1 THEN montee_an1 WHEN 2 THEN montee_an2 WHEN 3 THEN montee_an3 ELSE 1 END AS ca_ht_eur,
        taux_marge,
        taux_couts_variables,
        surface_m2 * (loyer_m2_an_eur + charges_m2_an_eur) AS loyer_charges_eur,
        nb_etp * cout_complet_annuel_etp_eur AS personnel_eur,
        surface_m2 * cout_energie_m2_an_eur AS energie_eur,
        surface_m2 * cout_amenagement_m2_eur + part_fixe_eur + budget_marketing_lancement_eur
            AS investissement_eur,
        duree_amortissement_ans,
        origine_donnees
    FROM annees
),
resultats AS (
    SELECT
        *,
        ca_ht_eur * taux_marge AS marge_brute_eur,
        ca_ht_eur * taux_couts_variables AS couts_variables_eur,
        ca_ht_eur * (taux_marge - taux_couts_variables) - loyer_charges_eur - personnel_eur - energie_eur
            AS ebitda_eur,
        CASE WHEN annee <= duree_amortissement_ans THEN investissement_eur / duree_amortissement_ans ELSE 0 END
            AS amortissement_eur
    FROM lignes
)
SELECT
    code_pays,
    scenario,
    format,
    annee,
    round(ca_ht_eur, 0) AS ca_ht_eur,
    round(marge_brute_eur, 0) AS marge_brute_eur,
    round(loyer_charges_eur, 0) AS loyer_charges_eur,
    round(personnel_eur, 0) AS personnel_eur,
    round(energie_eur, 0) AS energie_eur,
    round(couts_variables_eur, 0) AS couts_variables_eur,
    round(ebitda_eur, 0) AS ebitda_eur,
    round(amortissement_eur, 0) AS amortissement_eur,
    round(ebitda_eur - amortissement_eur, 0) AS resultat_eur,
    round(investissement_eur, 0) AS investissement_eur,
    round(sum(ebitda_eur) OVER (PARTITION BY scenario, format ORDER BY annee) - investissement_eur, 0)
        AS tresorerie_cumulee_eur,
    origine_donnees
FROM resultats;
