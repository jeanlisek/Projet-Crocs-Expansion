# Aurélie Périchon : restitution

**Rôle** : ce que le Comex voit, c'est-à-dire le dashboard et les slides. Le barème leur donne le plus de points : impact décisionnel et dataviz, 35 points.
**À l'oral** : section 1, entreprise et pays (1 min), et section 5, Go/No-Go et next steps (1 min 30).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T11 | Dashboard, 4 pages | Fait (capture de la page 1 à refaire) | T10 (faite : CSV dans `data/gold/exports/`) | Démo |
| T13 | Slides Comex (avec Briac) | Jeudi soir | T8, T11 | Oral |

**Outil** : Power BI (décision D1, prise le 12/11/2026).

> **Contrat `kpi_summary` mis à jour le 12/11/2026** : il a gagné la colonne `origine_donnees` (REEL, SIMULE ou MIXTE), décrite dans `REGLES_COMMUNES.md` (« Contrat entre les tâches »). Elle te sert à afficher la mention « données simulées » là où c'est le cas.

> **Mentions obligatoires**, à afficher sur le dashboard et sur la slide des sources :
>
> - dès qu'un visuel utilise les magasins de chaussures OpenStreetMap (densité concurrentielle) : « Données © les contributeurs d’OpenStreetMap, licence ODbL » ;
> - dès qu'un visuel utilise la population des villes allemandes (densité concurrentielle) : « Population : © Statistisches Bundesamt (Destatis), 2025, reproduction autorisée avec mention de la source » ;
> - dès qu'un visuel utilise les distances routières : « Itinéraires : OSRM, données © les contributeurs d’OpenStreetMap, licence ODbL ».

## Le dashboard

Du général au détail, au plus 7 visuels par page :

1. **Synthèse Comex** : cartes KPI avec leur seuil, verdict Go/No-Go, synthèse IA.
2. **Marché & prix** : taille et croissance du marché, parts de marché, indice prix. Filtre pays.
3. **Où s'implanter** : villes allemandes par score, loyer × densité. Filtres ville et format.
4. **Business case** : payback et point mort par scénario. Filtre scénario.

Sur chaque page, une zone de texte affiche le commentaire de `ai_commentary` correspondant au filtre actif (jointure sur `page` + `valeur_filtre`).

**Règles du cours** : titre explicite sur chaque graphique, axes et légendes, pas de double information, au plus 6 parts dans un camembert, au plus 3 groupes de barres, palette sobre (dégradé pour les quantités, pas de rouge agressif), un même chiffre identique partout. Mention « données simulées » là où c'est le cas.

## Tes fichiers

`dashboard/` (fichier du dashboard + captures), `slides/`.

## Comment commencer sans attendre

T10 est faite : les données du dashboard sont les CSV de `data/gold/exports/`, versionnés. Un `git pull` suffit pour les avoir, sans rien lancer. La section « Importer les exports dans Power BI » ci-dessous dit comment les charger.

