-- Table de synthèse des KPIs : contrat entre T7, l'IA (T9) et le dashboard (T11).
-- Colonnes figées (docs/equipe/REGLES_COMMUNES.md, « Contrat entre les tâches ») :
-- kpi, axe, pays, valeur, unite, seuil, statut_go, statut_epistemique, origine_donnees.
-- Seuils : parametres_kpi (section go_no_go de config/hypotheses.yaml, README 4.2).
-- statut_go : GO / NO-GO quand un seuil s'applique au pays candidat ; INFO sinon (pays de
-- référence, KPI sans seuil, lignes de comparaison réel / simulé).
-- Les KPIs de rentabilité Allemagne (par scénario) sont ajoutés par T8.
CREATE OR REPLACE VIEW kpi_summary AS
WITH s AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'go_no_go.tcam_segment_min_pct') AS tcam_min,
        max(valeur) FILTER (WHERE parametre = 'go_no_go.indice_prix_min') AS indice_min,
        max(valeur) FILTER (WHERE parametre = 'go_no_go.indice_prix_max') AS indice_max,
        max(valeur) FILTER (WHERE parametre = 'go_no_go.ecart_marge_vs_france_max_pts') AS ecart_marge_max,
        max(valeur) FILTER (WHERE parametre = 'go_no_go.catalogue_eligible_min_pct') AS catalogue_min
    FROM parametres_kpi
),
reference AS (
    SELECT code_pays, est_pays_reference FROM dim_pays
),
lignes AS (
    -- Marché
    SELECT 'Croissance du secteur (TCAM ' || k.annee_debut || '-' || k.annee_fin || ')' AS kpi, 'Marché' AS axe,
        k.code_pays AS pays, k.tcam_pct AS valeur, '%' AS unite,
        printf('≥ %g %%', s.tcam_min) AS seuil,
        CASE WHEN r.est_pays_reference THEN 'INFO' WHEN k.tcam_pct >= s.tcam_min THEN 'GO' ELSE 'NO-GO' END
            AS statut_go,
        'CALCUL' AS statut_epistemique, k.origine_donnees
    FROM kpi_croissance_secteur AS k JOIN reference AS r USING (code_pays), s
    UNION ALL
    SELECT 'Part de marché ' || k.nom_concurrent, 'Marché', k.code_pays, k.part_marche_pct, '%',
        NULL, 'INFO', 'CALCUL', k.origine_donnees
    FROM kpi_part_de_marche AS k
    WHERE k.id_concurrent <> 'C99'
    -- Prix
    UNION ALL
    SELECT 'Indice prix relatif (HT, base pays de référence = 100)', 'Prix', k.code_pays, k.indice_prix, 'indice',
        printf('%g à %g', s.indice_min, s.indice_max),
        CASE WHEN k.indice_prix BETWEEN s.indice_min AND s.indice_max THEN 'GO' ELSE 'NO-GO' END,
        'CALCUL', k.origine_donnees
    FROM kpi_indice_prix AS k, s
    UNION ALL
    SELECT 'Marge brute post-taxe', 'Prix', k.code_pays, k.marge_post_taxe_pct, '%',
        CASE WHEN r.est_pays_reference THEN NULL
            ELSE printf('≥ %g %%', round(k.marge_reference_meme_panier_pct - s.ecart_marge_max, 2)) END,
        CASE
            WHEN r.est_pays_reference THEN 'INFO'
            WHEN k.marge_post_taxe_pct >= k.marge_reference_meme_panier_pct - s.ecart_marge_max THEN 'GO'
            ELSE 'NO-GO'
        END,
        'CALCUL', k.origine_donnees
    FROM kpi_marge_post_taxe AS k JOIN reference AS r USING (code_pays), s
    -- Réseau
    UNION ALL
    SELECT CASE WHEN k.est_retenue THEN 'Densité concurrentielle'
            ELSE 'Densité concurrentielle (comparaison, jeu simulé)' END,
        'Réseau', k.code_pays, k.densite_pour_100k_hab, 'pour 100 000 hab.', NULL, 'INFO', 'CALCUL',
        k.origine_donnees
    FROM kpi_densite_concurrentielle_pays AS k
    UNION ALL
    SELECT 'Coût moyen au m² (loyer + charges) : ' || k.type_emplacement, 'Réseau', k.code_pays,
        round(avg(k.cout_m2_an_eur), 0), '€/m²/an', NULL, 'INFO', 'CALCUL', any_value(k.origine_donnees)
    FROM kpi_cout_m2 AS k
    GROUP BY k.code_pays, k.type_emplacement
    -- Logistique
    UNION ALL
    SELECT CASE WHEN k.est_retenue THEN 'Distance moyenne au hub le plus proche'
            ELSE 'Distance moyenne au hub le plus proche (comparaison, jeu simulé)' END,
        'Logistique', k.code_pays, k.distance_moyenne_km, 'km', NULL, 'INFO', 'CALCUL', k.origine_donnees
    FROM kpi_distance_hub_pays AS k
    UNION ALL
    -- README : FAIT (à vérifier). Tant que la source est simulée, ce n'est qu'une HYPOTHÈSE.
    SELECT k.taxe, 'Logistique', k.code_pays, k.valeur, k.unite, NULL, 'INFO',
        CASE WHEN k.origine_donnees = 'REEL' THEN 'FAIT' ELSE 'HYPOTHÈSE' END, k.origine_donnees
    FROM kpi_taxes AS k
    -- Assortiment
    UNION ALL
    SELECT 'Pénétration : ' || k.categorie, 'Assortiment', k.code_pays, k.taux_penetration_pct, '%',
        NULL, 'INFO', 'CALCUL', k.origine_donnees
    FROM kpi_penetration_categories AS k
    UNION ALL
    SELECT '% du catalogue éligible', 'Assortiment', k.code_pays, k.catalogue_eligible_pct, '%',
        printf('≥ %g %%', s.catalogue_min),
        CASE WHEN k.catalogue_eligible_pct >= s.catalogue_min THEN 'GO' ELSE 'NO-GO' END,
        'CALCUL', k.origine_donnees
    FROM kpi_catalogue_eligible AS k, s
    -- Rentabilité : benchmark du réseau France (l'Allemagne par scénario vient de T8)
    UNION ALL
    SELECT 'Coût d''occupation (loyer ÷ CA) : ' || k.type_emplacement, 'Rentabilité', k.code_pays,
        k.cout_occupation_pct, '%', NULL, 'INFO', 'CALCUL', k.origine_donnees
    FROM kpi_cout_occupation AS k
    UNION ALL
    SELECT 'Point mort par magasin : ' || k.type_emplacement, 'Rentabilité', k.code_pays,
        k.point_mort_ca_ht_eur, '€ de CA HT/an', NULL, 'INFO', 'CALCUL', k.origine_donnees
    FROM kpi_point_mort AS k
    UNION ALL
    SELECT 'Payback : ' || k.type_emplacement, 'Rentabilité', k.code_pays, k.payback_mois, 'mois', NULL,
        'INFO', 'CALCUL', k.origine_donnees
    FROM kpi_payback AS k
)
SELECT
    kpi,
    axe,
    pays,
    CAST(valeur AS DOUBLE) AS valeur,
    unite,
    seuil,
    statut_go,
    statut_epistemique,
    origine_donnees
FROM lignes;
