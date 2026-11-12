# Aurélie Périchon : restitution

**Rôle** : ce que le Comex voit, c'est-à-dire le dashboard et les slides. Le barème leur donne le plus de points : impact décisionnel et dataviz, 35 points.
**À l'oral** : section 1, entreprise et pays (1 min), et section 5, Go/No-Go et next steps (1 min 30).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T11 | Dashboard, 4 pages | Maquette maintenant | T10 pour les données finales | Démo |
| T13 | Slides Comex (avec Briac) | Jeudi soir | T8, T11 | Oral |

**Décision à prendre tout de suite** : Power BI (si tu as Windows) ou Looker Studio.

> **Contrat `kpi_summary` mis à jour le 12/11/2026** : il a gagné la colonne `origine_donnees` (REEL, SIMULE ou MIXTE), décrite dans `REGLES_COMMUNES.md` (« Contrat entre les tâches »). Elle te sert à afficher la mention « données simulées » là où c'est le cas.

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

Maquette dès maintenant sur les CSV de `data/bronze/` (lance `make simulate`) : structure des pages, filtres, couleurs. Quand T10 sera prête, il suffira de pointer vers `data/gold/exports/`.

Si tu utilises un assistant :
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/aurelie.md`. Je construis le dashboard dans <Power BI / Looker Studio>. Propose-moi pour chacune des 4 pages : les visuels (type de graphique justifié par l'objectif : comparaison, composition, distribution ou relation), les champs utilisés, les filtres, et l'emplacement du commentaire IA. Respecte les règles de dataviz de ma fiche.

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
