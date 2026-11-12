-- Sensibilité du payback (T8-sensibilite) : scénario et format de sensibilite_payback (pessimiste,
-- centre commercial), en faisant varier deux entrées du magasin type, toutes choses égales par ailleurs :
-- - le nombre d'ETP, de etp_min à l'ETP du magasin type (moyenne France), par pas de etp_pas ;
-- - le CA/m² en part de la France même format, de ca_m2_ratio_min à ca_m2_ratio_max.
-- Même calcul que business_case_annuel / business_case (montée en charge, EBITDA cumulé). Seuil inchangé :
-- go_no_go.payback_pessimiste_max_mois. Lecture : pour un nombre d'ETP donné, GO si CA/m² >=
-- ca_m2_ratio_min_go ; pour un CA/m² donné, GO si ETP <= etp_max_go (vide = jamais GO dans la grille).
CREATE OR REPLACE VIEW sensibilite_payback AS
WITH p AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'sensibilite_payback.etp_min') AS etp_min,
        max(valeur) FILTER (WHERE parametre = 'sensibilite_payback.etp_pas') AS etp_pas,
        max(valeur) FILTER (WHERE parametre = 'sensibilite_payback.ca_m2_ratio_min') AS ratio_min,
        max(valeur) FILTER (WHERE parametre = 'sensibilite_payback.ca_m2_ratio_max') AS ratio_max,
        max(valeur) FILTER (WHERE parametre = 'sensibilite_payback.ca_m2_ratio_pas') AS ratio_pas,
        max(valeur) FILTER (WHERE parametre = 'go_no_go.payback_pessimiste_max_mois') AS seuil_mois
    FROM parametres_kpi
),
h AS (
    SELECT h.*
    FROM business_case_hypotheses AS h
    JOIN parametres_kpi_texte AS s ON s.parametre = 'sensibilite_payback.scenario' AND s.valeur = h.scenario
    JOIN parametres_kpi_texte AS f ON f.parametre = 'sensibilite_payback.format' AND f.valeur = h.format
),
etp AS (
    -- grille + ETP exact du magasin type (pour retrouver le résultat du business case)
    SELECT round(p.etp_min + i * p.etp_pas, 2) AS nb_etp
    FROM p, h, range(0, CAST(floor((h.nb_etp - p.etp_min) / p.etp_pas + 1e-9) AS INTEGER) + 1) AS t(i)
    UNION
    SELECT h.nb_etp FROM h
),
ratios AS (
    SELECT round(p.ratio_min + i * p.ratio_pas, 2) AS ratio_ca_m2_vs_france
    FROM p, range(0, CAST(round((p.ratio_max - p.ratio_min) / p.ratio_pas) AS INTEGER) + 1) AS t(i)
),
grille AS (
    SELECT
        h.*,
        etp.nb_etp AS nb_etp_test,
        ratios.ratio_ca_m2_vs_france AS ratio_test,
        h.surface_m2 * h.ca_m2_france_eur * ratios.ratio_ca_m2_vs_france AS ca_croisiere_eur,
        h.surface_m2 * (h.loyer_m2_an_eur + h.charges_m2_an_eur) + etp.nb_etp * h.cout_complet_annuel_etp_eur
            + h.surface_m2 * h.cout_energie_m2_an_eur AS couts_fixes_eur,
        h.surface_m2 * h.cout_amenagement_m2_eur + h.part_fixe_eur + h.budget_marketing_lancement_eur
            AS investissement_eur
    FROM h, etp, ratios
),
annees AS (
    SELECT
        g.nb_etp_test,
        g.ratio_test,
        a.annee,
        g.investissement_eur,
        g.ca_croisiere_eur * CASE a.annee
            WHEN 1 THEN g.montee_an1 WHEN 2 THEN g.montee_an2 WHEN 3 THEN g.montee_an3 ELSE 1 END
            * (g.taux_marge - g.taux_couts_variables) - g.couts_fixes_eur AS ebitda_eur
    FROM grille AS g, LATERAL (SELECT unnest(range(1, g.horizon_annees + 1)) AS annee) AS a
),
cumul AS (
    SELECT
        *,
        sum(ebitda_eur) OVER (PARTITION BY nb_etp_test, ratio_test ORDER BY annee) - investissement_eur
            AS tresorerie_fin
    FROM annees
),
payback AS (
    SELECT
        nb_etp_test,
        ratio_test,
        min((annee - 1) * 12 + (ebitda_eur - tresorerie_fin) * 12.0 / ebitda_eur)
            FILTER (WHERE tresorerie_fin >= 0 AND tresorerie_fin - ebitda_eur < 0) AS payback_mois
    FROM cumul
    GROUP BY nb_etp_test, ratio_test
),
verdicts AS (
    SELECT
        payback.*,
        coalesce(payback.payback_mois <= p.seuil_mois, FALSE) AS est_go
    FROM payback, p
)
SELECT
    h.code_pays,
    h.scenario,
    h.format,
    v.nb_etp_test AS nb_etp,
    v.ratio_test AS ratio_ca_m2_vs_france,
    round(h.ca_m2_france_eur * v.ratio_test, 0) AS ca_m2_eur,
    round(v.payback_mois, 1) AS payback_mois,
    printf('≤ %g mois', p.seuil_mois) AS seuil,
    CASE WHEN v.est_go THEN 'GO' ELSE 'NO-GO' END AS statut_go,
    min(v.ratio_test) FILTER (WHERE v.est_go) OVER (PARTITION BY v.nb_etp_test) AS ca_m2_ratio_min_go,
    max(v.nb_etp_test) FILTER (WHERE v.est_go) OVER (PARTITION BY v.ratio_test) AS etp_max_go,
    abs(v.nb_etp_test - h.nb_etp) < 1e-9 AND abs(v.ratio_test - h.ratio_ca_m2_vs_france) < 1e-9
        AS est_cas_business_case,
    h.origine_donnees
FROM verdicts AS v, h, p;
