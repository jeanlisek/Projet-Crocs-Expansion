# Audit du jeu de données v1 (`crocs_dataset.zip`)

> Audit réalisé le 12/11/2026 sur `generate_data.py` (seed 2027), les 19 tables CSV et `DICTIONNAIRE_DONNEES.md`.
> Objectif : savoir ce qu'on garde, ce qu'on corrige avant l'oral, et ce qu'on assume comme limite.

## Verdict

**Bonne base, à garder.** Le modèle en constellation est propre, les clés sont cohérentes et les calculs internes bouclent. Les ordres de grandeur sont calibrés sur des sources citées, et le benchmark sur 6 pays est un vrai plus.

Trois problèmes doivent être corrigés avant l'oral, sinon ils coûtent des points :

1. La rentabilité des magasins est irréaliste.
2. 100 % des données sont simulées.
3. Les données sont trop propres pour raconter un nettoyage.

## Ce qui est solide

| Point | Constat |
|---|---|
| Modèle | Constellation : 12 tables de faits, 7 dimensions partagées (`dim_pays`, `dim_temps`, `dim_produit`…), clés explicites |
| Intégrité référentielle | 0 clé orpheline dans `fact_ventes_france` (produit, magasin, date) |
| Unicité | 0 doublon au grain mois × magasin × produit |
| Cohérence des calculs | 0 écart sur les contrôles TTC/1,2 = HT, HT − coût = marge, brut − remise = net |
| Reproductibilité | Seed fixe 2027, script déterministe |
| Valeurs nulles justifiées | Pas de salaire minimum légal en Italie → `NULL` conservé, c'est correct ; 1 184 relevés de prix concurrents sans `id_produit` (produits hors catalogue Crocs), c'est normal |
| Traçabilité | Sources de calibrage citées (Eurostat, TARIC, Cushman & Wakefield, 10-K Crocs) |
| Benchmark | 6 pays candidats, ce qui permet de justifier le choix de l'Allemagne |

## Problèmes, par gravité

### 🔴 1. Des magasins France trop rentables

Médianes 2025 calculées sur le jeu v1, par format :

| Format | CA HT / magasin | CA HT / m² | Taux de marge brute | Résultat magasin* | Payback |
|---|---|---|---|---|---|
| Centre commercial | 1,06 M€ | 8 974 € | 70 % | 441 k€ | 6 mois |
| Centre-ville | 1,18 M€ | 12 165 € | 70 % | 568 k€ | 4 mois |
| Gare / aéroport | 1,23 M€ | 18 877 € | 70 % | 544 k€ | 3 mois |
| Outlet | 0,77 M€ | 5 000 € | 60 % | 199 k€ | 19 mois |

*Marge brute − loyer − personnel − énergie. Il manque les autres coûts du magasin.

**Pourquoi c'est grave.** Avec un retour sur investissement en 3 à 6 mois, le Go est acquis d'avance. Il n'y a plus d'arbitrage à défendre, alors que la défense des arbitrages vaut 15 points. Ces chiffres sont aussi très au-dessus des ordres de grandeur habituels du commerce de chaussures spécialisé : un jury qui connaît le retail le verra.

**Correction.**
- Recalibrer `generate_data.py` (CA par magasin plus bas, ou surfaces plus grandes) et vérifier l'ordre de grandeur du CA/m² sur une source publique.
- Construire un compte de résultat magasin complet : loyer **+ charges** (déjà dans `fact_immobilier`), personnel, énergie, marketing de lancement, logistique par unité, démarque, frais bancaires, frais de siège, amortissement de l'investissement. Les hypothèses vont dans `config/hypotheses.yaml`.
- Présenter le business case Allemagne en **3 scénarios** (pessimiste, central, optimiste) sur la montée en charge. « Même dans le scénario pessimiste, le payback reste sous X mois » est une phrase qui se défend.

### 🔴 2. Tout est simulé, y compris ce qui s'appelle « scraping »

`fact_prix_releves` est présenté comme du scraping, mais il est simulé. Or la mission demande « d'identifier, collecter, structurer et **automatiser** », et le cours dit que le scraping est préféré à la génération. La partie Sources vaut 15 points.

**Correction.** Remplacer trois sources simulées par du réel et garder le simulé pour l'interne :

| Table | Source réelle | Effort |
|---|---|---|
| `dim_pays` (population, PIB/hab SPA, chômage, niveaux de prix) | API Eurostat | Faible |
| `fact_prix_releves`, partie Crocs | Scraping crocs.fr / crocs.de (respect du `robots.txt`) | Moyen |
| `dim_zone_chalandise.densite_concurrentielle` | OpenStreetMap, API Overpass (`shop=shoes`) | Moyen |

Restent simulés, et c'est légitime : ventes, magasins, coûts internes, tailles de marché (Euromonitor et Statista sont payants).

**Règle d'honnêteté :** toute table simulée est étiquetée « simulée » partout (README, dashboard, slides).

### 🟠 3. Des données trop propres

