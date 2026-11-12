# Alexis Sapone : modélisation, KPIs et business case

**Rôle** : rendre le jeu crédible (T2), puis calculer les chiffres sur lesquels le Comex décide.
**À l'oral** : section 3, pourquoi ces KPIs (2 min).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T2 | Recalibrer la rentabilité des magasins | **Prioritaire** | — | Business case crédible |
| T7 | Vues KPI + `kpi_summary` | Jeudi après-midi | T6 (faite) | IA, dashboard |
| T8 | Business case Allemagne : 3 scénarios + scoring des villes | Jeudi soir | T7 | Recommandation |

## Pourquoi T2 est urgent

Dans le jeu v1, un magasin rembourse son investissement en 3 à 6 mois, pour un CA de 9 à 19 k€/m² ; seuls les outlets font exception (19 mois, 5 000 €/m²). Le Go serait acquis d'avance, et le jury le verrait (voir `docs/AUDIT_JEU_DE_DONNEES_V1.md`, point 1).

## Tes fichiers

`src/simulate/generate_data.py`, `config/hypotheses.yaml` (section business case), `sql/kpi/`.

## Messages à coller

**T2**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/alexis.md`. Lis aussi le point 1 de `docs/AUDIT_JEU_DE_DONNEES_V1.md`. Tâche T2 sur `feature/T2-recalibrage`, créée depuis ce `develop` à jour.
> 1. Recalibre `src/simulate/generate_data.py` pour un payback médian France entre 1 et 4 ans par format, avec un CA/m² plausible pour du commerce de chaussures spécialisé. Les paramètres changés vont dans `config/hypotheses.yaml`, avec un commentaire.
> 2. Ajoute `date_fermeture` à `dim_magasin` (quelques fermetures pour illustrer le biais de survie) et déclare la colonne dans le `TableSpec` de `src/transform/bronze_to_silver.py`.
> 3. Ajoute une colonne qui signale les zones insulaires (Las Palmas) pour les exclure du benchmark logistique.
> 4. Relance `make simulate`, `make silver`, `make test` : les contrôles TTC/HT, marge et remise doivent rester à 0 écart.
> Montre-moi le tableau payback / CA par m² par format avant le commit.

**T7** (T6 est faite : les vues lisent l'entrepôt `data/gold/warehouse.duckdb`)

Consignes techniques :

- Une vue par fichier dans `sql/kpi/`, écrite en `CREATE OR REPLACE VIEW`.
- L'ordre des fichiers est libre : une vue qui en lit une autre est retentée après les autres.
- Une erreur SQL arrête `make kpi` en nommant le fichier fautif.
- Pour tester : `make gold && make kpi`.

Réel ou simulé : pour l'indice prix, le % du catalogue éligible, la densité concurrentielle et la distance au hub, la table réelle est prioritaire quand elle existe dans l'entrepôt ; sinon, utilise la simulée. Dans `kpi_summary`, `origine_donnees` indique d'où viennent les entrées (REEL, SIMULE ou MIXTE) et `statut_epistemique` reste conforme au README (section 2.3). Quand les deux tables existent, ajoute une ligne de comparaison réel / simulé.

> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/alexis.md`. Tâche T7 sur `feature/T7-kpi`, créée depuis ce `develop` à jour. Écris une vue SQL par KPI du README (section 2.3), une vue par fichier dans `sql/kpi/`, exécutée par `make kpi`, avec les règles de gestion de la section 2.5. Construis `kpi_summary` avec les colonnes exactes de `docs/equipe/REGLES_COMMUNES.md` (« Contrat entre les tâches »), pour tous les pays, avec les seuils de `config/hypotheses.yaml`. Un test par KPI sur un petit jeu calculé à la main.

**T8**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/alexis.md`. Tâche T8 sur `feature/T8-business-case`, créée depuis ce `develop` à jour. Compte de résultat d'un magasin type en Allemagne : loyer + charges, personnel, énergie, marketing de lancement, logistique, démarque, frais bancaires, frais de siège, amortissement. Trois scénarios de montée en charge (pessimiste, central, optimiste), hypothèses dans `config/hypotheses.yaml`. Vues `business_case` (payback, point mort, coût d'occupation par scénario et format) et `city_scoring` (score des villes allemandes : potentiel, loyer, densité concurrentielle, distance au hub). Ajoute les KPIs de rentabilité à `kpi_summary`.
