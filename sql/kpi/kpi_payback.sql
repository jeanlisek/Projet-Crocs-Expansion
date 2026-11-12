-- KPI « Payback » (README 2.3) : investissement d'ouverture ÷ résultat annuel, en mois.
-- Résultat = marge brute − coûts fixes (loyer, personnel, énergie). Agrégé depuis les sommes
-- (règle 6) ; la médiane des magasins est donnée à titre de comparaison.
-- Réseau France (benchmark) ; Allemagne par scénario (pessimiste, central, optimiste) : T8.
CREATE OR REPLACE VIEW kpi_payback AS
SELECT
    'FR' AS code_pays,
    coalesce(type_emplacement, 'Tous formats') AS type_emplacement,
    count(*) AS nb_magasins,
    count(*) FILTER (WHERE marge_brute_eur <= couts_fixes_eur) AS nb_magasins_resultat_negatif,
    round(sum(capex_ouverture_eur) * 12.0 / sum(marge_brute_eur - couts_fixes_eur), 1) AS payback_mois,
    round(median(CASE
        WHEN marge_brute_eur > couts_fixes_eur
            THEN capex_ouverture_eur * 12.0 / (marge_brute_eur - couts_fixes_eur)
        ELSE 'Infinity'::DOUBLE
    END), 1) AS payback_median_mois,
    CASE WHEN bool_and(est_simule) THEN 'SIMULE' WHEN NOT bool_or(est_simule) THEN 'REEL' ELSE 'MIXTE' END
        AS origine_donnees
FROM magasins_france_reference
GROUP BY ROLLUP (type_emplacement);
