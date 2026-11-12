# Aurélie Périchon : restitution

**Rôle** : ce que le Comex voit, c'est-à-dire le dashboard et les slides. Le barème leur donne le plus de points : impact décisionnel et dataviz, 35 points.
**À l'oral** : section 1, entreprise et pays (1 min), et section 5, Go/No-Go et next steps (1 min 30).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T11 | Dashboard, 4 pages | Maquette maintenant | T10 (faite : CSV dans `data/gold/exports/`) | Démo |
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
| `kpi_summary.csv` | Tous les KPIs, par pays, avec seuil et statut Go / No-Go (contrat de `REGLES_COMMUNES.md`) | 232 |
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
| `fact_prix_releves.csv` | Relevés de prix par pays, enseigne et produit | 4 153 |

`business_case.csv`, `city_scoring.csv` (T8) et `ai_commentary.csv` (T9) apparaîtront dans le même dossier dès que ces tâches seront mergées. Ils n'y sont pas encore.

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

- Les filtres pays et ville se posent sur `dim_pays[nom_pays]` et `dim_zone_chalandise[ville]`, jamais sur la colonne d'une table de faits : c'est ce qui fait réagir tous les visuels d'une page au même filtre.
- `ai_commentary` n'aura pas de relation : la zone de texte se filtre sur `page` et `valeur_filtre`.
- Le nom d'un concurrent se lit dans `dim_concurrent[nom_concurrent]`, celui d'un mois ou d'une saison dans `dim_temps`.
- `id_produit` est vide sur 1 157 des 4 153 relevés de prix : ce sont les produits des concurrents, absents du catalogue Crocs. Power BI les range sous une ligne « (Vide) » de `dim_produit` ; leur libellé reste dans `fact_prix_releves[libelle_produit]`.
- **Tables annuelles** (`fact_marche`, `fact_parts_de_marche`, `fact_immobilier`) : elles ont une colonne `annee`, alors que `dim_temps` a une ligne par mois. `annee` n'y est donc pas unique et Power BI refuse une relation 1 à plusieurs sur cette colonne. Deux façons de faire : utiliser directement la colonne `annee` de la table de faits comme axe du visuel, ou, pour un filtre année commun à plusieurs tables, créer une table d'années dans Power BI (Modélisation > Nouvelle table : `dim_annee = DISTINCT(dim_temps[annee])`) et la relier en 1 à plusieurs à la colonne `annee` de chacune de ces tables.
- La mention « données simulées » se pilote avec `est_simule` (tables) et `origine_donnees` (`kpi_summary`, `densite_concurrentielle`, `distance_hub`).

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
