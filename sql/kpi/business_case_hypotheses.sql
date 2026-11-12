-- Business case Allemagne (T8), entrées : une ligne par scénario et par format retenu.
-- Magasin type = moyennes du réseau France au même format (règle 7 : CA/m² à format identique) :
-- surface, ETP, CA HT/m² et taux de marge brute recalculés depuis les sommes (règle 6).
-- Taux de marge Allemagne = taux France + écart de marge post-taxe DE - FR (kpi_marge_post_taxe).
-- Loyer + charges : moyenne des 12 villes allemandes pour le type d'emplacement du format.
-- Coûts allemands : fact_couts_exploitation. Hypothèses : config/hypotheses.yaml (parametres_kpi).
CREATE OR REPLACE VIEW business_case_hypotheses AS
WITH p AS (
    SELECT parametre, valeur FROM parametres_kpi WHERE parametre LIKE 'business_case_allemagne.%'
),
formats AS (
    SELECT f.valeur AS format, e.valeur AS type_emplacement_immobilier
    FROM parametres_kpi_texte AS f
    JOIN parametres_kpi_texte AS e
        ON e.parametre = 'business_case_allemagne.emplacement_immobilier.' || f.valeur
    WHERE f.parametre LIKE 'business_case_allemagne.formats_retenus.%'
),
scenarios AS (
    SELECT
        split_part(parametre, '.', 3) AS scenario,
        max(valeur) FILTER (WHERE parametre LIKE '%.ca_m2_vs_france_meme_format') AS ratio_ca_m2_vs_france,
        max(valeur) FILTER (WHERE parametre LIKE '%.montee_en_charge.1') AS montee_an1,
        max(valeur) FILTER (WHERE parametre LIKE '%.montee_en_charge.2') AS montee_an2,
        max(valeur) FILTER (WHERE parametre LIKE '%.montee_en_charge.3') AS montee_an3
    FROM p
    WHERE parametre LIKE 'business_case_allemagne.scenarios.%'
    GROUP BY 1
),
generaux AS (
    SELECT
        sum(valeur) FILTER (WHERE parametre LIKE 'business_case_allemagne.couts_additionnels_pct_ca.%')
            AS couts_variables_pct_ca,
        max(valeur) FILTER (WHERE parametre = 'business_case_allemagne.investissement.part_fixe_eur')
            AS part_fixe_eur,
        max(valeur) FILTER (WHERE parametre = 'business_case_allemagne.duree_amortissement_capex_ans')
            AS duree_amortissement_ans,
        max(valeur) FILTER (WHERE parametre = 'business_case_allemagne.horizon_annees') AS horizon_annees
    FROM p
),
france AS (
    SELECT
        type_emplacement AS format,
        count(*) AS nb_magasins_france,
        avg(surface_vente_m2) AS surface_m2,
        avg(nb_etp) AS nb_etp,
        sum(ca_ht_eur) / sum(surface_vente_m2) AS ca_m2_france_eur,
        sum(marge_brute_eur) / sum(ca_ht_eur) AS taux_marge_france
    FROM magasins_france_reference
    GROUP BY type_emplacement
),
pays AS (
    SELECT valeur AS code_pays FROM (VALUES ('DE')) AS t(valeur)
),
immobilier AS (
    SELECT type_emplacement, avg(loyer_m2_an_eur) AS loyer_m2_an_eur, avg(charges_m2_an_eur) AS charges_m2_an_eur
    FROM kpi_cout_m2 JOIN pays USING (code_pays)
    GROUP BY type_emplacement
)
SELECT
    pays.code_pays,
    scenarios.scenario,
    formats.format,
    formats.type_emplacement_immobilier,
    france.nb_magasins_france,
    france.surface_m2,
    france.nb_etp,
    france.ca_m2_france_eur,
    scenarios.ratio_ca_m2_vs_france,
    france.ca_m2_france_eur * scenarios.ratio_ca_m2_vs_france AS ca_m2_eur,
    france.taux_marge_france,
    marge.ecart_vs_reference_pts AS ecart_marge_vs_france_pts,
    france.taux_marge_france + marge.ecart_vs_reference_pts / 100 AS taux_marge,
    generaux.couts_variables_pct_ca / 100 AS taux_couts_variables,
    immobilier.loyer_m2_an_eur,
    immobilier.charges_m2_an_eur,
    couts.cout_complet_annuel_etp_eur,
    couts.cout_energie_m2_an_eur,
    couts.cout_amenagement_m2_eur,
    couts.budget_marketing_lancement_eur,
    generaux.part_fixe_eur,
    generaux.duree_amortissement_ans,
    CAST(generaux.horizon_annees AS INTEGER) AS horizon_annees,
    scenarios.montee_an1,
    scenarios.montee_an2,
    scenarios.montee_an3,
    CASE WHEN couts.est_simule OR immobilier.loyer_m2_an_eur IS NULL THEN 'SIMULE' ELSE 'MIXTE' END
        AS origine_donnees
FROM scenarios
CROSS JOIN formats
CROSS JOIN generaux
CROSS JOIN pays
JOIN france ON france.format = formats.format
JOIN immobilier ON immobilier.type_emplacement = formats.type_emplacement_immobilier
JOIN kpi_marge_post_taxe AS marge ON marge.code_pays = pays.code_pays
JOIN fact_couts_exploitation AS couts ON couts.code_pays = pays.code_pays;
