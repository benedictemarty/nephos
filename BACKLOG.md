# Backlog — Nephos

**Nephos** est le **nom du programme** d'une plateforme SI météo gouvernée Po-scale. Le programme se compose de plusieurs **briques techniques nommées** :

```
Nephos (programme)
├── Nephos Vocab       — couche sémantique (SKOS + CF + QUDT + WMO + ECMWF)  ← existe
├── Nephos Catalog     — catalogue technique Iceberg + Lakekeeper             📋 E11
├── Nephos Storage     — stockage objet MinIO/Ceph + Zarr / Parquet            📋 E12
├── Nephos Workflow    — orchestration Dagster ou Kestra                       📋 E13
├── Nephos Contracts   — data contracts versionnés en Git                      📋 E14
├── Nephos Watch       — alerting métier + fraîcheur SLA + complétude          📋 E15-E16
├── Nephos Vault       — habilitations + classifications L0-L3 (ABAC)          📋 E17
├── Nephos Capture     — saisie opérateur (DataWindow)                         📋 E18
└── Nephos Trace       — modifications append-only event sourcing              📋 E19
```

Chaque sous-marque désigne **l'intégration et la gouvernance** d'une couche. Les briques OSS sous-jacentes (Iceberg, Lakekeeper, Dagster, Kestra, OPA, etc.) gardent leurs noms d'origine. Nephos est l'**intégrateur**, pas un fork.

Vision détaillée dans [`docs/architecture/`](docs/architecture/).

Voir [ADR 0001](docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md) (SKOS) et [ADR 0002](docs/adr/0002-python-comme-stack-dimplementation.md) (Python) pour le socle de Nephos Vocab. ADRs 0006 à 0019 (autres composants) à rédiger après confirmation sponsor / scope / budget / équipe.

## Réalignement (2026-05)

| EPIC | Statut | Composant Nephos |
|------|--------|------------------|
| E1 — Gouvernance architecturale et documentaire | ✅ majoritairement fait | Programme global |
| E2 — Refonte schéma SQL SKOS | ✅ fait | **Nephos Vocab** |
| E3 — Bootstrap projet Python | ✅ fait | **Nephos Vocab** (socle applicatif) |
| E4 — Pipeline d'import sources standards | ✅ majoritairement fait | **Nephos Vocab** (acquisition sémantique) |
| E5 — Validation et qualité sémantique | ✅ fait | **Nephos Vocab** (qualité sémantique) |
| E6 — Export et interopérabilité | ✅ partiellement | **Nephos Vocab** (diffusion sémantique) |
| E7 — Façade API | 📋 ouvert | **Nephos Vocab** (API service) |
| E8 — Curation et publication | 📋 ouvert | **Nephos Vocab** (curation) |
| E9 — Opération et observabilité | 📋 ouvert | **Nephos Vocab** (observabilité interne) |
| E10 — Outils de validation de fichiers | 📋 ouvert | **Nephos Vocab** (consumers de la sémantique) |
| **E11 — Nephos Catalog (Iceberg + Lakekeeper)** | 📋 nouveau | Capacité « Cataloguer » + « Stocker » |
| **E12 — Nephos Storage (objet + Zarr gridded)** | 📋 nouveau | Capacité « Stocker » (gridded Po-scale) |
| **E13 — Nephos Workflow (Dagster ou Kestra)** | 📋 nouveau | Capacités « Acquérir » + « Calculer » + « Évoluer » |
| **E14 — Nephos Contracts (gouvernance)** | 📋 nouveau | Capacité « Gouverner » transverse |
| **E15 — Nephos Watch (alerting métier — annexe A)** | 📋 nouveau | Capacité « Surveiller » + service consumer |
| **E16 — Nephos Watch (fraîcheur + complétude — annexes B, C)** | 📋 nouveau | Capacité « Surveiller » |
| **E17 — Nephos Vault (habilitations L0-L3 — annexe H)** | 📋 nouveau | Capacité « Habiliter » |
| **E18 — Nephos Capture (saisie opérateur — annexe F)** | 📋 nouveau | Capacité « Saisir » |
| **E19 — Nephos Trace (modifications append-only — annexe G)** | 📋 nouveau | Capacité « Évoluer » + traçabilité |

EPICs E11-E19 ne démarrent qu'après **décisions de cadrage** (sponsor, scope, budget, équipe).

## Conventions

- **Priorité** : `P0` bloquant / `P1` devrait être dans les 2-3 prochains sprints / `P2` nice-to-have ultérieur.
- **Taille** : T-shirt — `XS` ½ jour · `S` 1-2 jours · `M` 3-5 jours · `L` 1-2 sem. · `XL` > 2 sem.
- **État** : `📋 todo` · `🚧 en cours` · `✅ fait` · `⏸️ bloqué` · `❌ abandonné`.
- **ID** : `<EPIC>-<numéro>`. Stable, ne se réutilise pas.

### Definition of Ready (DoR)

Un item entre dans un sprint quand :

- la valeur métier est exprimée (ce que ça apporte) ;
- les critères d'acceptation sont écrits et testables ;
- les dépendances sont satisfaites ou explicitement assumées ;
- l'estimation est posée par l'équipe.

### Definition of Done (DoD)

Un item est terminé quand :

- le code (ou la doc) est versionné dans `main` ;
- les tests automatisés passent (≥ 80 % de couverture sur le code applicatif neuf) ;
- le `CHANGELOG.md` est mis à jour ;
- la documentation associée est à jour (CLAUDE.md, ADR, README ou docstrings selon le cas) ;
- pour un ADR : le fichier respecte le format MADR et est référencé dans le tableau du `CHANGELOG.md`.

---

## EPIC 1 — Gouvernance architecturale et documentaire

