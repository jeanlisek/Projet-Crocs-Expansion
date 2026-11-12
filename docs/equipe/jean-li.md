# Jean-Li Sek : tech lead

**Rôle** : dépôt, CI, pipeline bronze → silver → gold, intégration des branches, README final.
**À l'oral** : section 4, analyse et dataviz (3 min, avec Briac).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T1 | Dépôt, CI, Makefile, requirements | ✅ Fait | — | Tout |
| T5 | Bronze → silver + journal de nettoyage | ✅ Fait (squelette, tables réelles à brancher) | T3, T4, T16, T17, T18 pour les tables réelles | T6 |
| T6 | Silver → gold (DuckDB) + tests de qualité | ✅ Fait | T2, T5 | T7 |
| T10 | Exports pour le dashboard | Fait | T7, T9 | T11 |
| T16 | OpenStreetMap : magasins de chaussures par ville allemande | ✅ Fait | — | Densité concurrentielle réelle |
| T17 | Coordonnées réelles et distances routières (OSRM) | ✅ Fait | — | Distance aux hubs réelle |
| T14 | README final | Vendredi matin | T13 | Livrable 1 |

**Ton rôle transverse** : merger les branches dans `develop` dès qu'elles sont prêtes (CI verte), débloquer les autres.

## Tes fichiers

`Makefile`, `requirements.txt`, `.github/`, `src/transform/`, `src/collect/osm.py`, `src/collect/destatis.py`, `src/collect/osrm.py`, `tests/`, `data/gold/`, `README.md`.

## Messages à coller

**T6**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. Tâche T6 sur `feature/T6-gold`, créée depuis ce `develop` à jour. Construis `src/transform/build_gold.py` : charge les Parquet de `data/silver/` dans `data/gold/warehouse.duckdb` selon le modèle en constellation du README (section 3.2). Si des tables réelles existent dans `REAL_TABLES`, charge-les à côté des tables simulées, sans les fusionner. Ajoute `tests/test_qualite_gold.py` : unicité au grain, aucune clé orpheline, prix > 0, codes pays dans `dim_pays`. Cible `make gold`, ajoutée à `all`. Montre-moi le résultat avant le commit.

**Merger une branche d'un coéquipier**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. Récupère `origin/feature/<branche>`. D'abord, vérifie les auteurs avec `git log --format="%an <%ae>" develop..<branche>` et le texte des commits avec `git log --format=%B develop..<branche>` : si un auteur est extérieur à l'équipe, si un e-mail est vide, ou si un message mentionne un outil (assistant, `Co-Authored-By`…), arrête-toi et dis-le-moi. Un auteur de l'équipe peut signer sous un pseudo connu (tableau ci-dessous) : c'est accepté. Ensuite, lance `make lint` et `make test` dessus. Si tout passe, merge dans `develop` en `--no-ff`, push, et vérifie la CI avec `/opt/homebrew/bin/gh run list --limit 2`. Sinon, montre-moi ce qui casse sans corriger le code du coéquipier.

Pseudos connus de l'équipe (à compléter quand un membre en utilise un nouveau) :

| Signature git | Membre |
|---|---|
| `JeanRevo <briacturquety@gmail.com>` | Briac Truquety |

**T16 : OpenStreetMap**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. Tâche T16 sur `feature/T16-osm`, créée depuis ce `develop` à jour. Lis d'abord la politique d'usage de l'API Overpass et montre-moi ce qu'elle autorise. Ne lance aucune requête avant mon accord. Crée ensuite `src/collect/osm.py` : pour chaque ville allemande de `dim_zone_chalandise`, relève les magasins `shop=shoes` dans la limite administrative de la ville, avec le tag `brand` quand il existe. User-agent explicite, ≥ 2 s entre requêtes, réponses brutes datées dans `data/bronze/`. Commence par 2 villes et montre-moi le résultat avant d'élargir. Calcule la densité pour 100 000 habitants et dis-moi quelle population tu utilises et si elle est réelle ou simulée. Déclare la table dans `REAL_TABLES`, puis vérifie que `make silver` et `make gold` passent. Blocage ou limite atteinte : arrête-toi et dis-le-moi, sans contourner.

**T17 : distances routières**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. Tâche T17 sur `feature/T17-distances`, créée depuis ce `develop` à jour. Lis d'abord la politique d'usage du serveur public OSRM, et celle du service de géocodage que tu proposes, et montre-moi ce qu'elles autorisent. Ne lance aucune requête avant mon accord. Crée ensuite `src/collect/osrm.py` : coordonnées réelles des communes des 3 hubs et des villes cibles de `dim_zone_chalandise` (Allemagne d'abord), puis distance routière et durée de chaque hub vers chaque ville. User-agent explicite, ≥ 2 s entre requêtes, chaque réponse mise en cache dans `data/bronze/` pour ne jamais redemander un trajet déjà obtenu. Commence par 3 trajets et montre-moi. Déclare la table dans `REAL_TABLES`, avec dans `source` le rappel que l'emplacement des hubs est une hypothèse du scénario. Compare ensuite avec `fact_logistique` simulé et montre-moi les écarts.

**T10**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. Tâche T10 sur `feature/T10-exports`, créée depuis ce `develop` à jour. Exporte en CSV dans `data/gold/exports/` : `kpi_summary`, `business_case`, `city_scoring`, `ai_commentary` et les tables utiles au dashboard. Mêmes noms de colonnes que les vues. Cible `make exports`. Ces CSV sont versionnés.

**Fusion finale vers `main`** (jeudi soir, puis vendredi matin)
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. CI verte sur `develop` ? Si oui, merge `develop` dans `main` en `--no-ff`, push, vérifie la CI de `main`.
