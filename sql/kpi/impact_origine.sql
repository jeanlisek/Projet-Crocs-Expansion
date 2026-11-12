-- Levier d'origine : droit de douane UE sur les chaussures selon le pays de fabrication.
-- Produits du code SH impact_origine.code_sh (6402.99) : le jeu simulé leur applique son propre droit
-- (taux_droit_ue_pct de dim_produit). On le remplace par le droit réel, calculé comme le simulé sur la
-- valeur FOB + fret :
--   - droit_tiers_reel : 16,8 % pour tous (taxes_reference, droit de pays tiers TARIC) ;
--   - preference_vietnam : 0 % pour les produits fabriqués au Vietnam (TARIC, préférence tarifaire
--     de l'accord UE-Vietnam), 16,8 % pour les autres.
-- simule (référence) garde le droit du jeu simulé : il doit retrouver le business case tel quel.
-- Coût débarqué = FOB + fret + droit. L'économie de droit, pondérée par les quantités vendues en
-- magasin en France au même format l'année kpi.annee_reference, s'ajoute au taux de marge du
-- business case (business_case_hypotheses), puis le payback est recalculé comme dans business_case
-- (montée en charge, EBITDA cumulé, horizon). Ne modifie ni business_case, ni kpi_summary.
CREATE OR REPLACE VIEW impact_origine AS
WITH p AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'impact_origine.droit_preferentiel_pct') AS droit_pref_pct,
        max(valeur) FILTER (WHERE parametre = 'kpi.annee_reference') AS annee_reference,
        max(valeur) FILTER (WHERE parametre = 'go_no_go.payback_pessimiste_max_mois') AS seuil_mois
    FROM parametres_kpi
),
t AS (
    SELECT
        max(valeur) FILTER (WHERE parametre = 'impact_origine.code_sh') AS code_sh,
        max(valeur) FILTER (WHERE parametre = 'impact_origine.pays_preferentiel') AS pays_pref,
        max(valeur) FILTER (WHERE parametre = 'impact_origine.scenario') AS scenario,
        max(valeur) FILTER (WHERE parametre = 'impact_origine.format') AS format
    FROM parametres_kpi_texte
),
droit_tiers AS (
    -- même droit dans tous les pays de l'union douanière : celui de l'Allemagne, pays étudié
    SELECT droit_douane_ue_chaussures_ch64_pct AS droit_tiers_pct FROM taxes_reference WHERE code_pays = 'DE'
),
cas AS (
    SELECT * FROM (VALUES (1, 'simule'), (2, 'droit_tiers_reel'), (3, 'preference_vietnam')) AS c(ordre, cas_origine)
),
produits AS (
    SELECT
        cas.ordre,
        cas.cas_origine,
        d.id_produit,
        d.pays_origine,
        d.code_sh = t.code_sh AS est_concerne,
        d.cout_fob_eur + d.cout_fret_unitaire_eur AS valeur_en_douane_eur,
        d.cout_debarque_eur AS cout_debarque_simule_eur,
        CASE
            WHEN d.code_sh <> t.code_sh OR cas.cas_origine = 'simule' THEN d.taux_droit_ue_pct
            WHEN cas.cas_origine = 'preference_vietnam' AND d.pays_origine = t.pays_pref THEN p.droit_pref_pct
            ELSE droit_tiers.droit_tiers_pct
        END AS taux_droit_pct,
        d.taux_droit_ue_pct AS taux_droit_simule_pct
    FROM dim_produit AS d, cas, t, p, droit_tiers
),
couts AS (
    SELECT
        *,
        valeur_en_douane_eur * (1 + taux_droit_pct / 100) AS cout_debarque_eur,
        valeur_en_douane_eur * (taux_droit_simule_pct - taux_droit_pct) / 100 AS economie_droit_unitaire_eur
    FROM produits
),
ventes AS (
    -- ventes en magasin au format étudié, année de référence (même base que le taux de marge France)
    SELECT v.id_produit, sum(v.quantite_vendue) AS quantite, sum(v.ca_net_ht_eur) AS ca_ht_eur
    FROM fact_ventes_france AS v
    JOIN magasins_france_reference AS m ON m.id_magasin = v.id_magasin
    JOIN dim_temps AS d ON d.id_date = v.id_date
    JOIN t ON m.type_emplacement = t.format
    JOIN p ON d.annee = p.annee_reference
    GROUP BY v.id_produit
),
par_cas AS (
    SELECT
        c.ordre,
        c.cas_origine,
        count(*) FILTER (WHERE c.est_concerne) AS nb_produits_concernes,
        count(*) FILTER (WHERE c.est_concerne AND c.pays_origine = t.pays_pref) AS nb_produits_concernes_vietnam,
        sum(v.quantite * c.cout_debarque_eur) / sum(v.quantite) AS cout_debarque_moyen_eur,
        sum(v.quantite * c.economie_droit_unitaire_eur) / sum(v.ca_ht_eur) AS gain_taux_marge
    FROM couts AS c
    JOIN ventes AS v ON v.id_produit = c.id_produit
    CROSS JOIN t
    GROUP BY c.ordre, c.cas_origine, t.pays_pref
),
h AS (
    SELECT bh.* FROM business_case_hypotheses AS bh, t WHERE bh.scenario = t.scenario AND bh.format = t.format
),
annees AS (
    SELECT
        par_cas.ordre,
        par_cas.cas_origine,
        a.annee,
        h.surface_m2 * h.cout_amenagement_m2_eur + h.part_fixe_eur + h.budget_marketing_lancement_eur
            AS investissement_eur,
        h.surface_m2 * h.ca_m2_eur * CASE a.annee
            WHEN 1 THEN h.montee_an1 WHEN 2 THEN h.montee_an2 WHEN 3 THEN h.montee_an3 ELSE 1 END
            * (h.taux_marge + par_cas.gain_taux_marge - h.taux_couts_variables)
            - h.surface_m2 * (h.loyer_m2_an_eur + h.charges_m2_an_eur)
            - h.nb_etp * h.cout_complet_annuel_etp_eur
            - h.surface_m2 * h.cout_energie_m2_an_eur AS ebitda_eur
    FROM par_cas, h, LATERAL (SELECT unnest(range(1, h.horizon_annees + 1)) AS annee) AS a
),
cumul AS (
    SELECT
        *,
        sum(ebitda_eur) OVER (PARTITION BY ordre ORDER BY annee) - investissement_eur AS tresorerie_fin
    FROM annees
),
payback AS (
    SELECT
        ordre,
        min((annee - 1) * 12 + (ebitda_eur - tresorerie_fin) * 12.0 / ebitda_eur)
            FILTER (WHERE tresorerie_fin >= 0 AND tresorerie_fin - ebitda_eur < 0) AS payback_mois,
        max(ebitda_eur) FILTER (WHERE annee = (SELECT max(annee) FROM annees)) AS ebitda_croisiere_eur
    FROM cumul
    GROUP BY ordre
)
SELECT
    h.code_pays,
    h.scenario,
    h.format,
    par_cas.cas_origine,
    par_cas.nb_produits_concernes,
    par_cas.nb_produits_concernes_vietnam,
    (SELECT count(*) FROM dim_produit) AS nb_produits_catalogue,
    round(par_cas.cout_debarque_moyen_eur, 2) AS cout_debarque_moyen_eur,
    round((h.taux_marge + par_cas.gain_taux_marge) * 100, 2) AS taux_marge_pct,
    round(par_cas.gain_taux_marge * 100, 2) AS gain_marge_pts,
    round(payback.ebitda_croisiere_eur, 0) AS ebitda_croisiere_eur,
    round(payback.payback_mois, 1) AS payback_mois,
    printf('≤ %g mois', p.seuil_mois) AS seuil,
    CASE WHEN payback.payback_mois <= p.seuil_mois THEN 'GO' ELSE 'NO-GO' END AS statut_go,
    'MIXTE' AS origine_donnees
FROM par_cas
JOIN payback ON payback.ordre = par_cas.ordre
CROSS JOIN h
CROSS JOIN p
ORDER BY par_cas.ordre;
