-- KPI « Part de marché » (README 2.3) : part en valeur de chaque marque, tous canaux
-- confondus (règle 5 : ce n'est pas le CA de notre réseau), année kpi.annee_reference.
-- Recalculée depuis les CA estimés (règle 6), pas reprise de part_marche_valeur_pct.
CREATE OR REPLACE VIEW kpi_part_de_marche AS
WITH annee AS (
    SELECT CAST(valeur AS INTEGER) AS annee FROM parametres_kpi WHERE parametre = 'kpi.annee_reference'
),
lignes AS (
    SELECT pdm.*
    FROM fact_parts_de_marche AS pdm
    JOIN annee ON annee.annee = pdm.annee
)
SELECT
    lignes.code_pays,
    lignes.annee,
    lignes.id_concurrent,
    c.nom_concurrent,
    lignes.ca_estime_meur,
    sum(lignes.ca_estime_meur) OVER (PARTITION BY lignes.code_pays) AS ca_marche_meur,
    round(lignes.ca_estime_meur * 100.0 / sum(lignes.ca_estime_meur) OVER (PARTITION BY lignes.code_pays), 2)
        AS part_marche_pct,
    CASE WHEN lignes.est_simule THEN 'SIMULE' ELSE 'REEL' END AS origine_donnees
FROM lignes
JOIN dim_concurrent AS c ON c.id_concurrent = lignes.id_concurrent;
