-- KPI « Marge brute post-taxe » (README 2.3) :
-- (prix TTC local ÷ (1 + TVA) − coût débarqué − droits d'import − transport unitaire) ÷ prix HT,
-- recalculée depuis les sommes du panier (règle 6), jamais en moyennant des taux.
-- Droits d'import : nuls dans l'UE (règle 3), appliqués à la valeur FOB + fret hors UE.
-- Transport unitaire : moyenne, sur les villes non insulaires du pays, du coût depuis le hub le
-- plus proche. Le pays de référence n'a pas de ville dans fact_logistique : transport compté 0,
-- ce qui favorise légèrement la référence (limite assumée).
-- Pour chaque pays, la marge de référence est recalculée sur le même panier de SKU.
CREATE OR REPLACE VIEW kpi_marge_post_taxe AS
WITH transport AS (
    SELECT z.code_pays, avg(l.cout_min) AS transport_unitaire_eur
    FROM (
        SELECT id_zone, min(cout_transport_unitaire_eur) AS cout_min FROM fact_logistique GROUP BY id_zone
    ) AS l
    JOIN dim_zone_chalandise AS z ON z.id_zone = l.id_zone
    WHERE NOT z.zone_insulaire
    GROUP BY z.code_pays
),
lignes AS (
    SELECT
        prix.code_pays,
        prix.id_produit,
        prix.prix_ht_eur,
        prix.prix_ht_eur - p.cout_debarque_eur
            - (p.cout_fob_eur + p.cout_fret_unitaire_eur) * f.droit_import_marchandise_origine_asie_via_fr_pct / 100
            - coalesce(t.transport_unitaire_eur, 0) AS marge_eur,
        coalesce(t.transport_unitaire_eur, 0) AS transport_unitaire_eur,
        prix.est_simule
    FROM kpi_prix_crocs_ht AS prix
    JOIN dim_produit AS p ON p.id_produit = prix.id_produit
    JOIN fact_fiscalite AS f ON f.code_pays = prix.code_pays
    LEFT JOIN transport AS t ON t.code_pays = prix.code_pays
),
reference AS (
    SELECT lignes.*
    FROM lignes
    JOIN dim_pays AS pays ON pays.code_pays = lignes.code_pays
    WHERE pays.est_pays_reference
)
SELECT
    lignes.code_pays,
    count(*) AS nb_sku_panier,
    any_value(lignes.transport_unitaire_eur) AS transport_unitaire_eur,
    round(sum(lignes.marge_eur) * 100.0 / sum(lignes.prix_ht_eur), 2) AS marge_post_taxe_pct,
    round(sum(reference.marge_eur) * 100.0 / sum(reference.prix_ht_eur), 2) AS marge_reference_meme_panier_pct,
    round((sum(lignes.marge_eur) / sum(lignes.prix_ht_eur) - sum(reference.marge_eur) / sum(reference.prix_ht_eur))
        * 100, 2) AS ecart_vs_reference_pts,
    CASE
        WHEN bool_and(lignes.est_simule AND reference.est_simule) THEN 'SIMULE'
        WHEN NOT bool_or(lignes.est_simule OR reference.est_simule) THEN 'REEL'
        ELSE 'MIXTE'
    END AS origine_donnees
FROM lignes
JOIN reference ON reference.id_produit = lignes.id_produit
GROUP BY lignes.code_pays;
