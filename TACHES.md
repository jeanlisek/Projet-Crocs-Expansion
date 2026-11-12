# Répartition des tâches

**Chaque membre commence par sa fiche** : [`docs/equipe/`](docs/equipe/).

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
| D1 | Outil de dashboard | Power BI si au moins un membre a Windows, sinon Looker Studio |
| D2 | Seuils Go / No-Go | Ceux du README (section 4.2) |
| D3 | Recalibrage de la rentabilité magasin | Oui (voir l'audit, point 1) |
| D4 | Sources réelles | Eurostat + prix crocs.fr / crocs.de ; OpenStreetMap si le temps le permet |

## Tâches

| ID | Tâche | Responsable | Dépend de | Fini quand | Statut |
|---|---|---|---|---|---|
| T1 | Dépôt : arborescence, `develop`, CI, `Makefile`, `requirements.txt` | Jean-Li | — | La CI passe au vert sur `develop` | Fait |
| T2 | Recalibrer `generate_data.py` : CA/m² réaliste, charges, `date_fermeture` | Alexis | T1 | Payback médian France entre 1 et 4 ans ; contrôles de cohérence à 0 écart | À faire |
| T3 | Scraping des prix Crocs FR / DE (`robots.txt` vérifié d'abord) | Mehdi | T1 | Snapshots datés dans `data/bronze/` ; au moins 30 SKU appariés | À faire |
| T4 | API Eurostat → `dim_pays` réel | Mehdi | T1 | `dim_pays` alimenté par l'API, source et date dans les métadonnées | À faire |
| T5 | Bronze → silver : nettoyage + journal | Jean-Li | T3, T4 | `docs/JOURNAL_NETTOYAGE.md` : anomalie → décision → justification | Fait (squelette, tables réelles à brancher) |
| T6 | Silver → gold dans DuckDB + tests de qualité | Jean-Li | T2, T5 | `tests/test_qualite_gold.py` passe : unicité, intégrité, validité, cohérence | À faire |
| T7 | Vues KPI (les 14 du README) | Alexis | T6 | Une vue SQL par KPI + `kpi_summary` (valeur, seuil, statut Go/No-Go) | À faire |
| T8 | Business case Allemagne : compte de résultat magasin, 3 scénarios, scoring des villes | Alexis | T7 | Vues `business_case` et `city_scoring` ; hypothèses dans `config/hypotheses.yaml` | À faire |
| T9 | Brique IA : commentaires par valeur de filtre + synthèse Comex | Briac | T7 | Table `ai_commentary` ; chaque chiffre cité est vérifié par code | À faire |
| T10 | Exports pour le dashboard | Jean-Li | T7, T9 | CSV ou Parquet dans `data/gold/exports/` | À faire |
| T11 | Dashboard : 4 pages, template homogène | Aurélie | T10 (maquette dès maintenant) | Les filtres pays / ville / scénario changent les visuels **et** le commentaire IA | À faire |
| T12 | Dictionnaire champ par champ | Mehdi | T6 | `docs/DICTIONNAIRE_CHAMPS.md` au format du cours | À faire |
| T13 | Slides Comex (7 à 9 slides) | Aurélie + Briac | T8, T11 | Une question business par slide, recommandation lisible en 3 secondes | À faire |
| T14 | README final : Next steps, recommandation, liens | Jean-Li | T13 | Toutes les sections du sujet sont remplies | À faire |
| T15 | Répétition chronométrée | Tous | T13 | 10 minutes tenues, démo live testée | À faire |

## Planning

| Créneau | Jean-Li | Mehdi | Alexis | Briac | Aurélie |
|---|---|---|---|---|---|
| Jeudi, avant 18h30 | T1, puis T5 | T3, T4 | T2 | Prompts et garde-fous de T9 sur des KPIs factices | Maquette du dashboard (T11) sur le jeu v1 |
| **18h30 : bilan intermédiaire** | Présente l'état d'avancement | | | | |
| Jeudi soir | T6, T10 | T12 | T7, T8 | T9 branchée sur les vraies vues | T11 branché, début de T13 |
| Vendredi matin | T14, merge `main` | Relecture du README | Contrôle des chiffres slides vs dashboard | T13 | T13 |
| Vendredi | **T15 : répétition**, puis oral | | | | |

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
