# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog 1.1.0](https://keepachangelog.com/fr/1.1.0/)
et ce projet adhère au [versionnement sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté

- **Module `nephos.logging`** — configuration unifiée du logging (E3-05). Deux formats : `text` (humain, format `%(asctime)s %(levelname)-8s %(name)s — %(message)s`) et `json` (un objet JSON par ligne, destiné aux collecteurs Loki/Datadog/ELK). `configure_logging()` est idempotent et appelée automatiquement en tête de la callback CLI. `get_logger(name)` exposé pour usage par les modules métier à venir.
- **Renforcement du typage strict mypy** : ajout de `warn_return_any`, `warn_unreachable`, `disallow_any_generics`, `disallow_untyped_decorators`, `implicit_reexport=false`, `strict_equality`, `extra_checks` à `[tool.mypy]`. Annotations explicites ajoutées aux globales du CLI (`app: typer.Typer`, `console: Console`), à `__version__: str`, à `_STANDARD_ATTRS: frozenset[str]`. Migration des options Typer vers la syntaxe `Annotated[T, typer.Option(...)]` qui ne casse pas le typage des callees. Encapsulation de `__main__.py` dans une fonction `main()` typée pour éviter `Any` au top level.
- **`CONTRIBUTING.md`** — politique de contribution et workflow de revue. Acte la **chaîne de revue obligatoire à trois niveaux avant tout merge sur `main`** : auteur (humain ou agent IA) → revue agentique automatisée (rapport structuré déposé en commentaire de PR) → validation matérielle par un mainteneur senior humain. Règle explicitement applicable aux contributions produites par un agent IA en autonomie (aucun droit de merge direct, pas de bypass possible). Documente les conventions (branches, commits, PR), la Definition of Done, l'acceptation des licences (Apache 2.0 + CC-BY 4.0) et les commandes outillage local. Spécifie les **branch protection rules** GitHub à activer (item `E1-11` créé) et l'**agent reviewer GitHub Actions** à configurer (item `E1-12` créé).
- **Mention politique de revue** ajoutée en tête du `README.md`, sous le bandeau de licences. Section « Auteurs et contact » enrichie avec renvoi à `CONTRIBUTING.md`.
- **Squelette Alembic** :
  - `alembic.ini` à la racine. URL injectée dynamiquement depuis `nephos.config.Settings` (donc `NEPHOS_DATABASE_URL` ou `.env`). Hook post-write `ruff format` sur les nouveaux scripts. Format de fichier daté + slug + révision.
  - `alembic/env.py` — pas de modèles SQLAlchemy (`target_metadata = None`), Nephos étant en SQL pur. Mode online et offline supportés.
  - `alembic/script.py.mako` — gabarit pour les nouvelles migrations (typage moderne `str | None`, `from __future__ import annotations`).
  - `alembic/versions/20260505_0000_init_schema_v4_skos_0001.py` — première migration qui applique `schema_v4_skos.sql` en bloc via `op.execute`. Downgrade : `DROP SCHEMA … CASCADE` cohérent avec le contenu du fichier SQL. Couvre conjointement `E3-09` et `E2-08`.
  - `alembic/README.md` — workflow documenté (`uv run alembic …`).
- **CI GitHub Actions** :
  - `.github/workflows/ci.yml` — pipeline déclenché sur push `main`, pull-request et manuel. 6 jobs : `lint` (pre-commit complet), `type-check` (mypy strict), `security` (bandit + pip-audit), `docs-coverage` (interrogate, informatif), `test` (pytest avec matrice PostgreSQL 14 et 16, schéma v4 appliqué, couverture XML uploadée), `build` (sdist + wheel via uv build, gated sur les autres jobs). Concurrence par branche avec annulation des runs précédents.
  - `.github/workflows/nightly.yml` — exécuté à 03:00 UTC ou manuel. 2 jobs `continue-on-error` : `mutmut` (mutation testing avec Postgres réel, artefacts uploadés) et `audit-deep` (`pip-audit --strict` + `vulture`).
  - Couvre l'item `E3-07` du backlog.
- **Outillage qualité, sécurité et tests étendu** :
  - `.pre-commit-config.yaml` complet : hooks hygiène (EOF, trailing whitespace, large files, JSON/YAML/TOML/symlinks/case conflict, detect-private-key), `gitleaks` (détection de secrets), `ruff` (lint + format), `mypy` (typage strict), `bandit` (analyse de sécurité statique), `deptry` (dépendances inutilisées ou manquantes), `validate-pyproject`, `yamllint`, `markdownlint-cli`, `sqlfluff` (final newline sur le schéma SQL).
  - `pyproject.toml` enrichi en dev-deps : `hypothesis` (property-based testing), `mutmut` (mutation testing), `bandit[toml]`, `pip-audit` (CVE des dépendances), `deptry`, `interrogate` (couverture docstrings, seuil 70 %), `vulture` (dead code), `validate-pyproject[all]`.
  - Sections de configuration ajoutées : `[tool.bandit]`, `[tool.mutmut]`, `[tool.deptry]`, `[tool.interrogate]`, `[tool.vulture]`.
  - `.yamllint.yaml` et `.markdownlint.yaml` — configurations adaptées au projet (lignes longues tolérées, plusieurs H1 acceptés pour CHANGELOG/BACKLOG, `truthy` désactivé pour les workflows GitHub Actions).
  - Outils hors pre-commit (trop lents ou usage spécifique) documentés en tête du fichier : mutmut (CI nightly ou manuel), pip-audit (CI), vulture (manuel), interrogate (CI).
  - Couvre l'item `E3-06` du backlog.
- **ADR 0010** — Étendre le périmètre Nephos aux outils de validation et de qualité de données (`docs/adr/0010-nephos-comme-moteur-de-validation.md`). Acte que Nephos absorbe les outils consommateurs qui exploitent le référentiel pour qualifier des fichiers externes (GRIB, NetCDF, BUFR…), sous trois invariants : aucun stockage d'instances, aucune modification automatique du référentiel, lecture seule. Réponse à la question d'usage : « valider un fichier GRIB depuis la base ».
- **EPIC 10 — Outils de validation et qualité de données** ajouté au backlog avec 8 items (`E10-01` à `E10-08`) couvrant l'architecture plugin, les validateurs GRIB / NetCDF-CF / BUFR, le mode `--suggest` qui génère des propositions de mappings manquants, et une action GitHub publiable pour usage en CI tiers.
- **Bootstrap projet Python** :
  - `pyproject.toml` configuré pour `uv` + Hatchling (build), avec dépendances cibles (`rdflib`, `pyshacl`, `lxml`, `requests`, `SPARQLWrapper`, `pydantic`, `pydantic-settings`, `psycopg[binary]`, `typer`, `rich`, `alembic`) et dev (`pytest`, `pytest-cov`, `pytest-postgresql`, `ruff`, `mypy`, `pre-commit`).
  - Layout `src/nephos/` (package importable, `__main__.py`, `py.typed` pour le typage publié).
  - `src/nephos/config.py` — configuration typée (`pydantic-settings`) avec préfixe d'environnement `NEPHOS_`.
  - `src/nephos/cli.py` — CLI Typer avec sous-commandes `info`, `import {status,cf}`, `db {apply,upgrade}`, `export turtle`, `validate shacl`. Les sous-commandes non implémentées affichent un message clair avec pointeur vers l'item de backlog.
  - `.env.example` — modèle de configuration commentée.
  - `tests/__init__.py` — squelette pour les tests à venir.
  - Couvre les items `E3-01`, `E3-02`, `E3-03`, `E3-04` du backlog.
- **`docs/adr/template.md`** — gabarit MADR 4.0 pour les futurs ADR. 8 sections (contexte, drivers, options, décision, conséquences, pros/cons des options écartées, validation, références) avec consignes d'usage. Couvre l'item `E1-07` du backlog.
- **`schema_v4_skos.sql`** — schéma PostgreSQL refondu sur SKOS Core. Trois étages : SKOS Core (`scheme`, `concept`, `concept_label`, `concept_in_scheme`, `concept_semantic_relation`, `concept_note`, `concept_mapping`), extension typage physique (`concept_physical`, `unite`), bloc gouvernance refondu. Triggers d'audit posés sur `scheme`, `concept`, `unite`. Sept vues métier (`v_concepts_actifs`, `v_concepts_mesurables`, `v_concept_descendants`, `v_concept_ancestors`, `v_proposals_pending`, `v_audit_recent`, `v_imports_status`, `v_concepts_traduction_pending`). Couvre les items `E2-01`, `E2-02`, `E2-03`, `E2-05`, `E2-06`.
- Avertissement de dépréciation ajouté en tête de `schema_referentiel_v3.sql` (item `E2-11` traité — conservé en référence).

### Modifié

- **`README.md`** :
  - Section démarrage rapide réécrite pour pointer sur `schema_v4_skos.sql`. Tableau d'état actualisé.
  - Bandeau de licences (badges Apache 2.0 + CC-BY 4.0) et mention auteur ajoutés en tête, sous le titre.
  - Section « Contact » remplacée par « Auteurs et contact » avec rôles, lien vers les issues, mention d'acceptation des licences pour les contributions.

### Retiré

- **`CLAUDE.md`** — fichier d'instructions locales pour Claude Code retiré du suivi git et ajouté au `.gitignore`. Le fichier reste présent sur disque chez les contributeurs qui l'utilisent, mais n'est plus publié dans le dépôt distant. Référence à `CLAUDE.md` retirée du `README.md`.

### Ajouté

- **ADR 0003** — Domaine d'URI stable (`docs/adr/0003-domaine-uri-w3id-org.md`). Adoption de `https://w3id.org/nephos/vocab/{scheme}/{notation}` comme racine canonique des URI. Service du W3C Permanent Identifier Community Group, gratuit, permanence garantie. Préfixe à réserver via PR sur `perma-id/w3id.org` (item `E1-10` ajouté au backlog).
- **ADR 0004** — Stratégie multilingue (`docs/adr/0004-strategie-multilingue-fr-en.md`). `prefLabel@fr` et `prefLabel@en` obligatoires pour qu'un concept passe au statut `published` ; autres labels, notes et autres langues en best effort ; pas de traduction machine silencieuse. Contrainte SHACL à coder dans les shapes Nephos.
- **ADR 0005** — Licences (`docs/adr/0005-licences-apache-2-et-cc-by-4.md`). Double licence : Apache 2.0 (code, schéma SQL, scripts, doc d'ingénierie) + CC-BY 4.0 (données originales et traductions). Données importées conservent leur licence d'origine, attribution amont préservée via `concept_mapping` et `dcterms:source` dans les exports RDF.
- **`LICENSE`** — texte canonique d'Apache 2.0 à la racine (couvre le code et la documentation d'ingénierie).
- **`DATA_LICENSE`** — note explicative CC-BY 4.0 à la racine (couvre les données originales Nephos), avec inventaire des licences amont et politique d'attribution.
- **Items** `E1-01`, `E1-02`, `E1-03` du backlog marqués fait. Nouvel item `E1-10` (réservation w3id.org) à programmer.
- **`README.md`** racine — vision et périmètre du projet, architecture en une page, état actuel, démarrage rapide, index documentaire et tableau des ADR. Couvre l'item `E1-08` du backlog (marqué fait).
- **ADR 0009** — Stratégie d'orchestration ETL (`docs/adr/0009-strategie-orchestration-etl.md`). Acte un démarrage en code Python pur orchestré par GitHub Actions, avec Kestra (origine FR, Apache 2.0) comme cible explicite déclenchée par signaux observables. Disqualifie Airflow, Dagster et Prefect au titre de la souveraineté FR/EU. Met à jour le backlog : item `E1-09` ajouté et marqué fait.
- **`BACKLOG.md`** — backlog initial du projet structuré en 9 EPICs (gouvernance, schéma SQL, bootstrap Python, imports, validation, exports, API, curation, ops). Inclut Definition of Ready, Definition of Done, priorités (P0/P1/P2), estimations T-shirt, dépendances et deux sprints candidats prêts à embarquer.
- **ADR 0002** — Python comme stack d'implémentation du pipeline sémantique (`docs/adr/0002-python-comme-stack-dimplementation.md`). Acte le choix de Python 3.12+ pour l'ETL d'import (`rdflib`, `pyshacl`, `lxml`), la validation SHACL, l'export RDF/SKOS et le CLI opérateurs. Diffère explicitement le choix de la façade API à un ADR 0003 ultérieur.
- **ADR 0001** — adoption de SKOS (W3C) comme socle conceptuel du référentiel de métadonnées météo (`docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md`). Acte la refonte du modèle `vocab.types_grandeur` + `vocab.champs` en taxonomie multi-hiérarchique, restreint le périmètre aux concepts (option A) et exclut explicitement les tables `catalog.*`, `vocab.acteurs` et `vocab.licences`. Définit la stratégie de remplissage par import majoritaire (CF, QUDT, WMO) plutôt que par saisie manuelle.
- Initialisation du dépôt Git (branche `main`).
- `schema_referentiel_v3.sql` — schéma PostgreSQL initial du référentiel météorologique (v3, 873 lignes, schémas `gov` / `vocab` / `catalog`).
- `CLAUDE.md` — guide d'architecture à destination de Claude Code.
- `.gitignore` — exclusions standard (OS, éditeurs, dumps PostgreSQL, secrets, caches Python).

### Décisions d'architecture (ADR)

| ID | Titre | Statut |
|----|-------|--------|
| [0001](docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md) | Adopter SKOS comme socle du référentiel de métadonnées météo | Accepté |
| [0002](docs/adr/0002-python-comme-stack-dimplementation.md) | Python comme stack d'implémentation du pipeline sémantique | Accepté |
| 0003 | Domaine d'URI stable (engagement irréversible) | À rédiger |
| 0004 | Stratégie multilingue (FR seul vs FR+EN) | À rédiger |
| 0005 | Licence des données importées et de publication | À rédiger |
| 0006 | Choix de la façade API (REST custom / GraphQL / auto-génération sur Postgres) | À rédiger |
| 0007 | Outil de curation (Directus / VocBench / app custom) | À rédiger |
| 0008 | Conteneurisation et déploiement | À rédiger |
| [0009](docs/adr/0009-strategie-orchestration-etl.md) | Stratégie d'orchestration ETL (Python + GHA → Kestra sur signal) | Accepté |
| [0010](docs/adr/0010-nephos-comme-moteur-de-validation.md) | Étendre le périmètre aux outils de validation (GRIB, NetCDF, BUFR…) | Accepté |
