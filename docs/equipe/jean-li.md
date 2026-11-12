# Jean-Li Sek : tech lead

**Rôle** : dépôt, CI, pipeline bronze → silver → gold, intégration des branches, README final.
**À l'oral** : section 4, analyse et dataviz (3 min, avec Briac).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T1 | Dépôt, CI, Makefile, requirements | ✅ Fait | — | Tout |
| T5 | Bronze → silver + journal de nettoyage | ✅ Fait (squelette, tables réelles à brancher) | T3, T4 pour les tables réelles | T6 |
| T6 | Silver → gold (DuckDB) + tests de qualité | À faire | T2, T5 | T7 |
| T10 | Exports pour le dashboard | À faire | T7, T9 | T11 |
| T14 | README final | Vendredi matin | T13 | Livrable 1 |

**Ton rôle transverse** : merger les branches dans `develop` dès qu'elles sont prêtes (CI verte), débloquer les autres.

## Tes fichiers

`Makefile`, `requirements.txt`, `.github/`, `src/transform/`, `tests/`, `data/gold/`, `README.md`.

## Messages à coller

**T6**
> Lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/jean-li.md`. Tâche T6 sur `feature/T6-gold` depuis `develop`. Construis `src/transform/build_gold.py` : charge les Parquet de `data/silver/` dans `data/gold/warehouse.duckdb` selon le modèle en constellation du README (section 3.2). Si des tables réelles existent dans `REAL_TABLES`, charge-les à côté des tables simulées, sans les fusionner. Ajoute `tests/test_qualite_gold.py` : unicité au grain, aucune clé orpheline, prix > 0, codes pays dans `dim_pays`. Cible `make gold`, ajoutée à `all`. Montre-moi le résultat avant le commit.

**Merger une branche d'un coéquipier**
> Récupère `origin/feature/<branche>`. Lance `make lint` et `make test` dessus. Si tout passe, merge dans `develop` en `--no-ff`, push, et vérifie la CI avec `/opt/homebrew/bin/gh run list --limit 2`. Sinon, montre-moi ce qui casse sans corriger le code du coéquipier.

**T10**
> Tâche T10 sur `feature/T10-exports`. Exporte en CSV dans `data/gold/exports/` : `kpi_summary`, `business_case`, `city_scoring`, `ai_commentary` et les tables utiles au dashboard. Mêmes noms de colonnes que les vues. Cible `make exports`. Ces CSV sont versionnés.

**Fusion finale vers `main`** (jeudi soir, puis vendredi matin)
> CI verte sur `develop` ? Si oui, merge `develop` dans `main` en `--no-ff`, push, vérifie la CI de `main`.
