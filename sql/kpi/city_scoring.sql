-- Scoring des villes allemandes (T8), sur 100. Chaque critère est ramené de 0 à 100 entre les
-- villes (0 = la moins favorable, 100 = la plus favorable), puis pondéré (city_scoring.poids).
-- Potentiel : population de la zone de chalandise x indice de revenu (jeu simulé), noté sur
-- son logarithme (CONVENTION : sinon Berlin, 4 à 10 fois plus peuplée, écrase les autres villes).
-- Loyer : loyer + charges moyens des types d'emplacement des formats retenus (jeu simulé).
-- Densité concurrentielle : réelle (OSM) si disponible, sinon simulée ; plus dense = moins favorable
-- (CONVENTION : on lit la densité comme une pression concurrentielle).
-- Distance au hub : réelle (OSRM) si disponible, sinon simulée.
-- est_prioritaire : rang <= business_case_allemagne.nb_magasins_cible_2029.
CREATE OR REPLACE VIEW city_scoring AS
WITH poids AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'city_scoring.poids.potentiel') AS potentiel,
        max(valeur) FILTER (WHERE parametre = 'city_scoring.poids.loyer') AS loyer,
        max(valeur) FILTER (WHERE parametre = 'city_scoring.poids.densite_concurrentielle') AS densite,
        max(valeur) FILTER (WHERE parametre = 'city_scoring.poids.distance_hub') AS distance,
        max(valeur) FILTER (WHERE parametre = 'business_case_allemagne.nb_magasins_cible_2029') AS nb_cible
    FROM parametres_kpi
),
emplacements AS (
    SELECT e.valeur AS type_emplacement
    FROM parametres_kpi_texte AS f
    JOIN parametres_kpi_texte AS e
        ON e.parametre = 'business_case_allemagne.emplacement_immobilier.' || f.valeur
    WHERE f.parametre LIKE 'business_case_allemagne.formats_retenus.%'
),
loyers AS (
    SELECT id_zone, avg(cout_m2_an_eur) AS cout_m2_an_eur
    FROM kpi_cout_m2 JOIN emplacements USING (type_emplacement)
    GROUP BY id_zone
),
villes AS (
    SELECT
        z.id_zone,
        z.ville,
        z.population_zone_chalandise_millions * z.indice_revenu_ue100 / 100 AS potentiel,
        loyers.cout_m2_an_eur,
        coalesce(d.densite_pour_100k_hab, z.densite_concurrentielle_pour_100k_hab) AS densite_pour_100k_hab,
        coalesce(h.distance_reelle_km, l.distance_min_km) AS distance_hub_km,
        CASE WHEN d.id_zone IS NULL AND h.id_zone IS NULL THEN 'SIMULE' ELSE 'MIXTE' END AS origine_donnees
    FROM dim_zone_chalandise AS z
    JOIN loyers ON loyers.id_zone = z.id_zone
    LEFT JOIN densite_concurrentielle AS d ON d.id_zone = z.id_zone
    LEFT JOIN distance_hub AS h ON h.id_zone = z.id_zone
    LEFT JOIN (
        SELECT id_zone, min(distance_route_km) AS distance_min_km FROM fact_logistique GROUP BY id_zone
    ) AS l ON l.id_zone = z.id_zone
    WHERE z.code_pays = 'DE'
),
notes AS (
    SELECT
        *,
        (ln(potentiel) - min(ln(potentiel)) OVER ()) * 100.0
            / nullif(max(ln(potentiel)) OVER () - min(ln(potentiel)) OVER (), 0) AS note_potentiel,
        (max(cout_m2_an_eur) OVER () - cout_m2_an_eur) * 100.0
            / nullif(max(cout_m2_an_eur) OVER () - min(cout_m2_an_eur) OVER (), 0) AS note_loyer,
        (max(densite_pour_100k_hab) OVER () - densite_pour_100k_hab) * 100.0
            / nullif(max(densite_pour_100k_hab) OVER () - min(densite_pour_100k_hab) OVER (), 0) AS note_densite,
        (max(distance_hub_km) OVER () - distance_hub_km) * 100.0
            / nullif(max(distance_hub_km) OVER () - min(distance_hub_km) OVER (), 0) AS note_distance
    FROM villes
),
scores AS (
    SELECT
        notes.*,
        (note_potentiel * poids.potentiel + note_loyer * poids.loyer + note_densite * poids.densite
            + note_distance * poids.distance) / (poids.potentiel + poids.loyer + poids.densite + poids.distance)
            AS score,
        poids.nb_cible
    FROM notes, poids
)
SELECT
    id_zone,
    ville,
    round(potentiel, 3) AS potentiel_millions_ponderes,
    round(cout_m2_an_eur, 0) AS cout_m2_an_eur,
    densite_pour_100k_hab,
    distance_hub_km,
    round(note_potentiel, 1) AS note_potentiel,
    round(note_loyer, 1) AS note_loyer,
    round(note_densite, 1) AS note_densite,
    round(note_distance, 1) AS note_distance,
    round(score, 1) AS score,
    CAST(rank() OVER (ORDER BY score DESC) AS INTEGER) AS rang,
    rank() OVER (ORDER BY score DESC) <= nb_cible AS est_prioritaire,
    origine_donnees
FROM scores;
