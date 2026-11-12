# Briac Truquety : brique IA

**Rôle** : la synthèse et les commentaires générés par IA, exigés par le sujet. Le cours demande des **commentaires qui changent selon les filtres**, montrés en direct à l'oral.
**À l'oral** : section 4, démonstration de la brique IA (avec Jean-Li).

## Tes tâches

| ID | Tâche | Statut | Dépend de | Débloque |
|---|---|---|---|---|
| T9 | Commentaires par filtre + synthèse Comex | Démarrer maintenant sur des données factices | T7 pour les vraies données | Dashboard, slides |
| T13 | Slides Comex (avec Aurélie) | Jeudi soir | T8, T11 | Oral |

## Le principe

1. Les commentaires sont **pré-générés** pour chaque valeur de filtre (page × pays, page × ville, page × scénario) et stockés dans la table `ai_commentary`.
2. Le dashboard affiche le commentaire qui correspond au filtre actif. Changer de pays en démo change le commentaire.
3. **Garde-fou** : le modèle ne reçoit que les lignes de `kpi_summary` concernées. Après génération, le code extrait chaque nombre du texte et vérifie qu'il figure dans l'entrée. Sinon : régénération, puis `verifie = false`.

C'est ce garde-fou qui rend la brique défendable devant le jury : l'IA commente, elle n'invente pas de chiffres.

## Tes fichiers

`src/ai/`, `src/ai/prompts/`, `.env` (local, jamais commité).

## Messages à coller

**T9, étape 1 (maintenant)**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/briac.md`. Tâche T9 sur `feature/T9-ia`, créée depuis ce `develop` à jour. Crée `src/ai/commentary.py` et `src/ai/prompts/`. En attendant T7, fabrique un `kpi_summary` factice respectant exactement les colonnes du « Contrat entre les tâches », clairement marqué comme factice. Pour chaque (page × valeur de filtre), génère un commentaire de 2-3 phrases et une synthèse Comex structurée (contexte, constats par axe, risques, recommandation Go/No-Go avec conditions). Clé API lue dans `.env`. Ajoute la vérification des nombres. Écris dans `data/gold/ai_commentary.csv` (colonnes : `page`, `filtre`, `valeur_filtre`, `texte`, `verifie`, `date_generation`). Cible `make ai`. Montre-moi 3 exemples.

**T9, étape 2 (quand T7 est mergée)**
> Fais `git checkout develop && git pull`, puis lis `docs/equipe/REGLES_COMMUNES.md` et `docs/equipe/briac.md`. Reviens ensuite sur `feature/T9-ia` et fais `git merge develop` pour y récupérer les dernières modifications. Remplace le `kpi_summary` factice par la vraie vue de `data/gold/`. Régénère tous les commentaires, montre-moi ceux de la page Synthèse pour DE et ceux qui ont `verifie = false`.

**Point à trancher avec l'équipe** : quel fournisseur de LLM, et qui a une clé API.
