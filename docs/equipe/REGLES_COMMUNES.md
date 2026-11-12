# Règles communes de l'équipe

> **Avant chaque session : `git checkout develop && git pull`.** Les fiches sont mises à jour au fil de l'eau ; copiez toujours les messages depuis GitHub, pas depuis une ancienne copie.

> À lire par chaque membre **et par son assistant de code** avant toute tâche.
> Chaque membre a sa fiche dans ce dossier : `jean-li.md`, `mehdi.md`, `alexis.md`, `briac.md`, `aurelie.md`.

## Calendrier

| Moment | Ce qui doit être fait |
|---|---|
| Jeudi 18h30 | Bilan intermédiaire : chacun sait dire où il en est en une phrase |
| Jeudi 23h | **Gel des fonctionnalités** : tout est mergé dans `develop` |
| Vendredi matin | Corrections, slides, répétition chronométrée |
| Vendredi | Oral : 10 min + 2 min de questions |

## Installation (une fois)

Voir la section « Lancer le projet » du README (Python 3.11 via `uv`, `make install`, `make simulate`, `make silver`, `make test`). Sous Windows, prévenir Jean-Li.

## État du pipeline

> État au 12/11/2026. **À tenir à jour à chaque merge dans `develop`**, par la personne qui merge.

`make all` enchaîne quatre étapes. La collecte (`make collect`) n'en fait pas partie : ses résultats sont déjà dans le dépôt.

| Étape | Commande | Ce qu'elle produit | Où |
|---|---|---|---|
| 1. Simulation | `make simulate` | Les 19 tables simulées (seed 2027), en CSV. Jeu recalibré par T2 le 12/11/2026 : paramètres des magasins dans `config/hypotheses.yaml`, 3 magasins fermés (`date_fermeture`), zones insulaires signalées (`zone_insulaire`) | `data/bronze/*.csv` |
| 2. Silver | `make silver` | Les tables de `data/bronze/` et de `data/manual/`, typées et contrôlées (doublons, valeurs nulles, valeurs aberrantes), avec les colonnes `est_simule` et `source`, plus le rapport de contrôles | `data/silver/*.parquet`, `data/silver/rapport_controles.csv` |
| 3. Gold | `make gold` | L'entrepôt DuckDB, reconstruit depuis zéro : 23 tables (19 simulées, 4 réelles), 23 clés primaires, 28 relations | `data/gold/warehouse.duckdb` |
| 4. KPI | `make kpi` | Les vues KPI, créées dans l'entrepôt à partir de `sql/kpi/*.sql`. Deux vues à ce jour : `densite_concurrentielle` (T16) et `distance_hub` (T17) | Vues dans `data/gold/warehouse.duckdb` |

Aucun de ces fichiers n'est versionné : chacun les reconstruit chez soi avec `make all`. Deux exceptions en entrée, toutes deux versionnées :

- `data/manual/`, qui contient les saisies manuelles sourcées ;
- les fichiers `osm_*`, `destatis_*` et `osrm_*` de `data/bronze/`. Ce sont des instantanés datés du 12/11/2026 : le serveur Overpass est instable (une requête sur deux en erreur ce jour-là), le classeur Destatis est la pièce officielle d'où viennent les populations, et les serveurs publics OSRM et Nominatim n'acceptent qu'un usage léger. Les versionner évite à chacun de refaire la collecte et garantit que tout le monde calcule sur les mêmes données.

- **Les relations de l'entrepôt** : 23 pour les tables simulées, celles du diagramme du README (section 3.2), et 5 pour les tables réelles (`REAL_RELATIONSHIPS`). Elles sont déclarées en clés étrangères dans `RELATIONSHIPS` (`src/transform/build_gold.py`) : l'entrepôt refuse un doublon ou une clé orpheline.
- **Tables réelles** : elles se déclarent dans le registre `REAL_TABLES` (`src/transform/bronze_to_silver.py`). Quatre y sont à ce jour : `osm_villes`, `osm_magasins_chaussures` et `destatis_population_villes` (T16), `osrm_distances` (T17). Une table déclarée passe en silver puis en gold sous son propre nom, à côté des tables simulées, sans fusion. Tant que son fichier n'existe pas, elle est ignorée avec un message, sans arrêter le pipeline.
- **Deux dossiers d'entrée** : un fichier collecté par un script va dans `data/bronze/` (non versionné) ; un fichier saisi à la main depuis une source officielle va dans `data/manual/` (versionné) et se déclare avec `directory=MANUAL`. Dans les deux cas, le fichier s'appelle `<nom de la table>.csv`.
- **Collecte** : `make collect` reconstruit les tables réelles à partir des fichiers bruts versionnés. Elle n'appelle le réseau que pour une ville ou un trajet absent de `data/bronze/`.
- **Jeu simulé recalibré (T2)** : le recalibrage a changé les valeurs de 11 des 19 tables simulées, pas seulement celles des magasins et des ventes : le tirage aléatoire des tables suivantes a été décalé. Aucune table n'a disparu. Relancez `make all` après votre `git pull`. Tout chiffre du jeu v1 recopié dans un document (README, journal de nettoyage, slides) est à recalculer.
- **Tâches faites** : T1, T2, T5 (squelette, tables réelles à brancher), T6, T16, T17. Le suivi complet est dans `TACHES.md`.

