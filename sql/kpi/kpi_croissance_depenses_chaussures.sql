-- Confirmation de la croissance du secteur sur données réelles (T4, Eurostat) : TCAM des dépenses
-- de consommation des ménages en chaussures (COICOP CP032, euros courants) entre kpi.tcam_annee_debut
-- et kpi.tcam_annee_fin. Périmètre différent du KPI « Croissance du secteur » (segment casual moulé &
-- sandales, jeu simulé) : toutes chaussures, en valeur, inflation comprise. Ligne INFO de
-- confirmation : le verdict GO / NO-GO reste porté par la définition du README (2.3).
-- Un pays sans valeur publiée pour l'une des deux années (Royaume-Uni) n'a pas de ligne.
CREATE OR REPLACE VIEW kpi_croissance_depenses_chaussures AS
WITH periode AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'kpi.tcam_annee_debut') AS debut,
        max(valeur) FILTER (WHERE parametre = 'kpi.tcam_annee_fin') AS fin
    FROM parametres_kpi
),
bornes AS (
    SELECT
        debut_serie.code_pays,
        CAST(periode.debut AS INTEGER) AS annee_debut,
        CAST(periode.fin AS INTEGER) AS annee_fin,
        debut_serie.valeur AS depenses_debut_meur,
        fin_serie.valeur AS depenses_fin_meur,
        nullif(concat_ws(' ', debut_serie.statut_eurostat, fin_serie.statut_eurostat), '') AS statuts_eurostat,
        debut_serie.est_simule OR fin_serie.est_simule AS un_simule,
        debut_serie.est_simule AND fin_serie.est_simule AS tout_simule
    FROM eurostat_series AS debut_serie
    JOIN eurostat_series AS fin_serie
        ON fin_serie.code_pays = debut_serie.code_pays AND fin_serie.indicateur = debut_serie.indicateur
    JOIN periode ON debut_serie.annee = periode.debut AND fin_serie.annee = periode.fin
    WHERE debut_serie.indicateur = 'depenses_menages_chaussures_meur'
      AND debut_serie.valeur > 0
      AND fin_serie.valeur IS NOT NULL
)
SELECT
    code_pays,
    annee_debut,
    annee_fin,
    depenses_debut_meur,
    depenses_fin_meur,
    round((power(depenses_fin_meur / depenses_debut_meur, 1.0 / (annee_fin - annee_debut)) - 1) * 100, 2)
        AS tcam_pct,
    statuts_eurostat,
    CASE WHEN tout_simule THEN 'SIMULE' WHEN NOT un_simule THEN 'REEL' ELSE 'MIXTE' END AS origine_donnees
FROM bornes;
