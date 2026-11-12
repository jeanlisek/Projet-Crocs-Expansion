-- Comparaison France sur le même périmètre de coûts que le business case Allemagne (T8-sensibilite).
-- Magasins France ouverts toute l'année de référence (magasins_france_reference), formats retenus.
-- Mêmes postes que business_case : loyer + charges, personnel, énergie, coûts variables (démarque,
-- frais bancaires, siège, logistique : mêmes % du CA), amortissement de l'investissement sur la même durée.
-- Charges locatives : absentes du jeu France ; estimées avec le ratio charges / loyer de fact_immobilier
-- pour le même type d'emplacement (toutes villes, année de référence) : HYPOTHÈSE de proxy.
-- Payback : investissement ÷ EBITDA d'un magasin à maturité (pas de montée en charge : magasins
-- établis ; investissement France sans marketing de lancement). Ligne INFO : référence, pas un critère.
CREATE OR REPLACE VIEW business_case_france AS
WITH p AS (
    SELECT
        sum(valeur) FILTER (WHERE parametre LIKE 'business_case_allemagne.couts_additionnels_pct_ca.%') / 100
            AS taux_couts_variables,
        max(valeur) FILTER (WHERE parametre = 'business_case_allemagne.duree_amortissement_capex_ans')
            AS duree_amortissement_ans
    FROM parametres_kpi
),
formats AS (
    SELECT f.valeur AS format, e.valeur AS type_emplacement_immobilier
    FROM parametres_kpi_texte AS f
    JOIN parametres_kpi_texte AS e
        ON e.parametre = 'business_case_allemagne.emplacement_immobilier.' || f.valeur
    WHERE f.parametre LIKE 'business_case_allemagne.formats_retenus.%'
),
ratio_charges AS (
    SELECT type_emplacement, sum(charges_m2_an_eur) * 1.0 / sum(loyer_m2_an_eur) AS ratio_charges_loyer
    FROM kpi_cout_m2
    GROUP BY type_emplacement
),
magasins AS (
    SELECT
        m.type_emplacement AS format,
        count(*) AS nb_magasins,
        sum(m.ca_ht_eur) AS ca,
        sum(m.marge_brute_eur) AS marge,
        sum(m.loyer_annuel_eur) * (1 + r.ratio_charges_loyer) AS loyer_charges,
        sum(m.personnel_eur) AS personnel,
        sum(m.energie_eur) AS energie,
        sum(m.capex_ouverture_eur) AS investissement,
        bool_and(m.est_simule) AS est_simule
    FROM magasins_france_reference AS m
    JOIN formats ON formats.format = m.type_emplacement
    JOIN ratio_charges AS r ON r.type_emplacement = formats.type_emplacement_immobilier
    GROUP BY m.type_emplacement, r.ratio_charges_loyer
),
calcul AS (
    SELECT
        magasins.*,
        p.taux_couts_variables,
        p.duree_amortissement_ans,
        marge - ca * p.taux_couts_variables - loyer_charges - personnel - energie AS ebitda
    FROM magasins, p
)
SELECT
    'FR' AS code_pays,
    format,
    nb_magasins,
    round(ca / nb_magasins, 0) AS ca_ht_moyen_eur,
    round(marge * 100.0 / ca, 2) AS taux_marge_brute_pct,
    round(loyer_charges / nb_magasins, 0) AS loyer_charges_eur,
    round(personnel / nb_magasins, 0) AS personnel_eur,
    round(energie / nb_magasins, 0) AS energie_eur,
    round(ca * taux_couts_variables / nb_magasins, 0) AS couts_variables_eur,
    round(ebitda / nb_magasins, 0) AS ebitda_eur,
    round((ebitda - investissement / duree_amortissement_ans) / nb_magasins, 0) AS resultat_eur,
    round(investissement / nb_magasins, 0) AS investissement_eur,
    round(loyer_charges * 100.0 / ca, 2) AS cout_occupation_pct,
    round((loyer_charges + personnel + energie + investissement / duree_amortissement_ans) / nb_magasins
        / (marge / ca - taux_couts_variables), 0) AS point_mort_ca_ht_eur,
    round(CASE WHEN ebitda > 0 THEN investissement * 12.0 / ebitda END, 1) AS payback_mois,
    CASE WHEN est_simule THEN 'SIMULE' ELSE 'MIXTE' END AS origine_donnees
FROM calcul;
