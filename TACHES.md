# Répartition des tâches

> **Avant chaque session : `git checkout develop && git pull`.** Les fiches sont mises à jour au fil de l'eau ; copiez toujours les messages depuis GitHub, pas depuis une ancienne copie.

**Chaque membre commence par sa fiche** : [`docs/equipe/`](docs/equipe/).

Les numéros sont des identifiants ; l'ordre est donné par les phases.

> **Échéance : oral le vendredi 13/11.** Bilan intermédiaire jeudi à 18h30.
> Répartition proposée, à ajuster selon les profils de chacun.

## Règles d'équipe

- Une branche par tâche : `feature/<id>-<nom>` (ex. `feature/T3-scraping-crocs`), créée depuis `develop`.
- `git pull origin develop` avant de commencer, merge dans `develop` dès que la tâche est finie et que les tests passent.
- Personne ne pousse sur `main`. Jean-Li merge `develop` → `main` jeudi soir puis vendredi matin.
- Chaque chiffre affiché (dashboard, slides) vient d'une vue gold. Jamais de chiffre recopié à la main.
- **Gel des fonctionnalités jeudi 23h.** Vendredi, on ne corrige que des bugs et les slides.

## Décisions à prendre maintenant, tous ensemble (15 min)

| # | Décision | Proposition |
|---|---|---|
| D1 | Outil de dashboard | **Décidé le 12/11/2026 : Power BI.** (Proposition de départ : Power BI si au moins un membre a Windows, sinon Looker Studio) |
| D2 | Seuils Go / No-Go | Ceux du README (section 4.2) |
| D3 | Recalibrage de la rentabilité magasin | Oui (voir l'audit, point 1) |
| D4 | Sources réelles | Eurostat (T4), prix et catalogue crocs.fr / crocs.de (T3), OpenStreetMap (T16, T17), taxes officielles (T18) |

## Tâches

Les phases suivent l'ordre de la démarche du cours.

### 1. Collecte

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T2 | Recalibrer `generate_data.py` : CA/m² réaliste, charges, `date_fermeture` | Alexis | T1 | Payback médian France entre 1 et 4 ans ; contrôles de cohérence à 0 écart | Fait |
| T3 | Scraping des prix Crocs FR / DE (`robots.txt` vérifié d'abord) ; part du catalogue France présente sur crocs.de, par catégorie | Mehdi | T1 | Snapshots datés dans `data/bronze/` ; au moins 30 SKU appariés ; KPI « % catalogue éligible » réel par catégorie | Fait (128 paires FR/DE, 100 % du catalogue France présent sur crocs.de ; `kpi_indice_prix` et `kpi_catalogue_eligible` lisent ces tables pour l'Allemagne) |
| T4 | API Eurostat → `dim_pays` réel ; dépenses des ménages en chaussures et commerce de détail de chaussures (NACE 47.72) pour les mêmes pays | Mehdi | T1 | `dim_pays` alimenté par l'API, source et date dans les métadonnées ; codes des jeux de données Eurostat vérifiés et notés | À faire |
| T16 | OpenStreetMap (API Overpass) : magasins `shop=shoes` par ville allemande de `dim_zone_chalandise`, avec `brand` quand elle existe | Jean-Li | T1 | Fichier daté dans `data/bronze/` ; densité pour 100 000 habitants par ville | Fait |
| T17 | Coordonnées réelles des hubs et des villes cibles ; distances routières via OSRM | Jean-Li | T1 | Serveur public, requêtes espacées ; résultats en cache dans `data/bronze/` | Fait |
| T18 | Référentiel des taxes saisi à la main : TVA standard, TVA réduite chaussures enfant si elle existe, impôt sur les sociétés, droit de douane UE pour les chaussures (chapitre 64) | Briac | — | `data/manual/taxes_reference.csv` : une ligne par pays, avec `source_url` et `date_consultation` ; rien d'inventé | À faire |

### 2. Préparation

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T5 | Bronze → silver : nettoyage + journal | Jean-Li | T3, T4, T16, T17, T18 | `docs/JOURNAL_NETTOYAGE.md` : anomalie → décision → justification | Fait (squelette, tables réelles à brancher) |

### 3. Modélisation

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T6 | Silver → gold dans DuckDB + tests de qualité | Jean-Li | T2, T5 | `tests/test_qualite_gold.py` passe : unicité, intégrité, validité, cohérence | Fait |

### 4. Analyse

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T7 | Vues KPI (les 14 du README) | Alexis | T6 | Une vue SQL par KPI + `kpi_summary` (valeur, seuil, statut Go/No-Go) | Fait |
| T8 | Business case Allemagne : compte de résultat magasin, 3 scénarios, scoring des villes | Alexis | T7 | Vues `business_case` et `city_scoring` ; hypothèses dans `config/hypotheses.yaml` | Fait (sensibilité du payback, population Destatis et référence France mergées le 12/11/2026 ; voir `docs/ENSEIGNEMENTS.md`, section 4) |
| T9 | Brique IA : commentaires par valeur de filtre + synthèse Comex | Briac | T7 | Table `ai_commentary` ; chaque chiffre cité est vérifié par code | À faire |

### 5. Restitution

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T10 | Exports pour le dashboard | Jean-Li | T7, T9 | CSV ou Parquet dans `data/gold/exports/` | Fait (`make exports` ; `business_case`, `city_scoring` et `ai_commentary` s'exportent dès qu'ils existent) |
| T11 | Dashboard : 4 pages, template homogène | Aurélie | T10 (maquette dès maintenant) | Les filtres pays / ville / scénario changent les visuels **et** le commentaire IA | À faire |
| T12 | Dictionnaire champ par champ | Mehdi | T6 | `docs/DICTIONNAIRE_CHAMPS.md` au format du cours | Fait (généré par `python -m src.collect.dictionnaire` ; les vues sont listées avec leur définition, sans détail champ par champ) |
| T13 | Slides Comex (7 à 9 slides) | Aurélie + Briac | T8, T11 | Une question business par slide, recommandation lisible en 3 secondes | À faire |
| T14 | README final : Next steps, recommandation, liens | Jean-Li | T13 | Toutes les sections du sujet sont remplies | À faire |
| T15 | Répétition chronométrée | Tous | T13 | 10 minutes tenues, démo live testée | À faire |

### Transverse

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T1 | Dépôt : arborescence, `develop`, CI, `Makefile`, `requirements.txt` | Jean-Li | — | La CI passe au vert sur `develop` | Fait |

## Planning

| Créneau | Jean-Li | Mehdi | Alexis | Briac | Aurélie |
|---|---|---|---|---|---|
| Jeudi, avant 18h30 | T1, T5 et T6 (faits) ; T16, T17 | T3, T4 | T2 | T18 ; prompts et garde-fous de T9 sur des KPIs factices | Maquette du dashboard (T11) sur le jeu v1 |
| **18h30 : bilan intermédiaire** | Présente l'état d'avancement | | | | |
| Jeudi soir | Tables réelles branchées en silver (T5), T10 | T12 | T7, T8 | T9 branchée sur les vraies vues | T11 branché, début de T13 |
| Vendredi matin | T14, merge `main` | Relecture du README | Contrôle des chiffres slides vs dashboard | T13 | T13 |
| Vendredi | **T15 : répétition**, puis oral | | | | |

T16, T17 et T18 se font jeudi après-midi, avant 18h30, en parallèle de T3 et T4.

## Le dashboard (T11)

Quatre pages, du général au détail (méthode entonnoir du cours), au plus 7 visuels par page :

1. **Synthèse Comex** : cartes KPI avec leur seuil, verdict Go / No-Go, synthèse IA.
2. **Marché & prix** : taille et croissance du marché, parts de marché, indice prix. Filtre pays.
3. **Où s'implanter** : villes allemandes classées par score, loyer × densité concurrentielle. Filtres ville et format.
4. **Business case** : payback et point mort par scénario. Filtre scénario.

**Commentaires IA adaptatifs.** La table `ai_commentary` contient un commentaire par combinaison (page × valeur de filtre). Le dashboard affiche celui qui correspond au filtre actif. Quand on change de pays pendant la démo, le commentaire change.

Règles de dataviz du cours : titre explicite sur chaque graphique, pas de double information, au plus 6 parts dans un camembert, au plus 3 groupes de barres, palette sobre, un chiffre identique partout où il apparaît.

## L'oral (10 minutes)

| Temps | Section | Barème | Qui |
|---|---|---|---|
| 1 min | Entreprise & pays cible | Contexte | Aurélie |
| 1 min 30 | Base de données & cadrage | Modélisation (20) + Sources (15) | Mehdi |
| 2 min | Pourquoi ces KPIs | Choix des KPIs (30) | Alexis |
| 3 min | Analyse, dataviz, démo de la brique IA | Impact décisionnel & dataviz (35) | Jean-Li + Briac |
| 1 min 30 | Go / No-Go, conditions de succès, next steps | Défense des arbitrages (15) | Aurélie |

## Les slides (T13)

1. Crocs France, 48 magasins, la question du Comex
2. Le modèle de données et les sources (réel vs simulé)
3. Les 5 axes et leurs KPIs, avec les seuils fixés à l'avance
4. Marché & prix : le plafond de CA allemand
5. Où s'implanter : les villes prioritaires
6. Business case : 3 scénarios
7. La brique IA (capture et principe des garde-fous)
8. **Recommandation Go / No-Go**, conditions de succès, next steps
9. (Annexe) Limites et biais assumés
