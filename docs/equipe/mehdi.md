# Mehdi Zitouni : collecte de données réelles

**Rôle** : rapporter du **réel** dans un jeu aujourd'hui 100 % simulé. C'est ce qui sécurise les 15 points « Sources ».
**À l'oral** : section 2, base de données et cadrage (1 min 30).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T3 | Prix réels Crocs FR / DE (scraping ou relevé manuel) | **Prioritaire** | — | Indice prix réel |
| T4 | API Eurostat → données pays réelles | **Prioritaire** | — | `dim_pays` réel |
| T12 | Dictionnaire champ par champ | Jeudi soir | T6 | README |

## Tes fichiers

`src/collect/`, `docs/DICTIONNAIRE_CHAMPS.md`, et la déclaration de tes tables dans `REAL_TABLES` (`src/transform/bronze_to_silver.py`).

## Messages à coller

**T3 : prix Crocs**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/mehdi.md`. Tâche T3 sur `feature/T3-scraping-crocs`, créée depuis ce `develop` à jour.
> 1. Lis `robots.txt` de crocs.fr et crocs.de et montre-moi ce qu'il autorise. Ne scrape rien avant mon accord.
> 2. Si c'est autorisé : `src/collect/scrape_crocs.py`, user-agent explicite, ≥ 2 s entre requêtes. Champs : nom, code modèle, coloris, catégorie, prix affiché, prix barré, URL, date. 10 produits par site d'abord, montre-moi.
> 3. Si c'est interdit ou bloqué : arrête-toi et dis-le-moi, sans contourner.
> 4. Snapshots datés dans `data/bronze/`, déclarés dans `REAL_TABLES`. Appariement FR/DE par modèle et coloris, au moins 30 paires.

**Plan B si le site bloque** : relevé manuel d'environ 30 produits sur les deux sites, dans `data/bronze/prix_crocs_releve_manuel_<date>.csv` (mêmes colonnes + URL + date). C'est une donnée réelle et défendable. Ensuite :
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/mehdi.md`. Reviens ensuite sur `feature/T3-scraping-crocs` et fais `git merge develop` pour y récupérer les dernières modifications. Déclare `data/bronze/prix_crocs_releve_manuel_<date>.csv` dans `REAL_TABLES`, avec typage et contrôles, et vérifie que `make silver` passe.

**T4 : Eurostat**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/mehdi.md`. Tâche T4 sur `feature/T4-eurostat`, créée depuis ce `develop` à jour. Crée `src/collect/eurostat.py` : population, PIB par habitant en SPA, taux de chômage et indice de niveau de prix, pour FR, DE, ES, IT, BE, NL (et GB si disponible), dernière année disponible. Trouve les codes des jeux de données dans le catalogue Eurostat, vérifie-les et note-les en commentaire : ne les devine pas. Sortie datée dans `data/bronze/`, déclarée dans `REAL_TABLES`. Puis compare avec `dim_pays` simulé et montre-moi les écarts.

**T12 : dictionnaire**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/mehdi.md`. Tâche T12 sur `feature/T12-dictionnaire`, créée depuis ce `develop` à jour. Génère `docs/DICTIONNAIRE_CHAMPS.md` au format du cours : Champ, Type, Description, Formule, Exemple, Source, une section par table gold. Types et exemples lus dans les données, descriptions et sources tirées de `docs/DICTIONNAIRE_DONNEES.md` et du README. Mets `TODO` quand tu ne sais pas.
