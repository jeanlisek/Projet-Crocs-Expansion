-- KPI « Indice prix relatif » (README 2.3) : moyenne, sur un panier identique de SKU hors
-- promotion, de (prix HT pays ÷ prix HT pays de référence) × 100.
-- REEL : crocs_produits (T3, pages produit de crocs.fr et crocs.de). Une paire = même code
--   modèle et même code coloris, commandable sur les deux sites. Prix hors promotion : le prix
--   barré s'il existe, le prix affiché sinon. TVA : collecte.crocs.tva_pct de
--   config/hypotheses.yaml. Les prix HT sont arrondis au centime avant le rapport, avec le même
--   arrondi (au pair le plus proche, round_even) que src/collect/scrape_crocs.py, pour que les
--   deux calculs donnent le même chiffre : 54,99 ÷ 1,20 = 45,825 tombe pile sur une demie, et
--   l'arrondi classique donnerait 100,83 au lieu de 100,85. Sans arrondi, l'indice vaut 100,84.
-- SIMULE : fact_prix_releves, via kpi_prix_crocs_ht (panier des SKU du catalogue simulé).
-- est_retenue : la mesure réelle est prioritaire quand elle existe pour le pays.
CREATE OR REPLACE VIEW kpi_indice_prix AS
WITH tva AS (
    SELECT replace(parametre, 'collecte.crocs.tva_pct.', '') AS code_pays, valeur AS tva_pct
    FROM parametres_kpi
    WHERE starts_with(parametre, 'collecte.crocs.tva_pct.')
),
prix_reel AS (
    SELECT
        p.site AS code_pays,
        p.code_modele,
        p.code_coloris,
        round_even(coalesce(p.prix_barre, p.prix_affiche) / (1 + tva.tva_pct / 100), 2) AS prix_ht_eur
    FROM crocs_produits AS p
    JOIN tva ON tva.code_pays = p.site
    WHERE p.disponible
),
reference_reelle AS (
    SELECT prix_reel.code_modele, prix_reel.code_coloris, prix_reel.prix_ht_eur
    FROM prix_reel
    JOIN dim_pays AS pays ON pays.code_pays = prix_reel.code_pays
    WHERE pays.est_pays_reference
),
reference_simulee AS (
    SELECT prix.id_produit, prix.prix_ht_eur, prix.est_simule
    FROM kpi_prix_crocs_ht AS prix
    JOIN dim_pays AS pays ON pays.code_pays = prix.code_pays
    WHERE pays.est_pays_reference
),
mesures AS (
    SELECT
        prix.code_pays,
        'REEL' AS origine_donnees,
        count(*) AS nb_sku_panier,
        round(avg(prix.prix_ht_eur / reference.prix_ht_eur) * 100, 2) AS indice_prix
    FROM prix_reel AS prix
    JOIN reference_reelle AS reference USING (code_modele, code_coloris)
    JOIN dim_pays AS pays ON pays.code_pays = prix.code_pays
    WHERE NOT pays.est_pays_reference
    GROUP BY prix.code_pays
    UNION ALL
    SELECT
        prix.code_pays,
        CASE WHEN bool_and(prix.est_simule AND reference.est_simule) THEN 'SIMULE' ELSE 'MIXTE' END,
        count(*),
        round(avg(prix.prix_ht_eur / reference.prix_ht_eur) * 100, 2)
    FROM kpi_prix_crocs_ht AS prix
    JOIN reference_simulee AS reference ON reference.id_produit = prix.id_produit
    JOIN dim_pays AS pays ON pays.code_pays = prix.code_pays
    WHERE NOT pays.est_pays_reference
    GROUP BY prix.code_pays
)
SELECT
    mesures.*,
    origine_donnees = 'REEL' OR NOT bool_or(origine_donnees = 'REEL') OVER (PARTITION BY code_pays) AS est_retenue
FROM mesures;
