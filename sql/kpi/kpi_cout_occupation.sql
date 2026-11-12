-- KPI « Coût d'occupation » (README 2.3) : loyer ÷ CA HT du magasin, recalculé depuis les
-- sommes (règle 6), par format et tous formats, pour le réseau France (benchmark).
-- Charges locatives absentes du jeu France : le taux est un minorant. Allemagne : T8.
CREATE OR REPLACE VIEW kpi_cout_occupation AS
SELECT
    'FR' AS code_pays,
    coalesce(type_emplacement, 'Tous formats') AS type_emplacement,
    count(*) AS nb_magasins,
    round(sum(loyer_annuel_eur) * 100.0 / sum(ca_ht_eur), 2) AS cout_occupation_pct,
    CASE WHEN bool_and(est_simule) THEN 'SIMULE' WHEN NOT bool_or(est_simule) THEN 'REEL' ELSE 'MIXTE' END
        AS origine_donnees
FROM magasins_france_reference
GROUP BY ROLLUP (type_emplacement);
