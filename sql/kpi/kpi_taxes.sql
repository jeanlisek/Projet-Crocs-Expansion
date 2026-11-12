-- KPI « Droits & taxes locales » (README 2.3) : une ligne par pays et par taxe.
-- TODO T18 : lire data/manual/taxes_reference.csv (réel) en priorité quand il sera dans l'entrepôt.
CREATE OR REPLACE VIEW kpi_taxes AS
SELECT
    code_pays,
    taxe,
    valeur,
    unite,
    CASE WHEN est_simule THEN 'SIMULE' ELSE 'REEL' END AS origine_donnees
FROM (
    SELECT code_pays, 'TVA standard' AS taxe, taux_tva_standard_pct AS valeur, '%' AS unite, est_simule
    FROM fact_fiscalite
    UNION ALL
    SELECT code_pays, 'TVA chaussures enfant', taux_tva_chaussures_enfant_pct, '%', est_simule FROM fact_fiscalite
    UNION ALL
    SELECT code_pays, 'Impôt sur les sociétés', taux_impot_societes_pct, '%', est_simule FROM fact_fiscalite
    UNION ALL
    SELECT code_pays, 'Droit d''import (origine Asie, via la France)',
        droit_import_marchandise_origine_asie_via_fr_pct, '%', est_simule
    FROM fact_fiscalite
    UNION ALL
    SELECT code_pays, 'Éco-contribution', eco_contribution_par_paire_eur, '€/paire', est_simule FROM fact_fiscalite
);
