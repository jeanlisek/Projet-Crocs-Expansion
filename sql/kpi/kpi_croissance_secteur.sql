-- KPI « Croissance du secteur » (README 2.3) : TCAM de la taille du marché du segment
-- casual moulé & sandales, entre kpi.tcam_annee_debut et kpi.tcam_annee_fin (parametres_kpi).
-- Années observées seulement : les projections (est_projection) sont exclues.
CREATE OR REPLACE VIEW kpi_croissance_secteur AS
WITH periode AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'kpi.tcam_annee_debut') AS debut,
        max(valeur) FILTER (WHERE parametre = 'kpi.tcam_annee_fin') AS fin
    FROM parametres_kpi
),
bornes AS (
    SELECT
        m.code_pays,
        CAST(periode.debut AS INTEGER) AS annee_debut,
        CAST(periode.fin AS INTEGER) AS annee_fin,
        max(m.taille_marche_meur) FILTER (WHERE m.annee = periode.debut) AS taille_debut_meur,
        max(m.taille_marche_meur) FILTER (WHERE m.annee = periode.fin) AS taille_fin_meur,
        bool_and(m.est_simule) AS tout_simule,
        bool_or(m.est_simule) AS un_simule
    FROM fact_marche AS m, periode
    WHERE m.segment = 'Casual moulé & sandales'
      AND NOT m.est_projection
      AND m.annee IN (periode.debut, periode.fin)
    GROUP BY m.code_pays, periode.debut, periode.fin
)
SELECT
    code_pays,
    annee_debut,
    annee_fin,
    taille_debut_meur,
    taille_fin_meur,
    round((power(taille_fin_meur / taille_debut_meur, 1.0 / (annee_fin - annee_debut)) - 1) * 100, 2)
        AS tcam_pct,
    CASE WHEN tout_simule THEN 'SIMULE' WHEN NOT un_simule THEN 'REEL' ELSE 'MIXTE' END AS origine_donnees
FROM bornes;