Si tu utilises un assistant :
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/aurelie.md`. Je construis le dashboard dans Power BI, à partir des CSV de `data/gold/exports/`. Propose-moi pour chacune des 4 pages : les visuels (type de graphique justifié par l'objectif : comparaison, composition, distribution ou relation), les champs utilisés, les filtres, et l'emplacement du commentaire IA. Respecte les règles de dataviz de ma fiche.

## Importer les exports dans Power BI

Les fichiers sont dans `data/gold/exports/`, un par table ou vue, avec les mêmes noms de colonnes que dans l'entrepôt. `make exports` les réécrit (Jean-Li s'en charge).

| Fichier | Contenu | Lignes au 12/11/2026 |
|---|---|---|
| `kpi_summary.csv` | Tous les KPIs, par pays, avec seuil et statut Go / No-Go (contrat de `REGLES_COMMUNES.md`) | 287 |
| `densite_concurrentielle.csv` | Magasins de chaussures pour 100 000 habitants, 12 villes allemandes (réel) | 12 |
| `distance_hub.csv` | Distance routière au hub le plus proche, 12 villes allemandes (réel) | 12 |
| `dim_pays.csv` | Les 7 pays | 7 |
| `dim_zone_chalandise.csv` | Les 53 villes, dont 12 allemandes | 53 |
| `dim_concurrent.csv` | Les 12 marques et enseignes, Crocs comprise, avec leur nom | 12 |
| `dim_produit.csv` | Le catalogue Crocs : modèle, coloris, catégorie, prix France | 147 |
| `dim_temps.csv` | Un mois par ligne, de janvier 2019 à décembre 2029 | 132 |
| `fact_marche.csv` | Taille et croissance du marché par pays, année et segment | 154 |
| `fact_parts_de_marche.csv` | Parts de marché par pays, année et concurrent | 420 |
| `fact_immobilier.csv` | Loyers et charges par ville, année et type d'emplacement | 1 060 |
| `fact_prix_releves.csv` | Relevés de prix par pays, enseigne et produit (simulé) | 4 153 |
| `business_case.csv` | Business case Allemagne : une ligne par scénario (pessimiste, central, optimiste) et par format | 6 |
| `city_scoring.csv` | Score et rang des 12 villes allemandes, villes prioritaires | 12 |
| `sensibilite_payback.csv` | Payback du magasin type (scénario pessimiste, centre commercial) selon le nombre d'ETP et le CA/m² : grille pour une carte de chaleur | 1 519 |
| `eurostat_series.csv` | Séries annuelles Eurostat par pays et indicateur (dépenses en chaussures, prix, population, chômage...), réelles | 463 |
| `crocs_produits.csv` | Prix relevés sur crocs.fr et crocs.de, par modèle et coloris, le 12/11/2026, réels | 577 |
| `ai_commentary.csv` | Commentaires générés par IA, un par page et valeur de filtre, avec la synthèse Comex | 23 |
| `kpi_guide.csv` | Guide des KPI : une ligne par KPI de `kpi_summary` (jointure sur `kpi_summary[kpi]` = `kpi_guide[nom]`), avec définition, formule, unité HT / TTC, périmètre, source, origine et seuil ; pour une infobulle ou une page d'aide | 79 |

`ai_commentary.csv` (T9) contient 23 textes : la synthèse Comex (`page` = « Synthèse Comex »), un commentaire par pays (« Marché & prix »), par ville allemande (« Où s'implanter ») et par scénario (« Business case »). `make exports` le copie tel quel depuis `data/gold/ai_commentary.csv`. La colonne `verifie` vaut `true` quand chaque chiffre du texte a été retrouvé dans les données par le garde-fou de T9 : n'afficher que ces textes.

### Format des fichiers

| Réglage | Valeur |
|---|---|
| Encodage | UTF-8, sans BOM |
| Séparateur de colonnes | virgule |
| Séparateur décimal | point (`97.96`) |
| Dates | `AAAA-MM-JJ` |
| Booléens | `True` / `False` |
| Valeur manquante | cellule vide |
| Première ligne | noms de colonnes |

### Étapes

Les libellés des menus peuvent varier un peu selon la version de Power BI Desktop.

1. **Avant le premier import**, régler la lecture des nombres : Fichier > Options et paramètres > Options > Fichier actif > Paramètres régionaux > « Paramètres régionaux pour l'importation » = **Anglais (États-Unis)**. Sans cela, un Power BI en français lit mal le point décimal (`97.96` devient du texte, ou une date).
2. Accueil > Obtenir des données > Texte/CSV, puis choisir un fichier de `data/gold/exports/`.
3. Dans la fenêtre d'aperçu, vérifier **Origine du fichier = 65001 : Unicode (UTF-8)** et **Délimiteur = Virgule**. Si les accents s'affichent mal (`Ã©` au lieu de `é`), c'est que l'origine du fichier n'est pas sur 65001.
4. Cliquer sur « Transformer les données » et vérifier les types : `valeur` et les colonnes de prix, loyers et distances en nombre décimal, `annee` en nombre entier, `est_simule` en vrai/faux. `seuil` reste du texte (`≥ 80 %`). `id_date` de `fact_prix_releves` est un mois au format `AAAAMM`.
5. Recommencer pour chaque fichier, puis « Fermer et appliquer ».
6. Après un `git pull` qui met les CSV à jour : Accueil > Actualiser.

### Relations entre les tables

À créer dans la vue Modèle. Toutes vont de la dimension (côté 1) vers la table de faits (côté plusieurs), avec un filtrage croisé à sens unique. Si Power BI en a détecté d'autres automatiquement, les supprimer.

| Côté 1 | Côté plusieurs | Colonnes |
|---|---|---|
| `dim_pays` | `kpi_summary` | `code_pays` = `pays` |
| `dim_pays` | `dim_zone_chalandise` | `code_pays` |
| `dim_pays` | `fact_marche` | `code_pays` |
| `dim_pays` | `fact_parts_de_marche` | `code_pays` |
| `dim_pays` | `fact_prix_releves` | `code_pays` |
| `dim_zone_chalandise` | `fact_immobilier` | `id_zone` |
| `dim_zone_chalandise` | `densite_concurrentielle` | `id_zone` (une ligne par ville allemande : Power BI propose une relation 1 à 1) |
| `dim_zone_chalandise` | `distance_hub` | `id_zone` (idem) |
| `dim_concurrent` | `fact_parts_de_marche` | `id_concurrent` |
| `dim_concurrent` | `fact_prix_releves` | `id_concurrent` |
| `dim_produit` | `fact_prix_releves` | `id_produit` |
| `dim_temps` | `fact_prix_releves` | `id_date` |
| `dim_pays` | `business_case` | `code_pays` |
| `dim_pays` | `sensibilite_payback` | `code_pays` |
| `dim_pays` | `eurostat_series` | `code_pays` |
| `dim_pays` | `crocs_produits` | `code_pays` = `site` |
| `dim_zone_chalandise` | `city_scoring` | `id_zone` (une ligne par ville allemande : relation 1 à 1) |

- Les filtres pays et ville se posent sur `dim_pays[nom_pays]` et `dim_zone_chalandise[ville]`, jamais sur la colonne d'une table de faits : c'est ce qui fait réagir tous les visuels d'une page au même filtre.
- `ai_commentary` n'aura pas de relation : la zone de texte se filtre sur `page` et `valeur_filtre`.
- Le nom d'un concurrent se lit dans `dim_concurrent[nom_concurrent]`, celui d'un mois ou d'une saison dans `dim_temps`.
- `id_produit` est vide sur 1 157 des 4 153 relevés de prix : ce sont les produits des concurrents, absents du catalogue Crocs. Power BI les range sous une ligne « (Vide) » de `dim_produit` ; leur libellé reste dans `fact_prix_releves[libelle_produit]`.
- **Tables annuelles** (`fact_marche`, `fact_parts_de_marche`, `fact_immobilier`) : elles ont une colonne `annee`, alors que `dim_temps` a une ligne par mois. `annee` n'y est donc pas unique et Power BI refuse une relation 1 à plusieurs sur cette colonne. Deux façons de faire : utiliser directement la colonne `annee` de la table de faits comme axe du visuel, ou, pour un filtre année commun à plusieurs tables, créer une table d'années dans Power BI (Modélisation > Nouvelle table : `dim_annee = DISTINCT(dim_temps[annee])`) et la relier en 1 à plusieurs à la colonne `annee` de chacune de ces tables.
- **`eurostat_series`** mélange onze indicateurs dans la même colonne `valeur` : filtrer toujours sur `indicateur` (par exemple `depenses_menages_chaussures_meur`) avant d'afficher ou d'additionner. `statut_eurostat` = `p` signale une valeur provisoire (toutes les valeurs allemandes des dépenses en chaussures de 2022 à 2025). Le Royaume-Uni n'a presque pas de données Eurostat.
- **`crocs_produits`** : dans l'éditeur Power Query, passer `code_modele` et `code_coloris` en **Texte**, sinon Power BI lit `001` comme le nombre 1 et les paires FR / DE ne se retrouvent plus. Une paire FR / DE = même `code_modele` et même `code_coloris` ; seules les lignes `disponible` = vrai sont comparables.
- **`sensibilite_payback`** se lit en carte de chaleur : `nb_etp` en lignes, `ratio_ca_m2_vs_france` en colonnes, `statut_go` en couleur. La ligne `est_cas_business_case` = vrai est le magasin type du business case.
- La mention « données simulées » se pilote avec `est_simule` (tables) et `origine_donnees` (`kpi_summary`, `densite_concurrentielle`, `distance_hub`, `business_case`, `city_scoring`, `sensibilite_payback`).

## Les slides (7 à 9)

1. Crocs France, 48 magasins, la question du Comex
2. Modèle de données et sources (réel vs simulé)
3. Les 5 axes et leurs KPIs, seuils fixés à l'avance
4. Marché & prix : le plafond de CA allemand
5. Où s'implanter : villes prioritaires
6. Business case : 3 scénarios
7. Brique IA : capture et garde-fous
8. **Recommandation Go/No-Go**, conditions de succès, next steps
9. (Annexe) Limites et biais assumés

Une question business par slide, un message lisible en 3 secondes.
