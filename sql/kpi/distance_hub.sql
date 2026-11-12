-- KPI « Distance aux hubs » (README, section 2.3), par ville allemande.
-- Pour chaque ville : le hub le plus proche par la route et la distance routière réelle
-- (OSRM), comparés au hub le plus proche et à la distance du jeu simulé (fact_logistique,
-- distance à vol d'oiseau majorée de 25 %).
-- duree_conduite_h est un temps de conduite en voiture, pas un délai de livraison.
-- L'emplacement des hubs est une hypothèse du scénario (centre de la commune).
CREATE OR REPLACE VIEW distance_hub AS
WITH reel AS (
    SELECT
        id_zone,
        any_value(ville) AS ville,
        arg_min(id_hub, distance_route_km) AS id_hub_le_plus_proche,
        arg_min(commune_hub, distance_route_km) AS commune_hub_le_plus_proche,
        min(distance_route_km) AS distance_reelle_km,
        arg_min(duree_h, distance_route_km) AS duree_conduite_h
    FROM osrm_distances
    GROUP BY id_zone
),
simule AS (
    SELECT
        id_zone,
        arg_min(id_hub, distance_route_km) AS id_hub_le_plus_proche_simule,
        min(distance_route_km) AS distance_simulee_km
    FROM fact_logistique
    GROUP BY id_zone
)
SELECT
    reel.id_zone,
    reel.ville,
    reel.id_hub_le_plus_proche,
    reel.commune_hub_le_plus_proche,
    reel.distance_reelle_km,
    reel.duree_conduite_h,
    simule.id_hub_le_plus_proche_simule,
    simule.distance_simulee_km,
    reel.id_hub_le_plus_proche = simule.id_hub_le_plus_proche_simule AS meme_hub,
    round(reel.distance_reelle_km - simule.distance_simulee_km, 1) AS ecart_km,
    round((reel.distance_reelle_km - simule.distance_simulee_km) * 100.0 / simule.distance_simulee_km, 1)
        AS ecart_pct,
    'REEL' AS origine_donnees
FROM reel
JOIN simule ON simule.id_zone = reel.id_zone;
