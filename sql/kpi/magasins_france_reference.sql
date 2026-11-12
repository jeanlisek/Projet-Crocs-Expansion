-- Base des KPIs de rentabilité France (pas un KPI en soi) : un magasin physique par ligne,
-- ouvert toute l'année kpi.annee_reference (ouvert avant, pas fermé pendant), avec son compte
-- de résultat simplifié. Coûts fixes = loyer + personnel (ETP × coût complet) + énergie (m² ×
-- coût au m²). Les charges locatives ne sont pas connues pour les magasins France (limite).
-- Le compte de résultat complet (marketing, logistique, démarque, siège...) relève de T8.
CREATE OR REPLACE VIEW magasins_france_reference AS
WITH annee AS (
    SELECT CAST(valeur AS INTEGER) AS annee FROM parametres_kpi WHERE parametre = 'kpi.annee_reference'
),
ventes AS (
    SELECT
        v.id_magasin,
        sum(v.ca_net_ht_eur) AS ca_ht_eur,
        sum(v.marge_brute_eur) AS marge_brute_eur,
        bool_or(v.est_simule) AS ventes_simulees
    FROM fact_ventes_france AS v
    JOIN dim_temps AS t ON t.id_date = v.id_date
    JOIN annee ON annee.annee = t.annee
    GROUP BY v.id_magasin
)
SELECT
    m.id_magasin,
    m.type_emplacement,
    m.surface_vente_m2,
    m.nb_etp,
    ventes.ca_ht_eur,
    ventes.marge_brute_eur,
    m.loyer_annuel_eur,
    m.nb_etp * c.cout_complet_annuel_etp_eur AS personnel_eur,
    m.surface_vente_m2 * c.cout_energie_m2_an_eur AS energie_eur,
    m.loyer_annuel_eur + m.nb_etp * c.cout_complet_annuel_etp_eur + m.surface_vente_m2 * c.cout_energie_m2_an_eur
        AS couts_fixes_eur,
    m.capex_ouverture_eur,
    m.est_simule OR ventes.ventes_simulees AS est_simule
FROM dim_magasin AS m
JOIN ventes ON ventes.id_magasin = m.id_magasin
JOIN fact_couts_exploitation AS c ON c.code_pays = m.code_pays
JOIN annee ON TRUE
WHERE m.canal = 'Magasin physique'
  AND m.annee_ouverture < annee.annee
  AND (m.date_fermeture IS NULL OR year(m.date_fermeture) > annee.annee);
