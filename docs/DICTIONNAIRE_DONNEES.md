# Jeu de données – Crocs France : expansion européenne 2027-2029

> **Données simulées** mais calibrées sur des ordres de grandeur publics (prix publics Crocs, TVA, droits TARIC, loyers prime, salaires minimum 2025-2026). Le script `generate_data.py` est déterministe (seed 2027) : on le relance et on obtient exactement les mêmes fichiers. Avant la soutenance, vérifiez les chiffres « réglementaires » (TVA, IS, droits, SMIC) auprès des sources officielles citées plus bas.

## Hypothèses d'entreprise

| Élément | Valeur |
|---|---|
| Entreprise | Crocs France (réseau intégré, marques Crocs + HEYDUDE) |
| Réseau France (X) | **48 magasins physiques** + 1 canal e-commerce (crocs.fr) |
| Types d'emplacement | Centre-ville, centre commercial, outlet, gare/aéroport |
| Catalogue | 147 SKU (30 modèles × coloris) : sabots, sandales, bottes, Jibbitz, chaussures toile HEYDUDE |
| CA net TTC France | 40 M€ (2023) → 50 M€ (2024) → 53 M€ (2025) |
| Hubs | Moissy-Cramayel (IDF), Saint-Quentin-Fallavier (Lyon) + DC Crocs EMEA Dordrecht (NL) |
| Pays candidats | Allemagne, Espagne, Italie, Belgique, Pays-Bas, Royaume-Uni (la France sert de référence) |
| Historique | ventes de janv. 2023 à oct. 2026, marché 2019-2025, projections 2026-2029 |

## Modèle en constellation (plusieurs tables de faits qui partagent les mêmes dimensions)

```
                       dim_temps
                           │
 dim_magasin ── fact_ventes_france ── dim_produit ── fact_eligibilite_assortiment ── dim_pays
      │                                    │                                           │
 dim_hub_logistique ── fact_logistique ── dim_zone_chalandise ── fact_immobilier       │
                                           │                                           │
                         fact_presence_concurrents ── dim_concurrent ── fact_parts_de_marche
                                                                                       │
     fact_marche · fact_fiscalite · fact_couts_exploitation · fact_penetration_categories
     fact_prix_releves · fact_tendances_recherche  (toutes reliées à dim_pays)
```

Clés : `id_date` (AAAAMM), `id_produit`, `id_magasin`, `code_pays` (ISO-2), `id_zone`, `id_hub`, `id_concurrent`.

## Dimensions

| Table | Grain | Colonnes clés |
|---|---|---|
| `dim_pays` | 1 ligne par pays | population, PIB/hab (SPA, UE=100), chômage, indice niveau de prix chaussures (UE=100), devise, taux de change, membre UE |
| `dim_temps` | mois 2019-2029 | année, trimestre, saison, période de soldes, Black Friday, `est_historique` |
| `dim_produit` | SKU | marque, catégorie, modèle, coloris, cible, prix TTC/HT France, coût FOB, fret, droits UE, **coût débarqué**, code SH, taux de droit UE/UK, origine, taux de marge théorique |
| `dim_magasin` | magasin France | type d'emplacement, surface, loyer annuel, ETP, capex d'ouverture, hub de rattachement, distance au hub |
| `dim_hub_logistique` | entrepôt | localisation, surface, capacité en palettes |
| `dim_zone_chalandise` | ville cible (53 villes) | population de la ville et de la zone, indice de revenu, fréquentation, nb de centres commerciaux, part de touristes, **densité concurrentielle / 100k hab.** |
| `dim_concurrent` | marque | type d'acteur, positionnement prix, prix moyen |

## Faits

