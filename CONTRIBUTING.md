# Contribuer à Nephos

Merci de l'intérêt pour Nephos. Ce document décrit **le workflow de contribution**, les **conventions** et — surtout — la **chaîne de revue obligatoire avant tout merge**, qui combine revue agentique automatisée et validation humaine senior.

---

## 1. Chaîne de revue obligatoire avant merge

> **Aucun changement n'arrive sur `main` sans avoir été examiné matériellement par un mainteneur senior humain, après une revue agentique automatisée préalable. Cette règle s'applique sans exception aux contributions humaines comme aux contributions produites par un agent IA en autonomie.**

Le workflow comporte **trois niveaux**, dans cet ordre, **non court-circuitables** :

### Niveau 1 — Auteur (humain ou agent IA)

L'auteur produit la modification : code, schéma, ADR, documentation, configuration. Il pousse sur une **branche dédiée**, jamais directement sur `main`. Il ouvre une **pull request** documentée :

- titre court (`<type>: <résumé>`, voir conventions § 3) ;
- description qui explique le **pourquoi** (référencer items du `BACKLOG.md`, ADR, issues) ;
- diff couvert par CI verte (lint, type, sécu, tests) ;
- mise à jour de `CHANGELOG.md` et, si applicable, de `BACKLOG.md`.

Si l'auteur est un agent IA (par exemple Claude Code en mode autonomie), la PR doit explicitement le mentionner dans la description et inclure un trailer `Co-Authored-By` dans le commit.

### Niveau 2 — Revue agentique automatisée