`fact_ventes_france` compte 0 valeur nulle, 0 doublon et 0 valeur aberrante. Le cours insiste sur le passage bronze → silver (doublons, formats, valeurs manquantes, quartiles), mais il n'y a ici rien à nettoyer.

**Correction.** Les sources réelles du point 2 apporteront naturellement du nettoyage : prix au format `49,99 €`, produits en double, villes mal orthographiées. Tenir un **journal de nettoyage** (`docs/JOURNAL_NETTOYAGE.md`) : ce qui a été trouvé, la décision prise, la justification métier.

### 🟠 4. Part de marché et CA du réseau ne parlent pas du même périmètre

En France, `fact_parts_de_marche` attribue à Crocs 254,6 M€ en 2025, alors que les ventes du réseau totalisent 67 M€ HT. Sans explication, c'est une incohérence que le jury relèvera.

**Correction.** Ajouter une règle de gestion : la part de marché couvre **la marque, tous canaux confondus** (y compris les revendeurs), alors que le CA couvre **le réseau intégré** (48 magasins + crocs.fr). Cela renforce d'ailleurs le scénario : en Allemagne, la marque pèse déjà 13,9 % du segment via des revendeurs. La question devient « faut-il passer du wholesale à un réseau en propre ? ».

### 🟠 5. L'Allemagne n'est pas gagnante sur tous les axes

Aperçu des KPIs sur le jeu v1, **indicatif** (tout est simulé) :

| Pays | Marché 2025 (M€) | TCAM 2022-25 | Indice prix HT (FR=100) | Distance hub (km) | Densité concurrents /100k hab | Loyer centre commercial (€/m²/an) | Coût d'un ETP (€/an) | % catalogue éligible | Pénétration sabots |
|---|---|---|---|---|---|---|---|---|---|
| **DE** | **6 464** | **3,7 %** | **100,2** | **515** | **6,7** | **658** | **38 569** | **98 %** | **11,1 %** |
| ES | 3 465 | 4,6 % | 99,1 | 1 310 | 6,4 | 555 | 26 300 | 97 % | 15,6 % |
| IT | 5 017 | 2,9 % | 98,4 | 768 | 6,6 | 739 | 30 062 | 81 % | 12,1 % |
| BE | 1 068 | 3,7 % | 99,2 | 148 | 5,9 | 380 | 38 100 | 98 % | 12,5 % |
| NL | 1 608 | 3,8 % | 99,1 | 90 | 6,5 | 494 | 37 362 | 98 % | 10,6 % |
| GB | 7 035 | 4,2 % | 105,9 | 663 | 6,3 | 766 | 30 906 | 91 % | 13,0 % |

L'Allemagne est le plus gros marché de l'UE, mais elle a les coûts salariaux les plus élevés, une forte densité concurrentielle et une pénétration des sabots faible. **Il ne faut pas forcer le résultat.** C'est un excellent matériau pour la défense des arbitrages : « on choisit le plus gros plafond de CA, au prix de coûts plus élevés, avec ces conditions de succès ».

### 🟡 6. Points de méthode

- **2026 est partiel** (janvier à octobre). Toute comparaison 2026 vs 2025 doit porter sur janvier-octobre des deux années.
- **Indice prix** : seulement 15 SKU appariés par pays, relevés trimestriels. Calculer l'indice sur un panier identique de SKU, en HT, hors promotions. La formule actuelle du dictionnaire (« moyenne pays ÷ moyenne France ») est sensible au mix produit (référentiel, fiche 1.5).
- **Taux agrégés** : toujours recalculés depuis numérateurs et dénominateurs, jamais moyennés (référentiel, fiche 1.3).
- **CA/m²** : comparable uniquement à format identique (référentiel, fiche 4.3).
- **Pas de `date_fermeture`** dans `dim_magasin` : tous les magasins sont ouverts, d'où un biais de survie à mentionner (référentiel, fiche 4.1).
- Le **référentiel** vise un périmètre e-commerce (sessions web, stock, clients) que le jeu v1 ne couvre pas. Ce n'est pas nécessaire pour la question du Comex : à classer en roadmap, pas à construire.

### 🟡 7. Ce qui manque encore (normal à ce stade)

`generate_data.py` est un script unique de 44 Ko, sans tests ni pipeline. Il n'y a pas encore de couche gold, de calcul des KPIs, de dashboard, de brique IA ni de slides. C'est l'objet de `TACHES.md`.

## Utiliser le référentiel analytique

Il est très bon. À reprendre explicitement :

| Partie | Usage dans le projet |
|---|---|
| 0.1 Statuts FAIT / CALCUL / HYPOTHÈSE / CONVENTION | Chaque KPI du README porte son statut |
| 1.2 – 1.5 Anatomie d'un taux, non-additivité, composition | Règles de calcul des KPIs |
| 2.6 Valeurs aberrantes | Méthode IQR du journal de nettoyage |
| 4.3 Productivité, coût d'occupation | Business case magasin |
| 7 Biais et pièges | Checklist avant publication du dashboard |
| 8.1 Dimensions de qualité | Tests automatiques `tests/test_qualite_gold.py` |