| Table | Grain | Mesures |
|---|---|---|
| `fact_ventes_france` | mois × magasin × produit (246 476 lignes) | quantités, CA brut/net TTC, CA net HT, remise, coût des marchandises, marge brute, retours |
| `fact_marche` | pays × année × segment | taille de marché (M€), taux de croissance, `est_projection` |
| `fact_parts_de_marche` | pays × année × marque (segment casual moulé & sandales) | part de marché en valeur (%), CA estimé |
| `fact_presence_concurrents` | zone × concurrent | nb de points de vente, dont magasins en propre |
| `fact_immobilier` | zone × année × type d'emplacement | loyer €/m²/an, charges, taux de vacance |
| `fact_logistique` | hub × zone | distance routière, délai, coût par palette / par unité, frais de dédouanement, CO₂ |
| `fact_fiscalite` | pays | TVA standard et chaussures enfant, IS, éco-contribution, droits à l'import depuis la France, régime douanier |
| `fact_couts_exploitation` | pays (2026) | salaire vendeur, charges patronales, coût complet d'un ETP, aménagement €/m², énergie, budget marketing de lancement |
| `fact_prix_releves` | relevé (trimestriel, scraping simulé) | prix affiché (€ et devise locale), promo, remise. Couvre Crocs et les produits équivalents des concurrents |
| `fact_penetration_categories` | pays × année × catégorie | taux de pénétration (%), panier moyen, taille d'échantillon |
| `fact_eligibilite_assortiment` | pays × produit | éligible, motif d'exclusion, indice de demande locale, recommandation (cœur / optionnel / exclu), adaptation requise |
| `fact_tendances_recherche` | pays × mois | intérêt de recherche « crocs » (0-100, type Google Trends) |

## Calcul des KPIs du sujet

| Axe | KPI | Calcul |
|---|---|---|
| Marché | Croissance annuelle du secteur | `fact_marche.taux_croissance_annuel_pct` (segment casual moulé) |
| Marché | Part de marché France / concurrent dans le pays cible | `fact_parts_de_marche` filtré sur `C00` / sur le concurrent |
| Prix | Indice de prix relatif | moyenne du prix Crocs dans le pays cible ÷ moyenne France × 100 (`fact_prix_releves`, `id_concurrent='C00'`) |
| Prix | Marge brute estimée après taxes | (prix TTC local / (1+TVA) − coût débarqué − transport unitaire − droits UK éventuels) ÷ prix HT |
| Réseau | Densité concurrentielle | `dim_zone_chalandise.densite_concurrentielle_pour_100k_hab` |
| Réseau | Coût moyen au m² commercial | `fact_immobilier.loyer_m2_an_eur` (+ charges) |
| Logistique | Distance moyenne depuis les hubs | moyenne de `fact_logistique.distance_route_km`, en gardant le hub le plus proche de chaque zone |
| Logistique | Droits / taxes locales | `fact_fiscalite` + `dim_produit.taux_droit_uk_pct` |
| Assortiment | Pénétration des catégories | `fact_penetration_categories.taux_penetration_pct` |
| Assortiment | % du catalogue France éligible | nb de produits avec `eligible = True` ÷ 147 |
| Rentabilité | Point mort par magasin | (loyer + ETP × coût complet + énergie) ÷ taux de marge brute, à comparer au CA/m² France × surface |

## Règles de gestion

- Le CA net TTC correspond au CA brut moins les remises (soldes de janvier et juillet, Black Friday, outlet, fins de série). Le CA HT s'obtient en divisant le TTC par 1,20 (TVA France).
- Coût débarqué = FOB (USD × 0,92) + fret + droits de douane UE sur la valeur CAF. Hausses annuelles : +3 % sur les prix de vente, +2 % sur les coûts.
- Dans l'UE, les marchandises circulent librement et les droits ont déjà été payés à l'entrée. Le Royaume-Uni est un pays tiers : les produits fabriqués en Asie n'y ont pas d'origine préférentielle UE, donc des droits UK s'appliquent en plus des formalités de douane. En contrepartie, la TVA sur les chaussures enfant y est à 0 %.
- Les magasins ouverts dans l'année ne génèrent des ventes qu'à partir d'avril. HEYDUDE est en recul (−14 % puis −14 %), Crocs progresse (+6,5 % puis +3 %).
- Les données marquées « Projection » (2026-2029) sont des extrapolations à CAGR constant, pas des observations.

## Sources à citer (sur lesquelles les simulations sont calibrées)

Eurostat (population, PIB, indices de prix PLI, chômage) · Commission européenne TARIC / UK Global Tariff (droits SH 6401-6404, 3926) · Commission européenne, *Taxes in Europe Database* (TVA, IS) · Cushman & Wakefield, *Main Streets Across the World* (loyers prime) · Eurostat (salaires minimum) · Crocs Inc. 10-K 2024-2025 (marges, mix produits, DC de Dordrecht) · Google Trends (indices de recherche) · Euromonitor / Statista (tailles de marché).