## Git : le circuit

```bash
git checkout develop && git pull
git checkout -b feature/T<numéro>-<nom-court>
# ... travail ...
make lint && make test            # doit passer avant tout push
git push -u origin feature/T<numéro>-<nom-court>
```

Puis prévenir Jean-Li, qui merge dans `develop`. **Personne ne pousse sur `main`.**

## Si vous utilisez un assistant de code

1. Commencez **chaque** session par : « Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/<ton-prénom>.md`. Je travaille sur la tâche T<n>. »
2. Votre fiche contient des messages prêts à coller pour chaque tâche. Utilisez-les : ils limitent l'assistant à votre périmètre.
3. Demandez toujours à voir le résultat **avant** commit et push.

## Règles de données (non négociables)

1. **Aucun chiffre réel inventé.** Une donnée présentée comme réelle vient d'un fichier daté dans `data/bronze/` avec son URL. Si elle manque : `TODO`, et on le dit.
2. **Simulé = étiqueté** : colonnes `est_simule` et `source` dans chaque table.
3. **Hypothèses** dans `config/hypotheses.yaml`, avec leur origine en commentaire. Pas de nombre en dur dans le code.
4. **`data/bronze/` est immuable** : on retransforme, on ne modifie pas.
5. **Chaque correction de données** est consignée dans `docs/JOURNAL_NETTOYAGE.md` (anomalie, nb de lignes, décision, justification métier).
6. **Calculs** : taux recalculés depuis numérateurs et dénominateurs, jamais moyennés ; prix comparés en HT sur un panier identique de SKU ; CA/m² comparé à format identique ; 2026 partiel (janvier-octobre).
7. **Scraping** : lire `robots.txt` d'abord, user-agent explicite, ≥ 2 s entre requêtes, données produit publiques seulement. Blocage ou CAPTCHA : on s'arrête, jamais de contournement.
8. **Secrets** (clé API) dans `.env`, jamais commité. Le dépôt est **public**.

## Périmètre de chacun

Chacun ne modifie que **ses** fichiers (voir sa fiche). Les fichiers partagés ci-dessous se modifient par petites touches, en prévenant le groupe :

| Fichier partagé | Qui le maintient | Règle |
|---|---|---|
| `Makefile`, `requirements.txt`, `.github/` | Jean-Li | Ajout d'une ligne possible, prévenir |
| `src/transform/bronze_to_silver.py` (`TableSpec`, `REAL_TABLES`) | Jean-Li | Déclarer sa table ou sa colonne, rien d'autre |
| `config/hypotheses.yaml` | Alexis | Chacun ajoute sa section, ne touche pas celles des autres |
| `README.md` | Jean-Li | Les autres proposent, Jean-Li intègre (T14) |

## Contrat entre les tâches

La table `kpi_summary` (T7) est le point de rencontre entre KPIs, IA et dashboard. Ses colonnes sont figées :

| Colonne | Contenu |
|---|---|
| `kpi` | Nom du KPI |
| `axe` | Marché, Prix, Réseau, Logistique, Assortiment, Rentabilité |
| `pays` | Code ISO-2 |
| `valeur` | Nombre |
| `unite` | %, €, km, indice… |
| `seuil` | Seuil Go/No-Go (README 4.2), vide si aucun |
| `statut_go` | GO, NO-GO ou INFO |
| `statut_epistemique` | FAIT, CALCUL, HYPOTHÈSE ou CONVENTION, au sens du README (section 2.2) |
| `origine_donnees` | REEL, SIMULE ou MIXTE : d'où viennent les entrées du calcul |

`origine_donnees` a été ajoutée le 12/11/2026. Elle ne remplace pas `statut_epistemique` : un indice calculé sur des prix réels reste un CALCUL, avec `origine_donnees` = REEL.

Briac et Aurélie peuvent commencer avec une version factice de cette table, puis se brancher sur la vraie.