Avant qu'un humain n'examine la PR, **un agent reviewer** (distinct de l'auteur) analyse le diff et produit un **rapport structuré** déposé en commentaire de la PR. Le rapport couvre :

- **Cohérence architecturale** : respect des ADR existants, pas de violation des invariants (option A, double licence, multi-hiérarchie SKOS, séparation gov/vocab).
- **Qualité du code** : lisibilité, dette introduite, tests présents et significatifs, signaux de typage propres.
- **Sécurité** : validation des entrées, absence de secrets, évaluation des nouveaux droits accordés (auth, accès BD, exécution de code arbitraire).
- **Cohérence documentaire** : `CHANGELOG.md` à jour, `BACKLOG.md` synchronisé, items marqués `✅` quand appropriés, ADR référencé si décision structurante.
- **Tests et couverture** : tests d'intégration significatifs ajoutés, fixtures plausibles, pas de tests tautologiques.
- **Risque de régression** : impacts sur les autres modules, contrats de CLI/API, schéma SQL.

Le rapport conclut par **un verdict explicite** : `À faire passer en revue humaine`, `À retravailler avant revue humaine` ou `Bloquant — refonte requise`.

L'agent reviewer **n'a aucun droit de merge**. Sa fonction est d'éclairer la revue humaine, pas de la remplacer.

### Niveau 3 — Validation humaine senior

Un mainteneur senior **examine matériellement** :

- la PR elle-même (diff complet, pas seulement le résumé) ;
- le rapport de revue agentique (mais sans s'y soumettre — c'est un éclairage, pas un oracle) ;
- les tests et leur sortie ;
- les éventuels artefacts (rapports SHACL, exports RDF, dumps) ;
- l'impact sur le périmètre (cf. ADR 0001 option A et ADR 0010 invariants).

Le mainteneur senior peut :

- **Approuver et merger** ;
- **Demander des modifications** (commentaires détaillés sur la PR) ;
- **Refuser** la PR avec motivation, qui sera ajoutée à la PR pour traçabilité.

Le merge se fait **par squash** (un commit propre par PR) ou **par rebase** selon la cohérence du flux. Pas de merge commits.

### Cas spécifique : agent IA en autonomie

Quand un agent IA travaille en autonomie (par exemple session `/loop` ou délégation explicite), la chaîne de revue **reste obligatoire et inchangée** :

| Étape | Qui | Comment |
|---|---|---|
| Production | Agent IA en autonomie | Branche dédiée, PR documentée, CI verte. |
| **Revue agentique** | Agent reviewer distinct | Rapport structuré commenté sur la PR. |
| **Validation humaine senior** | Mainteneur humain | **Examen matériel obligatoire avant merge.** |

L'agent autonome **ne dispose d'aucun droit de merge direct sur `main`**. Toute tentative de bypass (push direct sur `main`, commit non revu) est une violation de la politique de contribution.

> **Pourquoi cette chaîne** : un agent IA peut produire du code plausible mais subtilement incorrect, oublier un invariant architectural posé dans un ADR, ou introduire une régression non détectée par la CI. La revue agentique attrape les plus évidents ; la revue humaine senior attrape les plus subtils. Les deux sont nécessaires, aucune n'est suffisante seule.

### Branches protégées (à activer côté GitHub)

L'enforcement technique se fait par les **branch protection rules** sur `main` :

- Pull requests obligatoires (pas de push direct).
- Au moins **1 review approuvée par un humain mainteneur** avant merge.
- Status checks obligatoires verts : `lint`, `type-check`, `security`, `test`, `build`.
- `Dismiss stale reviews when new commits are pushed`.
- `Require linear history` (squash ou rebase, pas de merge commits).
- `Restrict who can push to matching branches` (équipe mainteneurs uniquement).
- `Do not allow bypassing the above settings` même pour les administrateurs.

Cette configuration est à appliquer par le mainteneur — voir l'item E1-11 du `BACKLOG.md`.

---

## 2. Workflow de contribution

```
┌────────────────────┐
│ Issue (optionnel)  │ ← discuter avant de coder, surtout pour
└─────────┬──────────┘   les changements structurants ou ADR.
          ▼
┌────────────────────┐
│ Branche feat/X     │ ← depuis main, nommage explicite.
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Commits cohérents  │ ← un objectif par commit (cf. § 3).
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Pre-commit local   │ ← lint, format, mypy, bandit, deptry…
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Pull Request       │ ← description obligatoire, références au
└─────────┬──────────┘   backlog/ADR, CHANGELOG mis à jour.
          ▼
┌────────────────────┐
│ CI verte           │ ← lint, type, sécu, tests Postgres 14+16, build.
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Revue AGENTIQUE    │ ← rapport structuré déposé en commentaire.
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Revue HUMAINE      │ ← examen matériel par un mainteneur senior.
│ senior             │
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ Merge sur main     │ ← squash ou rebase, pas de merge commits.
└────────────────────┘
```

---

## 3. Conventions

### Branches

- `feat/<resume-court>` : nouvelle fonctionnalité.
- `fix/<resume-court>` : correction de bug.
- `docs/<resume-court>` : documentation seule.
- `chore/<resume-court>` : maintenance, outillage, refactor sans changement de comportement.
- `adr/<numero>-<titre>` : nouvel ADR ou modification d'un ADR existant.

### Messages de commit

Format inspiré de [Conventional Commits](https://www.conventionalcommits.org/) :

```
<type>(<scope>): <résumé court à l'impératif>

<description longue facultative — pourquoi, contexte, références>

<trailers : Refs, Closes, Co-Authored-By, …>
```

Types acceptés : `feat`, `fix`, `docs`, `chore`, `ci`, `test`, `refactor`, `style`, `perf`, `build`. Scopes courants : `schema`, `python`, `adr`, `cli`, `db`, `import`, `validators`, `ci`, `quality`, `readme`.

### Pull requests

- **Titre** : même format que les commits.
- **Description** :
  - section « Pourquoi » (motivation, lien vers item de backlog ou issue) ;
  - section « Quoi » (résumé fonctionnel, pas un dump du diff) ;
  - section « Tests » (ce qui a été testé, comment vérifier) ;
  - section « Notes au revieweur » si nécessaire (pièges, trade-offs).
- **CHANGELOG** mis à jour systématiquement.
- **BACKLOG** synchronisé si l'item couvert change d'état.
- **ADR** créé si la PR porte une décision structurante.

### Definition of Done

Reportée du `BACKLOG.md` :

- code (ou doc) versionné dans `main` après chaîne de revue ;
- tests automatisés verts (≥ 80 % de couverture sur le code applicatif neuf) ;
- `CHANGELOG.md` mis à jour ;
- documentation associée à jour (ADR, README, docstrings) ;
- pour un ADR : format MADR, référencé dans le tableau du `CHANGELOG.md` et du `README.md`.

---

## 4. Licences et contributions

Le projet est sous **double licence** (cf. [ADR 0005](docs/adr/0005-licences-apache-2-et-cc-by-4.md)) :

- **Code et documentation d'ingénierie** : [Apache 2.0](LICENSE).
- **Données originales** (concepts Nephos, traductions, mappings éditoriaux) : [CC-BY 4.0](DATA_LICENSE).

En soumettant une contribution, vous acceptez que :

- vos contributions de code soient distribuées sous Apache 2.0 ;
- vos contributions de données soient distribuées sous CC-BY 4.0 ;
- vous avez le droit légitime de contribuer ce contenu (pas de plagiat, pas de violation de licence amont).

Pour les imports issus de sources externes, conserver la licence d'origine et l'attribution dans `concept_mapping`. Voir ADR 0005 pour le détail.

---

## 5. Outillage local

Voir le [README](README.md#démarrage) pour la mise en place de PostgreSQL et l'application du schéma. Pour le développement :

```bash
# Installation des dépendances dev
uv sync --all-extras

# Activer les hooks pre-commit
uv run pre-commit install

# Vérifier que tout passe avant de pousser
uv run pre-commit run --all-files
uv run mypy src/nephos
uv run pytest

# Lancer mutation testing (long, optionnel)
uv run mutmut run
uv run mutmut results
```

---

## 6. Discussion et questions

- **Issues** : https://github.com/benedictemarty/nephos/issues
- **Discussions** : à activer côté GitHub si besoin émerge.
- **Décisions structurantes** : passent par un ADR avant code (voir `docs/adr/template.md`).
