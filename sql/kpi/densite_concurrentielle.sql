-- KPI « Densité concurrentielle » (README, section 2.3), par ville allemande.
-- Magasins de chaussures toutes enseignes (OpenStreetMap, shop=shoes) pour 100 000 habitants.
-- Numérateur : osm_villes (réel). Dénominateur : destatis_population_villes (réel, officiel,
-- même date de référence pour toutes les villes).
-- Les colonnes *_population_osm et *_population_simulee refont le même calcul avec les deux
-- autres populations, pour comparaison ; densite_simulee_v1 est la valeur du jeu simulé,
-- qui comptait les points de vente de neuf concurrents nommés (autre mesure).
CREATE OR REPLACE VIEW densite_concurrentielle AS
SELECT
    osm.id_zone,
    osm.ville,
    osm.nb_magasins_chaussures,
    destatis.population AS population_destatis,
    destatis.date_reference AS date_reference_population,
    round(osm.nb_magasins_chaussures * 100000.0 / destatis.population, 2) AS densite_pour_100k_hab,
    osm.population_osm,
    osm.annee_population_osm,
    round(osm.nb_magasins_chaussures * 100000.0 / osm.population_osm, 2) AS densite_population_osm,
    CAST(round(zone.population_ville_millions * 1000000) AS BIGINT) AS population_simulee,
    round(osm.nb_magasins_chaussures * 100000.0 / (zone.population_ville_millions * 1000000), 2)
        AS densite_population_simulee,
    zone.densite_concurrentielle_pour_100k_hab AS densite_simulee_v1,
    'REEL' AS origine_donnees
FROM osm_villes AS osm
JOIN destatis_population_villes AS destatis ON destatis.id_zone = osm.id_zone
JOIN dim_zone_chalandise AS zone ON zone.id_zone = osm.id_zone;
