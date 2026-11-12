-- Base des KPIs « Indice prix relatif » et « Marge brute post-taxe » (pas un KPI en soi).
-- Prix publics Crocs relevés sur les sites officiels (enseigne crocs.*), hors promotion
-- (README 2.5, règle 4), moyennés par SKU et par pays, puis convertis en HT avec la TVA
-- du pays : taux réduit chaussures enfant pour les cibles Enfant et Bébé, standard sinon.
-- TODO T3 : quand la table réelle des prix scrapés existera, la lire ici en priorité.
CREATE OR REPLACE VIEW kpi_prix_crocs_ht AS
SELECT
    r.code_pays,
    r.id_produit,
    count(*) AS nb_releves,
    avg(r.prix_affiche_eur) AS prix_ttc_eur,
    avg(r.prix_affiche_eur) / (1 + CASE
        WHEN p.cible IN ('Enfant', 'Bébé') THEN f.taux_tva_chaussures_enfant_pct
        ELSE f.taux_tva_standard_pct
    END / 100) AS prix_ht_eur,
    bool_and(r.est_simule) AS est_simule
FROM fact_prix_releves AS r
JOIN dim_produit AS p ON p.id_produit = r.id_produit
JOIN fact_fiscalite AS f ON f.code_pays = r.code_pays
WHERE r.enseigne LIKE 'crocs.%'
  AND NOT r.en_promotion
GROUP BY r.code_pays, r.id_produit, p.cible, f.taux_tva_chaussures_enfant_pct, f.taux_tva_standard_pct;
