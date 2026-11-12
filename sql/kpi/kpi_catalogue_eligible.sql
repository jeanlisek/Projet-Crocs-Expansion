-- KPI « % du catalogue éligible » (README 2.3) : SKU éligibles ÷ SKU du catalogue France
-- (dim_produit, 147 SKU), par pays. Le dénominateur est compté, pas écrit en dur.
-- TODO T3 : la part réelle du catalogue présente sur crocs.de sera prioritaire.
CREATE OR REPLACE VIEW kpi_catalogue_eligible AS
SELECT
    e.code_pays,
    count(*) FILTER (WHERE e.eligible) AS nb_sku_eligibles,
    (SELECT count(*) FROM dim_produit) AS nb_sku_catalogue,
    round(count(*) FILTER (WHERE e.eligible) * 100.0 / (SELECT count(*) FROM dim_produit), 2) AS catalogue_eligible_pct,
    CASE WHEN bool_and(e.est_simule) THEN 'SIMULE' WHEN NOT bool_or(e.est_simule) THEN 'REEL' ELSE 'MIXTE' END
        AS origine_donnees
FROM fact_eligibilite_assortiment AS e
GROUP BY e.code_pays;
