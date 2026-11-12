-- KPI « Coût moyen au m² » (README 2.3) : loyer + charges en €/m²/an, par ville et par
-- format, année kpi.annee_reference. Comparable seulement à format identique (règle 7).
CREATE OR REPLACE VIEW kpi_cout_m2 AS
SELECT
    z.code_pays,
    i.id_zone,
    z.ville,
    i.type_emplacement,
    i.annee,
    i.loyer_m2_an_eur,
    i.charges_m2_an_eur,
    i.loyer_m2_an_eur + i.charges_m2_an_eur AS cout_m2_an_eur,
    CASE WHEN i.est_simule THEN 'SIMULE' ELSE 'REEL' END AS origine_donnees
FROM fact_immobilier AS i
JOIN dim_zone_chalandise AS z ON z.id_zone = i.id_zone
WHERE i.annee = (SELECT CAST(valeur AS INTEGER) FROM parametres_kpi WHERE parametre = 'kpi.annee_reference');
