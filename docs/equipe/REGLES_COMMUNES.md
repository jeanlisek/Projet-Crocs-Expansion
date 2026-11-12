# Règles communes de l'équipe

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

1. Commencez **chaque** session par : « Lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/<ton-prénom>.md`. Je travaille sur la tâche T<n>. »
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
| `statut_epistemique` | FAIT, CALCUL, HYPOTHÈSE ou CONVENTION |

Briac et Aurélie peuvent commencer avec une version factice de cette table, puis se brancher sur la vraie.
