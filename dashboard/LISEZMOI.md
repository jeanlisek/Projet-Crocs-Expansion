# Dashboard Power BI (T11)

Projet Power BI au format `.pbip` (fichiers texte) : ouvrir `dashboard_crocs.pbip` avec Power BI Desktop.

## Ouvrir le dashboard sur un autre ordinateur (ordinateur de la présentation)

Les données sont lues dans `data/gold/exports/` via le paramètre **DossierExports**, qui contient un chemin absolu propre au PC d'Aurélie.

1. Cloner le dépôt (ou `git pull`), puis ouvrir `dashboard/dashboard_crocs.pbip`.
2. Accueil > Transformer les données > **Modifier les paramètres** : remplacer `DossierExports` par le chemin complet du dossier `data/gold/exports\` de cette machine (terminé par `\`).
3. Accueil > **Actualiser**. Les 4 pages et les commentaires IA doivent s'afficher.
4. Avant le premier import sur une nouvelle machine : Fichier > Options > Fichier actif > Paramètres régionaux pour l'importation = Anglais (États-Unis).

Le paramètre `DossierMaquette` (fichiers factices) n'est plus utilisé.

## Captures

`captures/` : une image par page (Synthèse Comex, Marché & prix, Où s'implanter, Business case).
