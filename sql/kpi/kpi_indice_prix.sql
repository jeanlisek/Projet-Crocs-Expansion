-- KPI « Indice prix relatif » (README 2.3) : moyenne, sur le panier des SKU relevés à la
-- fois dans le pays et dans le pays de référence, de (prix HT pays ÷ prix HT référence) × 100.
CREATE OR REPLACE VIEW kpi_indice_prix AS
WITH reference AS (
    SELECT prix.id_produit, prix.prix_ht_eur, prix.est_simule
    FROM kpi_prix_crocs_ht AS prix
    JOIN dim_pays AS pays ON pays.code_pays = prix.code_pays
    WHERE pays.est_pays_reference
)
SELECT
    prix.code_pays,
    count(*) AS nb_sku_panier,
    round(avg(prix.prix_ht_eur / reference.prix_ht_eur) * 100, 2) AS indice_prix,
    CASE
        WHEN bool_and(prix.est_simule AND reference.est_simule) THEN 'SIMULE'
        WHEN NOT bool_or(prix.est_simule OR reference.est_simule) THEN 'REEL'
        ELSE 'MIXTE'
    END AS origine_donnees
FROM kpi_prix_crocs_ht AS prix
JOIN reference ON reference.id_produit = prix.id_produit
JOIN dim_pays AS pays ON pays.code_pays = prix.code_pays
WHERE NOT pays.est_pays_reference
GROUP BY prix.code_pays;
