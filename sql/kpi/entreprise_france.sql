-- Présentation de l'entreprise : Crocs France en chiffres, une seule ligne (README, section 1).
-- Réseau : magasins physiques de dim_magasin (le canal e-commerce n'est pas un magasin) ; ouverts =
-- sans date de fermeture. CA de l'année kpi.annee_reference, net de remises, TTC et HT, tous canaux
-- (fact_ventes_france). Part de l'e-commerce : CA HT du canal e-commerce ÷ CA HT total, recalculée
-- depuis les sommes (règle 6). SKU : lignes de dim_produit (catalogue France).
CREATE OR REPLACE VIEW entreprise_france AS
WITH annee AS (
    SELECT CAST(valeur AS INTEGER) AS annee FROM parametres_kpi WHERE parametre = 'kpi.annee_reference'
),
reseau AS (
    SELECT
        count(*) FILTER (WHERE type_emplacement <> 'E-commerce') AS nb_magasins_total,
        count(*) FILTER (WHERE type_emplacement <> 'E-commerce' AND date_fermeture IS NULL)
            AS nb_magasins_ouverts,
        bool_and(est_simule) AS est_simule
    FROM dim_magasin
),
ventes AS (
    SELECT
        sum(v.ca_net_ttc_eur) AS ca_ttc_eur,
        sum(v.ca_net_ht_eur) AS ca_ht_eur,
        sum(v.ca_net_ht_eur) FILTER (WHERE m.type_emplacement = 'E-commerce') AS ca_ht_ecommerce_eur,
        bool_and(v.est_simule) AS est_simule
    FROM fact_ventes_france AS v
    JOIN dim_magasin AS m ON m.id_magasin = v.id_magasin
    JOIN dim_temps AS t ON t.id_date = v.id_date
    JOIN annee ON annee.annee = t.annee
),
catalogue AS (
    SELECT count(*) AS nb_sku, bool_and(est_simule) AS est_simule FROM dim_produit
)
SELECT
    annee.annee,
    reseau.nb_magasins_total,
    reseau.nb_magasins_ouverts,
    round(ventes.ca_ttc_eur, 0) AS ca_ttc_eur,
    round(ventes.ca_ht_eur, 0) AS ca_ht_eur,
    round(ventes.ca_ht_ecommerce_eur * 100.0 / ventes.ca_ht_eur, 2) AS part_ecommerce_ca_ht_pct,
    catalogue.nb_sku,
    CASE
        WHEN reseau.est_simule AND ventes.est_simule AND catalogue.est_simule THEN 'SIMULE'
        WHEN NOT (reseau.est_simule OR ventes.est_simule OR catalogue.est_simule) THEN 'REEL'
        ELSE 'MIXTE'
    END AS origine_donnees
FROM annee, reseau, ventes, catalogue;
