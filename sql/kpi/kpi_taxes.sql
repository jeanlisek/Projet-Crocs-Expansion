-- KPI « Droits & taxes locales » (README 2.3) : une ligne par pays et par taxe.
-- Réel prioritaire : taxes_reference (T18, saisi depuis les sources officielles, URL par ligne).
-- Le jeu simulé (fact_fiscalite) reste en comparaison pour les taxes que le réel couvre, et seul
-- pour celles qu'il ne couvre pas (droit d'import via la France, éco-contribution).
-- TVA chaussures enfant : sans taux réduit publié, le taux normal s'applique.
-- Impôt sur les sociétés : taux tels que publiés, pas toujours sur le même périmètre (voir note) :
-- l'Allemagne est un taux combiné (IS 15 % + solidarité 5,5 % de l'IS + taxe professionnelle
-- moyenne 14,23 %, variable selon la commune) ; la France est le taux normal hors surtaxes.
CREATE OR REPLACE VIEW kpi_taxes AS
WITH reel AS (
    SELECT code_pays, 'TVA standard' AS taxe, taux_tva_standard_pct AS valeur, '%' AS unite,
        CAST(NULL AS VARCHAR) AS note, est_simule
    FROM taxes_reference
    UNION ALL
    SELECT code_pays, 'TVA chaussures enfant',
        coalesce(taux_tva_reduite_chaussures_enfant_pct, taux_tva_standard_pct), '%',
        CASE WHEN taux_tva_reduite_chaussures_enfant_pct IS NULL THEN 'pas de taux réduit : taux normal' END,
        est_simule
    FROM taxes_reference
    UNION ALL
    SELECT code_pays, 'Impôt sur les sociétés', taux_impot_societes_pct, '%',
        CASE code_pays
            WHEN 'DE' THEN 'taux combiné : IS, solidarité et taxe professionnelle moyenne incluses'
            WHEN 'FR' THEN 'taux normal, hors surtaxes'
        END,
        est_simule
    FROM taxes_reference
    UNION ALL
    SELECT code_pays, 'Droit de douane UE sur les chaussures (chapitre 64, payé une fois à l''entrée)',
        droit_douane_ue_chaussures_ch64_pct, '%', NULL, est_simule
    FROM taxes_reference
    WHERE droit_douane_ue_chaussures_ch64_pct IS NOT NULL
),
simule AS (
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
),
lignes AS (
    -- famille : taxes comparables entre réel et simulé. Le droit d'import simulé (0 % dans l'UE,
    -- déjà acquitté à l'entrée) se compare au droit de douane UE réel : il passe en comparaison
    -- quand le réel existe, pour ne pas sembler le contredire.
    SELECT *, CASE WHEN taxe LIKE 'Droit%' THEN 'Droits de douane' ELSE taxe END AS famille
    FROM (
        SELECT code_pays, taxe, valeur, unite, note, est_simule FROM reel
        UNION ALL
        SELECT code_pays, taxe, valeur, unite, NULL, est_simule FROM simule
    )
)
SELECT
    code_pays,
    taxe,
    valeur,
    unite,
    note,
    CASE WHEN est_simule THEN 'SIMULE' ELSE 'REEL' END AS origine_donnees,
    NOT est_simule OR NOT bool_or(NOT est_simule) OVER (PARTITION BY code_pays, famille) AS est_retenue
FROM lignes;
