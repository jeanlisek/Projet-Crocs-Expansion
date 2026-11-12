-- KPI « Distance moyenne aux hubs » (README 2.3), par pays : moyenne, sur les villes du pays,
-- de la distance routière au hub le plus proche. Les zones insulaires sont exclues (T2).
-- REEL : vue distance_hub (OSRM). SIMULE : fact_logistique (vol d'oiseau × 1,25).
-- est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays.
CREATE OR REPLACE VIEW kpi_distance_hub_pays AS
WITH mesures AS (
    SELECT
        z.code_pays,
        'REEL' AS origine_donnees,
        count(*) AS nb_villes,
        round(avg(d.distance_reelle_km), 1) AS distance_moyenne_km
    FROM distance_hub AS d
    JOIN dim_zone_chalandise AS z ON z.id_zone = d.id_zone
    WHERE NOT z.zone_insulaire
    GROUP BY z.code_pays
    UNION ALL
    SELECT
        z.code_pays,
        CASE WHEN bool_and(z.est_simule) THEN 'SIMULE' ELSE 'MIXTE' END,
        count(*),
        round(avg(l.distance_min_km), 1)
    FROM (SELECT id_zone, min(distance_route_km) AS distance_min_km FROM fact_logistique GROUP BY id_zone) AS l
    JOIN dim_zone_chalandise AS z ON z.id_zone = l.id_zone
    WHERE NOT z.zone_insulaire
    GROUP BY z.code_pays
)
SELECT
    mesures.*,
    origine_donnees = 'REEL' OR NOT bool_or(origine_donnees = 'REEL') OVER (PARTITION BY code_pays) AS est_retenue
FROM mesures;
