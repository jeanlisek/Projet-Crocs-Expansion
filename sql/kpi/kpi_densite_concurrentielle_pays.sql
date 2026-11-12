-- KPI « Densité concurrentielle » (README 2.3), agrégée par pays : points de vente pour
-- 100 000 habitants, recalculée depuis les sommes des villes (règle 6).
-- REEL : vue densite_concurrentielle (OpenStreetMap shop=shoes, population Destatis).
-- SIMULE : dim_zone_chalandise (points de vente de neuf concurrents nommés : autre mesure).
-- est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays.
CREATE OR REPLACE VIEW kpi_densite_concurrentielle_pays AS
WITH mesures AS (
    SELECT
        z.code_pays,
        'REEL' AS origine_donnees,
        'Magasins de chaussures OpenStreetMap (shop=shoes)' AS mesure,
        count(*) AS nb_villes,
        round(sum(d.nb_magasins_chaussures) * 100000.0 / sum(d.population_destatis), 2) AS densite_pour_100k_hab
    FROM densite_concurrentielle AS d
    JOIN dim_zone_chalandise AS z ON z.id_zone = d.id_zone
    GROUP BY z.code_pays
    UNION ALL
    SELECT
        code_pays,
        CASE WHEN bool_and(est_simule) THEN 'SIMULE' ELSE 'MIXTE' END,
        'Points de vente des concurrents nommés (jeu simulé)',
        count(*),
        round(sum(nb_points_vente_concurrents) * 100000.0 / sum(population_ville_millions * 1000000), 2)
    FROM dim_zone_chalandise
    GROUP BY code_pays
)
SELECT
    mesures.*,
    origine_donnees = 'REEL' OR NOT bool_or(origine_donnees = 'REEL') OVER (PARTITION BY code_pays) AS est_retenue
FROM mesures;