Décisions structurantes à acter avant d'écrire du code en quantité.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E1-01 | ADR 0003 — Domaine d'URI stable. Décision : `https://w3id.org/nephos/vocab/{scheme}/{notation}`. | **P0** | S | — | ✅ |
| E1-02 | ADR 0004 — Stratégie multilingue. Décision : `prefLabel@fr` ET `prefLabel@en` obligatoires sur les concepts publiés. | P0 | XS | — | ✅ |
| E1-03 | ADR 0005 — Licences. Décision : Apache 2.0 (code) + CC-BY 4.0 (données originales) + sources amont sous licence d'origine. | P0 | S | — | ✅ |
| E1-10 | Réservation du préfixe `nephos` sur `perma-id/w3id.org` (PR + `.htaccess` initial pointant sur placeholder). | P1 | S | E1-01 | 📋 |
| E1-11 | Activer les **branch protection rules** sur `main` côté GitHub : PR obligatoire, ≥1 review humaine approuvée, 7 status checks (`Lint, format, hygiene`, `Type-check (mypy strict)`, `Security (bandit, pip-audit)`, `Tests (pytest, Postgres 14)`, `Tests (pytest, Postgres 16)`, `Docstring coverage (interrogate)`, `Build sdist + wheel`), dismiss stale reviews, linear history, restrict push, no admin bypass, no force push, no deletion, conversation resolution required. Appliqué via `gh api` (cf. ADR 0011). Validé via ADR 0012 (CVE bloquante PYSEC-2022-42969 traitée). | **P0** | XS | — | ✅ |
| E1-12 | **Agent reviewer GitHub Actions** : `anthropics/claude-code-action@v1` authentifié par OAuth Max (`CLAUDE_CODE_OAUTH_TOKEN`), workflow `.github/workflows/agent-review.yml`, prompt structuré qui charge le contexte ADR pertinent et impose le format de rapport en 6 sections + verdict (CONTRIBUTING.md § 1 niveau 2). Permissions minimales (`contents: read`, `pull-requests: write`, `issues: write`), pas de `pull_request_target`, concurrence par branche. Décision actée par ADR 0013. | P1 | M | E1-11 | ✅ |
| E1-13 | **Adapter la chaîne de revue au cas mainteneur unique** : amender ADR 0011 via ADR 0014 (`required_approving_review_count: 0` tant qu'il n'y a qu'un mainteneur) ; conserver tous les autres verrous (status checks, linear history, enforce_admins, no force/deletion, conversation resolution). Conditions de retour à `1` documentées (CR1 second mainteneur ajouté, CR2 organisation multi-membres). | **P0** | XS | E1-11 | ✅ |
| E1-14 | **Procédure de retour** à `required_approving_review_count: 1` lorsqu'un second mainteneur entre. Documenter la commande `gh api PUT` et la mise à jour de CONTRIBUTING.md § 1. | P2 | XS | E1-13 | 📋 |
| E1-04 | ADR 0006 — Choix de la façade API (REST custom FastAPI / GraphQL via Hasura ou pg_graphql / auto-génération PostgREST). Différé en ADR 0002. | P1 | M | E2-01 | 📋 |
| E1-05 | ADR 0007 — Outil de curation (Directus / VocBench / app custom React/TS). | P2 | M | E2-* | 📋 |
| E1-06 | ADR 0008 — Stratégie de conteneurisation et déploiement (Compose dev / Kubernetes prod / autre). | P2 | M | E3-08 | 📋 |
| E1-07 | Template ADR (MADR 4.0) versionné dans `docs/adr/template.md` pour homogénéiser les futures décisions. | P1 | XS | — | ✅ |
| E1-08 | `README.md` racine — vision projet, architecture en 1 page, comment démarrer, liens vers ADR et backlog. | P1 | S | — | ✅ |
| E1-09 | ADR 0009 — Stratégie d'orchestration ETL (Python pur + GHA en phase 1, Kestra en cible phase 2 sur signal). | P0 | S | — | ✅ |

---

## EPIC 2 — Refonte du schéma SQL sur le modèle SKOS

Réécriture du `schema_referentiel_v3.sql` en `schema_v4_skos.sql`. Voir ADR 0001 pour la décision de fond.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E2-01 | Schéma SKOS Core minimal (`scheme`, `concept`, `concept_label`, `concept_in_scheme`, `concept_semantic_relation`, `concept_note`) avec contraintes (`UNIQUE`, `CHECK`, FK). | **P0** | M | E1-01, E1-02 | ✅ |
| E2-02 | Extension typage physique (`concept_physical`, lien à `unite` et `unite_conversion`). | P0 | S | E2-01 | ✅ |
| E2-03 | Bloc gouvernance refondu (réutilise `users`, `roles`, `statuses`, `audit_log`, `proposals`, `imports`, `import_sources`) sur le modèle SKOS. | P0 | M | E2-01 | ✅ |
| E2-04 | **Trigger d'audit étendu** : 7 nouveaux triggers ajoutés à `schema_v4_skos.sql` (section 5) sur `vocab.concept_label`, `vocab.concept_note`, `vocab.concept_in_scheme`, `vocab.concept_semantic_relation`, `vocab.concept_mapping`, `vocab.concept_physical` et `gov.proposals`. Tous utilisent `gov.audit_trigger_func` avec leur PK explicite. Couverture totale `gov.audit_log` : 10 tables (3 préexistantes + 7 nouvelles). 7 tests d'intégration (`tests/integration/test_schema_audit_extended.py`) couvrant INSERT/UPDATE/DELETE/STATUS_CHANGE — incluant la distinction STATUS_CHANGE sur `gov.proposals` et la propagation de `changed_columns` sur `concept_note`. | P1 | S | E2-01, E2-03 | ✅ |
| E2-05 | Vues métier — `v_concepts_actifs`, `v_concepts_mesurables`, `v_proposals_pending`, `v_audit_recent`, `v_imports_status`, `v_concepts_traduction_pending`. | P1 | S | E2-01, E2-03 | ✅ |
| E2-06 | Vues récursives `v_concept_descendants` / `v_concept_ancestors` (`WITH RECURSIVE`, tolérantes aux cycles). | P1 | S | E2-01 | ✅ |
| E2-07 | Tests d'intégrité du schéma : 3 modules (`test_schema_constraints.py` 23 tests, `test_schema_views.py` 8 tests, `test_schema_audit.py` 6 tests) — couvrent contraintes URI/notation/lang/prefLabel, vues métier (incluant la résolution récursive tolérante aux cycles), triggers d'audit (INSERT/UPDATE/STATUS_CHANGE/DELETE). | P0 | M | E2-01, E3-04 | ✅ |
| E2-08 | Migration alembic initiale capturant le schéma v4 (point de départ versionné). | P1 | S | E2-01, E3-09 | ✅ |
| E2-09 | Diagramme entité-relation auto-généré (`schemaspy` ou `tbls`) commité dans `docs/schema/`. | P2 | XS | E2-01 | 📋 |
| E2-10 | Glossaire des entités SKOS (1 page) — pour onboarding non-développeur. | P2 | XS | E2-01 | 📋 |
| E2-11 | Décision sur la conservation ou non du `schema_referentiel_v3.sql` (archive vs suppression). | P1 | XS | E2-01 | ✅ (avertissement ajouté en en-tête, conservé en référence) |

---

## EPIC 3 — Bootstrap du projet Python

Mise en place du squelette technique du backend Python.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E3-01 | `pyproject.toml` initialisé avec `uv` ; layout `src/nephos/`. | **P0** | XS | — | ✅ |
| E3-02 | Dépendances de base : `rdflib`, `pyshacl`, `lxml`, `requests`, `SPARQLWrapper`, `pydantic`, `pydantic-settings`, `psycopg`, `typer`. | P0 | XS | E3-01 | ✅ |
| E3-03 | CLI squelette `nephos --help` avec sous-commandes (`import`, `validate`, `export`, `db`) renvoyant un message « pas encore implémenté » avec pointeur vers l'item de backlog. | P0 | S | E3-02 | ✅ |
| E3-04 | Configuration applicative typée (URL Postgres, dossiers de travail, log level, uri_base) via `pydantic-settings` + `.env.example`. | P0 | XS | E3-02 | ✅ |
| E3-05 | Logging structuré (`text` humain ou `json` structuré) configurable par `NEPHOS_LOG_FORMAT`. Module `nephos.logging` avec `configure_logging()` (idempotent) et `get_logger(name)`. Appelé en tête de la callback CLI. | P1 | XS | E3-04 | ✅ |
| E3-06 | Pre-commit hooks complets : hygiène (EOF, trailing ws, large files, JSON/YAML/TOML), `gitleaks` (secrets), `ruff` (lint+format), `mypy` (typage strict), `bandit` (sécu statique), `deptry` (deps inutilisées/manquantes), `validate-pyproject`, `yamllint`, `markdownlint`, `sqlfluff` (final newline). Mutmut, pip-audit, vulture, interrogate déclarés en dev-deps mais hors pre-commit (invocation CI ou manuelle). Configurations correspondantes dans `pyproject.toml`, `.yamllint.yaml`, `.markdownlint.yaml`. | P0 | M | E3-01 | ✅ |
| E3-07 | CI GitHub Actions : workflow `ci.yml` (lint via pre-commit, mypy strict, sécu bandit + pip-audit, docstring coverage interrogate, tests pytest sur Postgres 14 et 16, build sdist+wheel) + workflow `nightly.yml` (mutmut, pip-audit strict, vulture). Concurrence par branche, cancel-in-progress. | P0 | M | E3-06 | ✅ |
| E3-08 | `Dockerfile` multi-stage : builder Python 3.12-slim avec uv pinné, runtime fin avec libpq5/libxml2/libxslt1.1/ca-certificates, utilisateur non-root `nephos`. ENTRYPOINT = CLI Nephos, CMD = `--help`. `.dockerignore` complet. | P1 | S | E3-01 | ✅ |
| E3-09 | Squelette Alembic configuré : `alembic.ini`, `alembic/env.py` (URL lue depuis `Settings`, target_metadata=None car pas d'ORM), `script.py.mako`, `alembic/README.md` documentant le workflow. Première migration `0001` qui applique `schema_v4_skos.sql` en bloc (cumule E2-08). | P0 | S | E3-01, E3-04 | ✅ |
| E3-10 | `docker-compose.yml` dev : service `postgres` (16-alpine) avec volume nommé `nephos-pg-data`, healthcheck `pg_isready`, init du schéma via `docker-entrypoint-initdb.d`. Service `nephos` profil `cli` (pas démarré par défaut, invoqué via `compose run`). | P1 | S | E3-08 | ✅ |
| E3-11 | Squelette de tests (`tests/`, `tests/integration/`) + `conftest.py` avec fixtures `db_conn` (recréation du schéma avant chaque test, skip si `NEPHOS_DATABASE_URL` non défini), `admin_user_id`. Tests unitaires CLI (`test_cli.py`) et logging (`test_logging.py`) sans dépendance Postgres. | P0 | S | E3-02 | ✅ |

---

## EPIC 4 — Pipeline d'import des sources standards

Implémentation des imports — partie qui livre la valeur fonctionnelle visible. Voir ADR 0001 pour la stratégie.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E4-01 | Framework ETL générique : interface `Importer` (ABC : `discover_version`, `extract`, `transform`, `load`), `ImportRunner` orchestrateur (cycle `discover → open journal → extract → transform → load → close` ou `failed`), `RunOptions` (force, user_id, dry_run), journal `gov.imports` (open/close/failure récupérée hors-transaction), exceptions typées, helpers `nephos.db.connect()`. 5 tests d'intégration valident création/idempotence/échec rollback/dry-run/source inconnue. | **P0** | M | E2-01, E3-03 | ✅ |
| E4-02 | Import **CF Standard Names** : `CFStandardNamesImporter` parse l'XML CF (URL officielle ou fichier local), normalise les notations en minuscules (ADR 0003), conserve l'identifiant CF original dans `concept_physical.cf_standard_name`, crée le scheme `grandeurs-cf`, pose `concept_label@en` humanisé, `concept_note@en` (definition), `concept_in_scheme`, `concept_mapping` (`exactMatch` vers fiche CF) et `concept_physical` avec résolution best-effort des unités via `vocab.unite.symbole`. Statut initial `approved` (ADR 0004 : `published` requiert FR). 8 tests d'intégration sur fixture mini. **Validation live : 5023 concepts importés en 16s (< 5 min ✅).** Idempotence vérifiée (re-run 0 création). | **P0** | M | E4-01 | ✅ |
| E4-03 | Import **CF Area Type** (62 concepts en live ; URL officielle disponible) — `CFAreaTypeImporter` réutilise les helpers SQL du CF importer + scheme dédié `area-types-cf` + `_upsert_concept` local qui renseigne `import_source_id`. CLI `nephos import cf-area`. 3 tests d'intégration. **CF Cell Methods et CF Regions** : URLs publiques pas trouvées (404 sur les chemins canoniques) ; reportés en E4-03b si une source publique apparaît. | P0 | S | E4-02 | ✅ partiel (Area Type) |
| E4-03b | Import CF Cell Methods + CF Regions si une source publique stable est identifiée. À voir avec la communauté CF. | P2 | S | E4-03 | 📋 |
| E4-04 | Import **QUDT Units** : `QUDTUnitsImporter` parse le Turtle QUDT via `rdflib`, stocke les unités dans `vocab.unite` avec `qudt_uri` (idempotence par URI, rapprochement par symbole pour enrichir les unités préexistantes), détecte les SI canoniques (multiplier=1 + pas d'offset + applicableSystem SI), gère les collisions de symbole (skip + warning). 7 tests d'intégration sur fixture mini. **Validation live** : 2490 unités QUDT importées en 11s ; 84 collisions de symbole (doublons sémantiques attendus). Re-import CF après QUDT : **560 unités CF résolues** (vs 17 avant). Mapping symboles CF↔QUDT plus poussé reporté en E4-04b. | P0 | M | E4-01, E2-02 | ✅ |
| E4-04b | **Mapping symboles CF ↔ QUDT** : module `nephos.importers._unit_symbols` avec `normalize_cf_to_qudt(s)` qui convertit la notation CF (tokens espacés, exposants signés `m s-1`) en notation QUDT (numérateur·...·/dénominateur, exposants Unicode `m/s`). Intégré dans `_resolve_unit` du CF importer comme 2e candidat de match. **Gain mesuré en live : résolution unités CF passe de 11,2 % à 80,1 %** (+3462 sur 5023, ×7). 18 tests unitaires couvrent les cas typiques (cf. `tests/test_unit_symbols.py`). | P1 | S | E4-04 | ✅ |
| E4-04c | Import **QUDT QuantityKinds** (grandeurs physiques) — couche concept au-dessus des unités. À évaluer vs duplication avec CF Standard Names. | P2 | M | E4-04 | 📋 |
| E4-05 | Import **WMO Codes Registry** : `WMOCodesImporter` paramétrable par register URL + scheme cible Nephos ; presets `bufr-0-02-001` (Type of station), `bufr-0-02-002` (Wind instrumentation), `bufr-0-02-003` (Measuring equipment), `bufr-0-08-021` (Time significance). Parse Turtle SKOS WMO via `rdflib`, version = `dct:modified` du register, `exactMatch` vers URI WMO. CLI `nephos import wmo-codes --code-list <preset>` ou `--register-url ... --scheme-code ...`. 5 tests d'intégration. **Validation live BUFR 0-08-021 : 31 concepts importés, 0 violation SHACL, idempotence ✅.** Listes additionnelles ajoutables ultérieurement en dérivant un nouveau preset. | P1 | M | E4-01 | ✅ |
| E4-06 | Mappings **ECMWF Parameter Database** (alignement par mapping seul, pas de clone) — `ECMWFMappingsImporter` parse `cfName.def` du dépôt `ecmwf/eccodes` (Apache 2.0) qui mappe explicitement chaque CF Standard Name vers son triplet GRIB2 (`discipline`, `parameterCategory`, `parameterNumber`). Pour chaque CF dans cfName.def présent en base sous `grandeurs-cf`, pose un `concept_mapping closeMatch` vers une URL filtrée du Parameter Database (`https://codes.ecmwf.int/grib/param-db/?discipline=D&parameterCategory=C&parameterNumber=N`). `discover_version` = MD5 court du fichier. Idempotent par contrainte unique `(concept_id, target_uri, mapping_relation)`. CLI `nephos import ecmwf-mappings`. 7 tests (intégration + unitaires de parsing). **Validation live** : 47 entrées parsées depuis ecCodes develop. **V2 à venir** : résolution vers un `id` ECMWF spécifique en présence de `typeOfStatisticalProcessing`/`typeOfFirstFixedSurface`. | P1 | M | E4-01 | ✅ |
| E4-07 | Mappings **NERC BODC** P01/P02 via SPARQL endpoint (alignement par mapping seul). | P2 | M | E4-01 | 📋 |
| E4-08 | **Détection des concepts disparus** côté source : module `nephos.etl.deprecation.mark_disappeared_concepts` qui marque en `status='deprecated'` les concepts d'un `import_source_id` dont `import_version` ne correspond plus à la version courante, ciblés par `concept_in_scheme`. Intégré dans `ImportRunner` (option `RunOptions.detect_disappeared=True` par défaut). Nouvel hook `Importer.target_scheme_codes()` (default `None` = désactivé) déclaré par `CFStandardNamesImporter`, `CFAreaTypeImporter`, `WMOCodesImporter` ; `QUDTUnitsImporter` reste opt-out (touche `vocab.unite`, pas `vocab.concept`). Préservation explicite des concepts `has_local_override = TRUE`. Compteur `ImportResult.nb_deprecated_disappeared` exposé en CLI. 6 tests d'intégration (fixture amputée `wmo_bufr_0_02_001_partial.ttl`) couvrant : nominal, 2 disparus, override protégé, désactivation, scheme isolation cross-source, scheme_codes vide = no-op. | P1 | S | E4-01 | ✅ |
| E4-09 | Commande `nephos import status` : SELECT sur la vue `gov.v_imports_status`, sortie Rich avec source/nom/licence/versions/dernière import/nb concepts/overrides. **Bug fix collatéral** : le CF importer n'écrivait pas `concept.import_source_id`, corrigé. 2 tests d'intégration. | P1 | S | E4-01 | ✅ |
| E4-10 | Tests d'intégration : un test bout-en-bout par source, avec snapshot de la source figé en fixture. | P0 | M | E4-02..07, E3-11 | 📋 |

---

## EPIC 5 — Validation et qualité sémantique

Protection contre la dérive du référentiel.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E5-01 | Shapes SHACL Core (`shapes/nephos_skos_core.ttl`) : URI Nephos (ADR 0003), notation regex (ADR 0003), prefLabel ≥1 + uniqueLang, **PublishedConcept** virtuel imposant FR+EN (ADR 0004), pas de self-broader (SKOS S27). Module `nephos.validators.shacl_runner` construit le graphe RDF depuis Postgres et exécute pyshacl. CLI `nephos validate shacl [--scheme CODE] [--strict] [--report]`. **Validation live : 5023 concepts CF conformes en mode normal ; 5023 violations en mode --strict** (file de traduction FR identifiée). 5 tests d'intégration. | P0 | M | E2-01 | ✅ |
| E5-02 | Shapes SHACL Nephos métier (`shapes/nephos_metier.ttl`) : `MeasurableConceptShape` (value_type ∈ enum, Violation), `NumericMeasurableShape` (concept scalaire/vectoriel/tensoriel doit avoir une unité, Warning), `AttributionShape` (concept publié → dcterms:source OU skos:definition, Warning), `InSchemeShape` (concept orphelin → Warning, à durcir plus tard). `SHACLValidator` enrichit le graphe : skos:inScheme, dcterms:source, marqueurs nephos:MeasurableConcept/NumericMeasurableConcept/valueType/hasUnit. 4 tests d'intégration. | P1 | M | E5-01, E2-02 | ✅ |
| E5-03 | Validation systématique post-import : `RunOptions.validate_after` (défaut `True`) chaîne SHACL après `load`, compteurs ajoutés en `notes` du `ImportResult`. Mode `strict_validation=True` lève `ImportValidationError` et rollback la transaction de chargement. 4 tests d'intégration. | P0 | S | E5-01, E4-01 | ✅ |
| E5-04 | **Rapport qualité automatisé** : `nephos.validators.quality_report.QualityReporter` exécute 8 détecteurs sur la base — `concepts_without_pref_label` (error), `concepts_without_scheme` (warning), `concepts_self_broader` (error, défense en profondeur — la CHECK constraint le bloque déjà), `duplicate_pref_label_lang` (error, défense en profondeur), `duplicate_notation_in_scheme` (error), `duplicate_mappings` (error), `missing_pref_label_fr/en` (warning, ADR 0004). Filtrage par scheme via `scheme_code`. Sortie structurée `QualityReport` avec `findings: list[QualityFinding]` (code, label, severity, count, samples ≤ 5). CLI `nephos validate quality [--scheme CODE] [--fail-on-error]`. 11 tests d'intégration (un par détecteur + filtrage scheme + structure rapport). | P1 | M | E5-01 | ✅ |
| E5-05 | **Commande `nephos validate all`** combinant SHACL Core + rapport qualité (E5-04) sur un sous-ensemble (`--scheme CODE`). Mode `--strict` (SHACL publié strict, ADR 0004) et `--fail-on-error` (exit 2 si SHACL non conforme OU qualité signale ≥ 1 erreur — exploitable en CI). Sortie Rich unifiée (5 lignes par phase). 3 tests d'intégration via `typer.testing.CliRunner` : base saine exit 0, erreur qualité + `--fail-on-error` exit 2, erreur sans flag exit 0. Les commandes individuelles `validate shacl` et `validate quality` restent disponibles. | P1 | S | E5-03 | ✅ |

---

## EPIC 6 — Export et interopérabilité

Rendre le référentiel consommable hors-Postgres.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E6-01 | Export RDF/SKOS — module `nephos.exporters.SKOSExporter` charge depuis Postgres et sérialise en Turtle/RDF-XML/JSON-LD/N3 via rdflib. Couvre : `skos:Concept` + notation + prefLabel/altLabel/hiddenLabel multilingues + skos:definition/scopeNote/example/historyNote, `skos:inScheme` + `skos:topConceptOf` + `skos:hasTopConcept`, broader/narrower/related internes, *Match externes (mappings amont), `dcterms:license` (CC-BY 4.0 ADR 0005), `dcterms:source` (URL source amont). CLI `nephos export turtle [SCHEME] [-o FILE] [-f FORMAT]`. **Validation live : 5023 concepts CF exportés en 2s, 35154 lignes Turtle valide, parsing rdflib OK** (critère ADR 0001 atteint). 6 tests d'intégration. | P1 | S | E2-01 | ✅ |
| E6-02 | Export **RDF/XML** et **JSON-LD** (sérialisations alternatives via `rdflib`). | P2 | XS | E6-01 | 📋 |
| E6-03 | **Validation des exports par un outil tiers** : `nephos.validators.skos_external.SkosExternalValidator` réutilise `SKOSExporter` (E6-01) pour produire le graphe Turtle qui serait publié, puis exécute les 5 checks SKOS standards de la lib **`skosify`** (NatLibFi, MIT) — `hierarchy_cycles`, `disjoint_relations`, `preflabel_uniqueness`, `hierarchical_redundancy`, `label_overlap`. Capture des warnings via un handler logging dédié, classification par regex sur le message vers un code stable (`hierarchy_cycles`, `disjoint_relations`, …). Sortie structurée `SkosExternalReport` avec `issues: list[SkosExternalIssue]` et `by_check()`. CLI `nephos validate skos-external [--scheme CODE] [--issues] [--fail-on-issue]`. 6 tests d'intégration (graphe propre conforme, cycle détecté, disjonction détectée, classification, agrégation). Choix `skosify` plutôt que Skosmos (JVM lourd) ou SKOS-Play (en ligne, hors CI) : exécutable en CI, validation SKOS standard. | P1 | S | E6-01 | ✅ |
| E6-04 | Export différentiel (delta entre deux versions du référentiel) pour publication incrémentale. | P2 | M | E6-01 | 📋 |

---

## EPIC 7 — Façade API

À démarrer après l'ADR 0003 façade API. Périmètre dépendant du choix.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E7-01 | API MVP (lecture seule) couvrant : recherche par notation/label, hiérarchie d'un concept, mappings d'un concept, listing par scheme. | P1 | L | E1-04, E2-* | 📋 |
| E7-02 | Documentation API (OpenAPI ou GraphQL Schema selon ADR 0004) auto-générée. | P1 | S | E7-01 | 📋 |
| E7-03 | Tests d'intégration API (golden path par endpoint). | P1 | M | E7-01 | 📋 |
| E7-04 | Stratégie d'authentification et d'autorisation (anonyme lecture, auth pour mutations futures). | P2 | M | E1-04 | 📋 |

---

## EPIC 8 — Curation et publication

Après MVP technique. Concerne l'expérience utilisateur curateur et consommateur.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E8-01 | Choix outil de curation (Directus, VocBench, app custom) → ADR 0007. | P2 | — | E1-05 | 📋 |
| E8-02 | Déploiement Skosmos en lecture seule sur l'export RDF, comme « façade publique ». | P2 | M | E6-01 | 📋 |
| E8-03 | URI résolvables : redirection HTTP de `https://nephos.meteo.fr/vocab/...` vers HTML (Skosmos) ou RDF (selon `Accept`). | P2 | M | E1-01, E8-02 | 📋 |
| E8-04 | Workflow de proposition (`gov.proposals`) côté UI curateur. | P2 | L | E8-01 | 📋 |

---

## EPIC 10 — Outils de validation et qualité de données

Acté en [ADR 0010](docs/adr/0010-nephos-comme-moteur-de-validation.md). Outils consommateurs qui exploitent le référentiel pour qualifier des fichiers externes (GRIB, NetCDF, BUFR…) sans rien stocker ni modifier le référentiel automatiquement.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E10-01 | Architecture de la commande `nephos validate <format>` — interface plugin (`extract` / `resolve` / `report`) commune à tous les formats. | P1 | M | E3-03 | 📋 |
| E10-02 | Validateur GRIB1 / GRIB2 via `eccodes` + `cfgrib`. Résolution `paramId` → concept Nephos via `concept_mapping` (source `ECMWF_PARAMS`), fallback CF Standard Names. | P1 | L | E10-01, E4-06 | 📋 |
| E10-03 | Rapport de validation au format Rich (interactif terminal), JSON et Markdown. | P1 | M | E10-01 | 📋 |
| E10-04 | Mode `--suggest` : génère des propositions de mappings manquants en `gov.proposals` lorsqu'un paramètre externe n'est pas résolu. Aucune écriture ailleurs. | P2 | M | E10-02 | 📋 |
| E10-05 | Validateur NetCDF-CF via `xarray` — vérification des attributs `standard_name`, `units`, `cell_methods` contre le référentiel. | P2 | L | E10-01, E4-02 | 📋 |
| E10-06 | Validateur BUFR via `pdbufr` ou équivalent — descripteurs WMO ↔ concepts Nephos. | P2 | L | E10-01, E4-05 | 📋 |
| E10-07 | Action GitHub publiée (`benedictemarty/nephos-validate-action`) pour valider un GRIB en CI sur un dépôt tiers. | P2 | M | E10-02 | 📋 |
| E10-08 | Documentation utilisateur (`docs/validation.md`) avec exemples de sortie, codes retour et intégration CI. | P2 | S | E10-02, E10-03 | 📋 |

---

## EPIC 9 — Opération et observabilité

Pré-requis production. Hors MVP.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E9-01 | Métriques Prometheus exposées par le CLI/API (durée d'import, nb concepts, taux d'erreur SHACL). | P2 | M | E3-* | 📋 |
| E9-02 | Healthcheck + readiness endpoints. | P2 | XS | E7-01 | 📋 |
| E9-03 | Stratégie de backup/restore Postgres (`pg_dump` versionné, restore testé). | P2 | M | — | 📋 |
| E9-04 | Runbook ops (incidents fréquents, procédures de re-sync, escalade). | P2 | S | E4-* | 📋 |
| E9-05 | Identifier la dépendance qui ramène `py` 1.11.0 dans l'arbre et tenter de la faire sortir (mise à jour amont, alternative, fork). Conditions de sortie de l'ignore PYSEC-2022-42969 (cf. ADR 0012). | P2 | S | — | 📋 |

---

## Sprint candidat 1 — « Fondations » (≈ 2 semaines)

Objectif : décisions structurantes prises, schéma SQL refondu testable, projet Python amorcé.

| Item | Pourquoi maintenant |
|------|---------------------|
| E1-01 ADR 0003 URI | Bloque les imports — un URI publié n'est pas révocable. |
| E1-02 ADR 0004 multilingue | Impacte la table `concept_label`. |
| E1-07 Template ADR | Cadre pour les futurs ADR sans surcoût. |
| E1-08 README racine | Onboarding minimal. |
| E2-01 Schéma SKOS Core | Cœur du livrable. |
| E2-02 Extension typage physique | Indissociable du Core. |
| E2-03 Bloc gouvernance refondu | Réutilise l'existant v3. |
| E2-07 Tests d'intégrité schéma | DoD = tests verts. |
| E3-01 → E3-04 Bootstrap Python | Permet d'enchaîner sur l'ETL. |
| E3-06, E3-07 Pre-commit + CI | Évite la dette de qualité. |
| E3-09 Alembic | Rend la migration versionnable dès le sprint 1. |

Indicateurs de fin de sprint :

- ADR 0003 et 0004 acceptés.
- `schema_v4_skos.sql` versionné, applicable à blanc, tests d'intégrité verts.
- `nephos --help` fonctionnel (commandes vides) avec CI verte sur `main`.

---

## EPIC 11 — Nephos Catalog (Iceberg + Lakekeeper)

Introduction du catalogue technique, fondation du data lakehouse cible. À démarrer après confirmation sponsor / scope / budget / équipe.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E11-01 | ADR 0008 — Choix Iceberg + Lakekeeper comme catalogue technique de référence | **P0** | S | Cadrage | 📋 |
| E11-02 | Déploiement Lakekeeper en local Docker compose pour POC | **P0** | M | E11-01 | 📋 |
| E11-03 | Premier dataset Iceberg : ingestion observation tabulaire (METAR ou SYNOP) | **P0** | M | E11-02 | 📋 |
| E11-04 | Lien Postgres `vocab.concept` ↔ Iceberg table column metadata (FK URI) | **P0** | M | E11-03 | 📋 |
| E11-05 | API REST `/catalog/datasets` : recherche par concept Nephos ou attribut technique | P1 | M | E11-04 | 📋 |
| E11-06 | Export du catalogue Iceberg en STAC (interopérabilité communautaire) | P2 | M | E11-04 | 📋 |
| E11-07 | Tests d'intégration end-to-end : ingestion → catalogue → lecture DuckDB | **P0** | M | E11-03 | 📋 |

---

## EPIC 12 — Nephos Storage (objet + Zarr gridded)

Introduction du stockage objet et du format Zarr v3 pour les données gridded. À démarrer après E11.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E12-01 | ADR 0009 — Format pivot Zarr v3 pour gridded météo, justification vs alternatives | **P0** | S | E11-01 | 📋 |
| E12-02 | Déploiement MinIO en local Docker compose, configuration buckets par classification | **P0** | S | E11-01 | 📋 |
| E12-03 | Premier dataset Zarr : conversion d'un GFS GRIB vers Zarr (recette versionnée) | **P0** | M | E12-02 | 📋 |
| E12-04 | Lecture Zarr via xarray + DuckDB intégrée à l'API résolveur | **P0** | M | E12-03 | 📋 |
| E12-05 | Politique de chunking optimisée par usage (lat/lon vs time-series) | P1 | M | E12-03 | 📋 |
| E12-06 | Cycle de vie hot/warm/cold/frozen via lifecycle policies S3 | P1 | M | E12-02 | 📋 |
| E12-07 | Plan de retrieval frozen testé annuellement | P1 | S | E12-06 | 📋 |

---

## EPIC 13 — Nephos Workflow (Dagster ou Kestra)

Couche orchestration unifiant les 3 modes de déclenchement (heure, ressource, pivot). Choix Dagster ou Kestra à trancher.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E13-01 | ADR 0010 — Choix orchestrateur : Dagster vs Kestra. Argument souveraineté à arbitrer | **P0** | S | Cadrage | 📋 |
| E13-02 | Déploiement orchestrateur retenu en local Docker compose | **P0** | S | E13-01 | 📋 |
| E13-03 | Asset/flow pour ingestion GFS NOMADS (mode schedule) | **P0** | M | E13-02, E11-03 | 📋 |
| E13-04 | Sensor sur commit Iceberg pour cascade downstream automatique (mode ressource) | **P0** | M | E13-03 | 📋 |
| E13-05 | Auto-materialize sur changement de recette ou de concept (mode pivot) | P1 | M | E13-04 | 📋 |
| E13-06 | Bridge SLURM optionnel pour jobs HPC | P2 | L | E13-02 | 📋 |
| E13-07 | Migration des cron / scripts ad-hoc legacy vers orchestrateur unifié | P1 | L | E13-02 | 📋 |

---

## EPIC 14 — Nephos Contracts (gouvernance par construction)

Generalisation du modèle data contract YAML versionné à toute publication. Validation CI bloquante.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E14-01 | ADR 0011 — Format de data contract YAML : schéma technique + sens métier + qualité + SLA + owner + politique d'accès | **P0** | M | E11-04 | 📋 |
| E14-02 | Validation de contract en CI : schéma cohérent, concept Nephos existant, règles qualité exécutables | **P0** | M | E14-01 | 📋 |
| E14-03 | Premier data contract pilote sur dataset Iceberg de E11-03 | **P0** | S | E14-01 | 📋 |
| E14-04 | Politique de versioning des contracts (compatibilité ascendante) | P1 | M | E14-01 | 📋 |
| E14-05 | UI / CLI de découverte des contracts | P1 | S | E14-03 | 📋 |
| E14-06 | Reporting d'écarts contract / réalité (audit semestriel automatisé) | P2 | M | E14-03 | 📋 |

---

## EPIC 15 — Nephos Watch (alerting métier)

Cf. annexe A du document technique. Alert contracts versionnés + state machine + notifier découplé.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E15-01 | ADR 0012 — Modèle alert contract YAML, state machine open/acknowledged/resolved/silenced | P1 | S | E14-01 | 📋 |
| E15-02 | Premier alert contract pilote (par exemple vent fort) avec évaluation Dagster sensor | P1 | M | E15-01, E13-04 | 📋 |
| E15-03 | Service notifier (FastAPI) avec canaux email / webhook | P1 | M | E15-02 | 📋 |
| E15-04 | UI consultation alertes ouvertes + historique (Streamlit) | P1 | S | E15-03 | 📋 |
| E15-05 | Workflow d'acquittement (validation 2-yeux pour alertes critiques) | P1 | M | E15-03 | 📋 |
| E15-06 | Distinction alerting plateforme (Grafana) vs alerting métier (plateforme) | P0 | XS | E15-01 | 📋 |

---

## EPIC 16 — Nephos Watch (fraîcheur SLA + complétude)

Cf. annexes B et C du document technique.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E16-01 | ADR 0013 — Modèle freshness policy : expected_publication, freshness_sla, on_late_data | P1 | S | E14-01 | 📋 |
| E16-02 | État de fraîcheur gouverné en Iceberg `platform.dataset_freshness_state` | P1 | M | E16-01 | 📋 |
| E16-03 | Cascade SLA : retard primaire propagé aux secondaires/produits | P1 | M | E16-02 | 📋 |
| E16-04 | ADR 0014 — Manifeste de complétude : mandatory vs optional, on_partial | P1 | S | E14-01 | 📋 |
| E16-05 | Détection complétude à l'arrivée du dataset (pygrib / Zarr metadata) | P1 | M | E16-04 | 📋 |
| E16-06 | Lineage column-level pour cascade fine sur dataset partial | P2 | L | E16-05 | 📋 |
| E16-07 | Reporting de ponctualité et complétude par dataset | P1 | M | E16-02, E16-05 | 📋 |

---

## EPIC 17 — Nephos Vault (habilitations L0-L3)

Cf. annexe H du document technique. Aviation, marine, défense, RGPD, embargos.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E17-01 | ADR 0015 — Classifications L0/L1/L2/L3, ABAC OPA, isolation physique L3 | **P0** | M | Cadrage juridique | 📋 |
| E17-02 | Déploiement Keycloak (IDP fédéré) | P1 | M | E17-01 | 📋 |
| E17-03 | Déploiement OPA + intégration Lakekeeper policies | P1 | M | E17-02 | 📋 |
| E17-04 | Premier access contract pilote sur dataset L1 (aviation par exemple) | P1 | M | E17-03 | 📋 |
| E17-05 | Audit d'accès gouverné en Iceberg `platform.access_log` | P1 | M | E17-03 | 📋 |
| E17-06 | Tests de fuite par recoupement (red team interne) | P1 | S | E17-04 | 📋 |
| E17-07 | Plateforme jumelle L3 défense (architecture isolée) | P2 | XL | E17-01 | 📋 |

---

## EPIC 18 — Nephos Capture (saisie opérateur DataWindow)

Cf. annexe F du document technique. Observations terrain (feux, dégâts, niveau d'eau) saisies dans la plateforme.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E18-01 | ADR 0016 — DataWindow générée depuis data contract + JSON Schema | P1 | M | E14-01 | 📋 |
| E18-02 | Génération automatique du formulaire React JSON Schema Form depuis le contract | P1 | M | E18-01 | 📋 |
| E18-03 | Backend API saisie (FastAPI + Pydantic dérivé) | P1 | M | E18-01 | 📋 |
| E18-04 | Premier workflow pilote : saisie feux de forêt | P1 | M | E18-02, E18-03 | 📋 |
| E18-05 | Mode offline + sync (app mobile) | P2 | L | E18-04 | 📋 |
| E18-06 | Pièces jointes (photos) avec URN S3 + lifecycle distinct | P2 | M | E18-04 | 📋 |
| E18-07 | Anonymisation RGPD à la lecture (visages, plaques, géoloc) | P1 | M | E17-04 | 📋 |

---

## EPIC 19 — Nephos Trace (modifications append-only event sourcing)

Cf. annexe G du document technique. Aucune modification par UPDATE direct, append-only avec lineage et cascade.

| ID | Titre | P | Taille | Dépend | État |
|----|-------|---|--------|--------|------|
| E19-01 | ADR 0017 — Event sourcing append-only : 5 types (correction, validation, override, retract, flag) | **P0** | M | E14-01 | 📋 |
| E19-02 | Schéma Iceberg `obs.*.events` append-only + vue `current` matérialisée | P1 | M | E19-01 | 📋 |
| E19-03 | Workflow validation 2-yeux pour modifications critiques | P1 | M | E19-02 | 📋 |
| E19-04 | Cascade downstream automatique sur correction (auto-materialize) | P1 | M | E19-02, E13-05 | 📋 |
| E19-05 | Diffusion event de correction publique (METAR COR, webhook) | P1 | M | E19-02 | 📋 |
| E19-06 | Audit UI consultation chaîne de versions | P2 | M | E19-02 | 📋 |
| E19-07 | Bloquer accès SQL direct (lecture seule humains, IDE révoqué) | P1 | S | E19-01 | 📋 |

---

## Sprint candidat 2 — « Premier import » (≈ 2 semaines)

Objectif : livrer l'import CF Standard Names en bout-en-bout.

| Item | Pourquoi |
|------|----------|
| E4-01 Framework ETL | Pré-requis à tout import. |
| E4-02 Import CF Standard Names | Premier livrable de valeur visible. |
| E5-01, E5-03 SHACL de base + validation post-import | Garde-fous sur le premier import. |
| E6-01 Export Turtle d'un scheme | Boucle de feedback : ce qu'on importe est ré-exportable. |
| E6-03 Validation export par outil tiers | Critère de validation ADR 0001. |
| E2-08 Migration alembic v4 | Gel de la version SKOS Core. |

Indicateurs de fin de sprint :

- ≥ 5000 concepts CF importés en moins de 5 min, validation SHACL passée.
- Export Turtle d'un scheme accepté par Skosmos ou SKOS-Play.

---

## Idées et notes (pour plus tard)

- Évaluer **`pg_jsonschema`** ou **`pgshacl`** pour répliquer une partie de la validation SHACL au plus près de la BD.
- Étudier l'**alignement avec SOSA/SSN** si le périmètre s'étend un jour aux observations (option B abandonnée pour l'instant).
- **Exploration de versionnement temporel SCD2** si le besoin de relire le référentiel à une date passée se précise.
- **Linting de cohérence linguistique** sur les `prefLabel` et `definition` (orthographe, longueur, marqueurs de qualité).
