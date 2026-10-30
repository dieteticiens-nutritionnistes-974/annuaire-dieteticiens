# Consignes pour l'agent IA

Ce dépôt publie l'annuaire des diététiciens libéraux de La Réunion sur GitHub Pages :
https://dieteticiens-nutritionnistes-974.github.io/annuaire-dieteticiens/

Les personnes qui te sollicitent ne sont pas développeuses. Parle-leur simplement, en français, explique ce que tu fais et **demande toujours leur accord avant de publier** (`git push`).

## Comment le site est construit

| Fichier | Rôle | Le modifier ? |
|---|---|---|
| `index.html` | La page publiée. **Générée** : données et photos sont intégrées dedans. | Jamais à la main : relancer la construction. |
| `outils/construire.py` | Lit l'export CSV du formulaire et génère `index.html` + `rapport-anomalies.md`. | Seulement si le formulaire a changé de structure. |
| `corrections.json` | Corrections manuelles appliquées à chaque construction (noms, communes, liens, exclusions, surcharges). | Oui, c'est l'endroit pour toute correction de contenu. |
| `src/gabarit.html` | Mise en page, styles et code de la carte. Contient `/*DATA*/` et `/*GEO*/`, remplacés à la construction. | Pour une modification de présentation. |
| `src/communes.json` | Contours simplifiés des 24 communes (IGN). | Non. |
| `cache/`, `donnees/`, `rapport-anomalies.md` | Photos téléchargées, CSV, rapport. **Non versionnés** (voir `.gitignore`). | — |

Prérequis : `git`, `python3` et Pillow (`python3 -m pip install Pillow` si l'import échoue).

## Mise à jour annuelle à partir d'un nouvel export CSV

1. `git pull` pour partir de la dernière version.
2. Copier le CSV fourni dans `donnees/` (dossier ignoré par git : **ne jamais versionner le CSV**, il contient les réponses brutes du formulaire).
3. Lancer `python3 outils/construire.py donnees/<fichier>.csv`.
4. Lire `rapport-anomalies.md` et le **présenter à la personne** : nombre de fiches, liste des personnes, points à vérifier.
5. Pour chaque point qu'elle veut corriger, modifier `corrections.json` (jamais le CSV), puis relancer l'étape 3.
   - prénom/nom mal découpé ou sans accent → `noms`
   - commune non reconnue → `communes` (orthographe saisie → nom officiel)
   - personne qui ne doit plus apparaître → `exclure`
   - photo qui ne se télécharge pas → demander à la personne de partager le fichier Drive en « Tous les utilisateurs disposant du lien », puis relancer
6. Ouvrir `index.html` dans un navigateur et vérifier : carte avec pastilles, vue « Par commune », trombinoscope, ouverture d'une fiche.
7. Résumer les changements par rapport à la version en ligne (`git diff --stat`, fiches ajoutées ou retirées) et **demander l'accord** de publier.
8. `git add index.html corrections.json` (et les autres fichiers volontairement modifiés), commit avec un message clair (ex. « Annuaire 2027 : 15 fiches »), `git push`.
9. GitHub Pages republie en une à deux minutes. Vérifier https://dieteticiens-nutritionnistes-974.github.io/annuaire-dieteticiens/ (forcer le rechargement).

## Modifications ponctuelles en cours d'année

Exemple : « Le numéro de Maëlle Guyon a changé », « Retire Thomas Doucet ».

- Changer une information d'une fiche : ajouter une entrée dans `corrections.json > surcharges`, avec l'identifiant de la fiche (prénom-nom sans accents, ex. `maelle-guyon`) :
  `"maelle-guyon": { "tel": "0692 00 00 00" }`
  Champs possibles : `tel`, `email`, `pitch`, `structure`, `communes` (liste de noms officiels), `modalites` (`Cabinet`, `Visio`, `Domicile`), `liens` (objet avec `rdv`, `site`, `instagram`, `facebook`, `linkedin`), `formations` (liste).
- Retirer quelqu'un : ajouter son nom tel que saisi dans le formulaire à `exclure`.
- Puis reconstruire à partir du **dernier CSV** (le demander à la personne s'il n'est pas dans `donnees/`) et suivre les étapes 4 à 9.

## Règles

- Ne jamais publier sans l'accord explicite de la personne.
- Ne jamais versionner de CSV ni de données qui ne figurent pas déjà sur le site.
- Ne pas inventer d'information sur un professionnel : tout vient du formulaire ou d'une demande explicite.
- Garder la page autonome (pas de nouveau service externe, pas de traceur, pas de cookie).
