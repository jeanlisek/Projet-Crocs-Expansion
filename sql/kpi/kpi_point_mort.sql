-- KPI « Point mort par magasin » (README 2.3) : coûts fixes annuels ÷ taux de marge brute,
-- en CA HT annuel. Par format et tous formats : (coûts fixes moyens) ÷ (marge totale ÷ CA total).
-- Réseau France (benchmark) ; Allemagne par scénario : T8.
CREATE OR REPLACE VIEW kpi_point_mort AS
SELECT
    'FR' AS code_pays,
    coalesce(type_emplacement, 'Tous formats') AS type_emplacement,
    count(*) AS nb_magasins,
    round(sum(marge_brute_eur) * 100.0 / sum(ca_ht_eur), 2) AS taux_marge_brute_pct,
    round(sum(couts_fixes_eur) / count(*) / (sum(marge_brute_eur) / sum(ca_ht_eur)), 0) AS point_mort_ca_ht_eur,
    round(sum(ca_ht_eur) / count(*), 0) AS ca_ht_moyen_eur,
    CASE WHEN bool_and(est_simule) THEN 'SIMULE' WHEN NOT bool_or(est_simule) THEN 'REEL' ELSE 'MIXTE' END
        AS origine_donnees
FROM magasins_france_reference
GROUP BY ROLLUP (type_emplacement);
