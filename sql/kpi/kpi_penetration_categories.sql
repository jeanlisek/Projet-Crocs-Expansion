-- KPI « Pénétration des catégories » (README 2.3) : part des consommateurs ayant acheté la
-- catégorie, par pays, année kpi.annee_reference.
CREATE OR REPLACE VIEW kpi_penetration_categories AS
SELECT
    code_pays,
    annee,
    categorie,
    taux_penetration_pct,
    taille_echantillon,
    CASE WHEN est_simule THEN 'SIMULE' ELSE 'REEL' END AS origine_donnees
FROM fact_penetration_categories
WHERE annee = (SELECT CAST(valeur AS INTEGER) FROM parametres_kpi WHERE parametre = 'kpi.annee_reference');
