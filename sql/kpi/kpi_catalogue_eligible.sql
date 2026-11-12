-- KPI « % du catalogue éligible » (README 2.3), par pays.
-- REEL : crocs_catalogue (T3, pages de catégorie de crocs.fr et crocs.de). Références (code
--   modèle + code coloris) du site du pays de référence aussi listées sur le site du pays,
--   ÷ références du site du pays de référence. Une référence listée dans plusieurs catégories
--   compte une fois.
-- SIMULE : fact_eligibilite_assortiment. SKU éligibles ÷ SKU du catalogue France (dim_produit),
--   dénominateur compté et non écrit en dur. Autre mesure : éligibilité réglementaire du jeu
--   simulé, et non présence sur le site.
-- est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays.
CREATE OR REPLACE VIEW kpi_catalogue_eligible AS
WITH catalogue AS (
    SELECT DISTINCT site AS code_pays, code_modele, code_coloris FROM crocs_catalogue
),
reference AS (
    SELECT catalogue.code_modele, catalogue.code_coloris
    FROM catalogue
    JOIN dim_pays AS pays ON pays.code_pays = catalogue.code_pays
    WHERE pays.est_pays_reference
),
mesures AS (
    SELECT
        catalogue.code_pays,
        'REEL' AS origine_donnees,
        'Références du catalogue du site de référence listées sur le site du pays' AS mesure,
        count(*) AS nb_sku_eligibles,
        (SELECT count(*) FROM reference) AS nb_sku_catalogue,
        round(count(*) * 100.0 / (SELECT count(*) FROM reference), 2) AS catalogue_eligible_pct
    FROM catalogue
    JOIN reference USING (code_modele, code_coloris)
    JOIN dim_pays AS pays ON pays.code_pays = catalogue.code_pays
    WHERE NOT pays.est_pays_reference
    GROUP BY catalogue.code_pays
    UNION ALL
    SELECT
        e.code_pays,
        CASE WHEN bool_and(e.est_simule) THEN 'SIMULE' ELSE 'MIXTE' END,
        'SKU éligibles du catalogue France (jeu simulé)',
        count(*) FILTER (WHERE e.eligible),
        (SELECT count(*) FROM dim_produit),
        round(count(*) FILTER (WHERE e.eligible) * 100.0 / (SELECT count(*) FROM dim_produit), 2)
    FROM fact_eligibilite_assortiment AS e
    GROUP BY e.code_pays
)
SELECT
    mesures.*,
    origine_donnees = 'REEL' OR NOT bool_or(origine_donnees = 'REEL') OVER (PARTITION BY code_pays) AS est_retenue
FROM mesures;
