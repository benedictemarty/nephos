# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog 1.1.0](https://keepachangelog.com/fr/1.1.0/)
et ce projet adhère au [versionnement sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Réorganisé

- **Réalignement stratégique du projet** : Nephos est désormais positionné comme **couche sémantique** d'une **plateforme SI météo gouvernée Po-scale** dont la vision est formalisée dans `docs/architecture/`.
  - Nouveau dossier `docs/architecture/` regroupant 4 documents de cadrage stratégique : architecture technique (`architecture_si_meteo.md`, ~35 pages, 8 annexes opérationnelles), architecture fonctionnelle v2 avec auto-critique intégrée (`architecture_fonctionnelle_si_meteo.md`, ~22 pages : capacités DAMA-aligned, business case avec ordres de grandeur conservateurs, scénarios métier concrets, stratégie de transition strangler pattern, dialogue avec contre-arguments), benchmark de 8 plateformes existantes (`benchmark_plateformes_meteo.md`, ~16 pages : MARS, NOAA BDP, EUMETSAT Data Store, Copernicus CDS/ADS, Pangeo, Microsoft Planetary Computer, Google Earth Engine, AWS Open Data Program), cartographie des SI internes des services météo nationaux (`sin_internes_smn.md`, ~14 pages : l'opérateur national, ECMWF, DWD, MetOffice, NOAA, JMA, BOM, KNMI, MeteoSwiss, KMA, plus composants partagés NinJo, ALADIN/ACCORD, Unified Model, ecCodes, OpenIFS).
  - Versions `.docx` générées dans `docs/architecture/docx/` via pandoc.
  - `docs/architecture/README.md` guide de lecture des 4 documents.
- **README.md** racine : encart d'évolution stratégique pointant vers `docs/architecture/`. Documentation existante (ADR, BACKLOG, CHANGELOG) préservée.
- **CLAUDE.md** : réécriture pour refléter la position de Nephos comme couche sémantique de la cible plateforme. Distinction claire entre code merged (couche sémantique) et couches à construire (catalogue Iceberg, stockage Zarr, orchestration Dagster/Kestra, gouvernance contracts, alerting, fraîcheur, complétude, accès classifiés). Conventions à respecter quand on étend vers la cible.
- **BACKLOG.md** : ajout d'un encart de réalignement (10 EPICs existants conservés, position dans la cible explicitée) et de **9 nouveaux EPICs** (E11-E19) couvrant les couches manquantes pour la cible : catalogue technique Iceberg + Lakekeeper (E11), stockage objet + Zarr (E12), orchestration Dagster ou Kestra (E13), data contracts gouvernance (E14), alerting métier (E15), fraîcheur SLA + complétude (E16), habilitations classifiées L0-L3 (E17), saisie opérateur DataWindow (E18), modifications append-only event sourcing (E19). Démarrage des EPICs E11-E19 conditionné aux décisions de cadrage (sponsor, scope, budget, équipe).
- **ADRs futurs identifiés** : 12 nouveaux ADRs (0006 à 0019, listés en section 9 du document technique) à rédiger après confirmation cadrage. Noms et numéros stabilisés.

### Limites assumées

- Les documents d'architecture sont des **drafts** soumis à critique structurante. Limites explicites signalées : hypothèses sur l'existant à valider en audit, chiffres en ordres de grandeur, pas de relecture juridique.
- Les EPICs E11-E19 ne démarrent **pas immédiatement** : ils attendent décisions de cadrage.
- **Aucun changement de code applicatif** dans cette PR : c'est un réalignement de documentation et de backlog. Le code existant (152 tests verts) reste fonctionnel et continue de couvrir la couche sémantique.

### Ajouté

- **Trigger d'audit étendu** (E2-04) — `gov.audit_trigger_func` est désormais attaché à 10 tables au total (3 préexistantes : `scheme`, `concept`, `unite` ; 7 nouvelles : `concept_label`, `concept_note`, `concept_in_scheme`, `concept_semantic_relation`, `concept_mapping`, `concept_physical`, `gov.proposals`).
  - Modifications dans `schema_v4_skos.sql` section 5 : 7 nouveaux `CREATE TRIGGER` avec PK explicite passée en `TG_ARGV[0]` (puisque les conventions de nommage ne suivent pas toujours `<table>_id` — ex. `concept_semantic_relation` a `relation_id`).
  - `gov.proposals` : son champ `status` étant éligible à la distinction `STATUS_CHANGE` de la fonction d'audit, le passage `submitted → under_review/approved/rejected/applied` est tracé spécifiquement, ce qui rend `gov.v_audit_recent` utilisable comme journal des décisions de curation.
  - 7 tests d'intégration (`tests/integration/test_schema_audit_extended.py`) couvrent INSERT, UPDATE avec `changed_columns`, DELETE et STATUS_CHANGE.
- **Validation des exports par un outil tiers** (E6-03) — `nephos.validators.skos_external.SkosExternalValidator` réutilise `SKOSExporter` (E6-01) pour produire le graphe Turtle exact qui serait publié, puis exécute les checks SKOS standards via la bibliothèque **`skosify`** (NatLibFi, MIT).
  - Checks : `hierarchy_cycles` (cycles broader, SKOS S22/S27), `disjoint_relations` (broader/related disjoints, S27), `preflabel_uniqueness` (un prefLabel par lang, S14), `hierarchical_redundancy` (broader transitivement redondant), `label_overlap` (libellé partagé entre concepts distincts).
  - Capture programmatique des warnings skosify via un handler logging dédié (skosify logue sur le root logger). Classification par regex sur le message vers un code stable.
  - Sortie structurée : `SkosExternalReport` (`nb_concepts`, `issues`, propriété `conforms`, méthode `by_check()`) et `SkosExternalIssue` (`check`, `severity`, `message`).
  - CLI : `nephos validate skos-external [--scheme CODE] [--issues/--no-issues] [--fail-on-issue]`. Le mode `--fail-on-issue` retourne exit 2 si au moins une anomalie est détectée — exploitable en pipeline CI.
  - 6 tests d'intégration : graphe propre conforme, cycle broader détecté, disjonction broader/related détectée, classification de messages connus + fallback `unknown`, agrégation `by_check()`.
  - Choix `skosify` plutôt que Skosmos (JVM lourd, déploiement séparé) ou SKOS-Play (validateur en ligne hors CI) : pure Python, exécutable dans le même process, validation SKOS conforme à l'esprit de l'ADR 0001 (export validé par outil tiers).
- **Commande `nephos validate all`** (E5-05) — point d'entrée unique combinant SHACL Core (E5-01) et rapport qualité (E5-04) sur un sous-ensemble du référentiel.
  - Filtre commun `--scheme CODE` propagé aux deux validateurs. Option `--strict` héritée du SHACL pour imposer FR+EN sur les concepts validés (ADR 0004).
  - `--fail-on-error` retourne exit 2 si SHACL non conforme OU si la qualité signale au moins une anomalie de sévérité `error` — exploitable directement en pipeline CI / post-import.
  - Sortie Rich unifiée : table à deux phases (SHACL + Qualité) avec compteurs ; les commandes `validate shacl` et `validate quality` restent disponibles pour les rapports détaillés.
  - 3 tests d'intégration via `typer.testing.CliRunner` : base saine → exit 0, concept orphelin + `--fail-on-error` → exit 2, concept orphelin sans flag → exit 0.
- **Rapport qualité automatisé** (E5-04) — `nephos.validators.quality_report.QualityReporter` scanne la base à la recherche d'anomalies structurelles complémentaires au validateur SHACL Core.
  - 8 détecteurs : `concepts_without_pref_label` (error), `concepts_without_scheme` (warning), `concepts_self_broader` (error), `duplicate_pref_label_lang` (error), `duplicate_notation_in_scheme` (error), `duplicate_mappings` (error, mêmes `(concept, target_uri)` avec relations divergentes), `missing_pref_label_fr` et `missing_pref_label_en` (warning sur concepts publiés, ADR 0004).
  - Sortie structurée : `QualityReport` agrège une liste de `QualityFinding` (code stable, label humain, severity ∈ error/warning/info, count, samples ≤ 5 URIs). Propriétés `has_errors` et `total_anomalies`.
  - Filtrage par scheme (`scheme_code`) sur les détecteurs applicables ; `concepts_without_scheme` ignore le filtre par construction (un concept orphelin n'a aucun scheme à filtrer).
  - CLI : `nephos validate quality [--scheme CODE] [--samples/--no-samples] [--fail-on-error]`. Sortie Rich avec sévérités colorées et exemples par catégorie. Code de sortie 2 si `--fail-on-error` et au moins une anomalie de sévérité `error` est détectée — exploitable en CI.
  - 11 tests d'intégration : 1 par détecteur (incluant les cas où la DB bloque déjà l'anomalie en défense en profondeur), 1 sur le filtrage par scheme, 2 sur la structure du rapport.
- **Mappings ECMWF Parameter Database** (E4-06) — alignement par mapping seul, pas de clone des paramètres ECMWF.
  - Source : `cfName.def` du dépôt `ecmwf/eccodes` (Apache 2.0), qui expose un mapping CF Standard Name → triplet GRIB2 (`discipline`, `parameterCategory`, `parameterNumber`).
  - `nephos.importers.ecmwf_mappings.ECMWFMappingsImporter` parse le fichier (regex sur les blocs `'name' = { … }`), pour chaque CF name présent en base sous `grandeurs-cf` pose un `concept_mapping mapping_relation='closeMatch'` vers `https://codes.ecmwf.int/grib/param-db/?discipline=D&parameterCategory=C&parameterNumber=N`. `discover_version` = MD5 court du fichier. Idempotent grâce à la contrainte unique `(concept_id, target_uri, mapping_relation)`.
  - CLI : `nephos import ecmwf-mappings [--source URL|FILE] [--dry-run]`.
  - 7 tests : 3 intégration (création + idempotence + base sans CF) et 4 unitaires de parsing (entry simple, qualifiers extra, entry incomplète skipée, format URL).
  - Validation live : 47 entrées parsées depuis ecCodes develop. Sur une base sans CF importé : `0 créations, 47 unmatched` (comportement attendu). Sur base CF complète, le mapping s'établit pour les CF couverts par `cfName.def`.
  - `closeMatch` (et non `exactMatch`) : un même triplet GRIB2 peut désigner plusieurs paramètres ECMWF distincts en présence de qualificatifs additionnels (`typeOfStatisticalProcessing`, `typeOfFirstFixedSurface`) ; la V2 affinera vers un `id` ECMWF unique.
- **Détection des concepts disparus côté source** (E4-08) — règle « jamais de DELETE, toujours `status='deprecated'` ».
  - Nouveau module `nephos.etl.deprecation` avec `mark_disappeared_concepts(conn, source_id, current_version, scheme_codes)` qui passe en `deprecated` les concepts dont `import_version` ne correspond plus à la version courante, restreints à `scheme_codes`. Sécurité : `scheme_codes` vide ⇒ no-op (refus de marquer toute la base).
  - Nouvel hook `Importer.target_scheme_codes() -> tuple[str, ...] | None` (default `None` = désactivé). Déclaré par `CFStandardNamesImporter` (`grandeurs-cf`), `CFAreaTypeImporter` (`area-types-cf`), `WMOCodesImporter` (scheme courant). `QUDTUnitsImporter` reste opt-out (touche `vocab.unite`).
  - Intégration `ImportRunner` automatique entre `load` et validation SHACL ; option `RunOptions.detect_disappeared=True` par défaut. Préservation explicite des concepts `has_local_override = TRUE`.
  - Nouveau champ `ImportResult.nb_deprecated_disappeared` ; ligne « Deprecated (disparus) » dans la sortie Rich CLI.
  - 6 tests d'intégration (`tests/integration/test_etl_deprecation.py`) avec fixture amputée `wmo_bufr_0_02_001_partial.ttl` : nominal sans disparus, 2 disparus marqués, override protégé, désactivation via `RunOptions`, scheme isolation cross-source (autre scheme WMO préservé), `scheme_codes=()` no-op.
- **Import WMO Codes Registry** (E4-05) — `nephos.importers.wmo_codes.WMOCodesImporter`, importer paramétrable pour les code lists publiées en SKOS/Turtle par https://codes.wmo.int.
  - Constructeur : `WMOCodesImporter(register_url=..., scheme_code=..., scheme_title=...)`. Helper `from_preset(key)` pour les presets fournis.
  - 4 presets initiaux (BUFR section commune) : `bufr-0-02-001` (Type of station), `bufr-0-02-002` (Type of instrumentation for wind measurement), `bufr-0-02-003` (Type of measuring equipment used), `bufr-0-08-021` (Time significance).
  - Parsing : `rdflib` Turtle, identification du `reg:Register` racine, extraction des `skos:Concept` membres directs (filtre par préfixe d'URI). `discover_version` = `dct:modified` du register.
  - Side effects en base : création locale du scheme cible (`status='approved'`), upsert des concepts par URI Nephos `{uri_base}/{scheme_code}/{notation}` (idempotent), `concept_label@en` (kind=pref) depuis `rdfs:label@en`, `concept_in_scheme`, `concept_mapping exactMatch` vers l'URI WMO d'origine, `import_source_id = WMO_CODES`.
  - CLI : `nephos import wmo-codes --code-list <preset>` (presets) ou `--register-url <URL> --scheme-code <code> --scheme-title <titre>` (mode custom). `--list-presets` affiche le tableau Rich des presets disponibles.
  - 5 tests d'intégration (`tests/integration/test_importer_wmo_codes.py`) avec fixture mini Turtle (`tests/integration/fixtures/wmo_bufr_0_02_001_mini.ttl`).
  - **Validation live** sur BUFR 0-08-021 (Time significance) : 31 concepts importés, idempotence ✅ (rerun = 31 inchangées), 0 violation et 0 warning SHACL post-import (`v_imports_status` montre WMO_CODES = 1 version, 31 concepts).
  - Limitation actuelle : `dcterms:source` au niveau scheme/concept reste à enrichir (n'altère pas les triplets `exactMatch` vers les URIs WMO d'origine, qui constituent déjà la traçabilité sémantique).
- **Validation SHACL post-import** (E5-03) — `RunOptions.validate_after` (défaut `True`) chaîne `SHACLValidator.validate` après le `load`. Compteurs ajoutés en `notes` du `ImportResult`. Mode `strict_validation=True` lève `ImportValidationError` et déclenche le rollback de la transaction de chargement en cas de violation. 4 tests d'intégration : conforme + notes informatives, désactivation lax, violation en lax (consigne), violation en strict (rollback + journal failed).
- **Export RDF/SKOS** (E6-01) — module `nephos.exporters.SKOSExporter` qui charge depuis Postgres et sérialise un sous-ensemble du référentiel.
  - Formats supportés : Turtle (défaut), RDF/XML, JSON-LD, N3 (via `rdflib.Graph.serialize`).
  - Triplets émis : `skos:Concept` + `skos:notation` + `skos:prefLabel`/`altLabel`/`hiddenLabel` multilingues + `skos:definition`/`scopeNote`/`example`/`historyNote`/`editorialNote`/`changeNote`. Schemes via `skos:ConceptScheme` + `skos:inScheme` + `skos:topConceptOf` + `skos:hasTopConcept`. Relations internes (`skos:broader`/`narrower`/`related`) entre concepts du sous-ensemble. Mappings externes (`*Match` vers ressources amont) toujours inclus. `dcterms:license <https://creativecommons.org/licenses/by/4.0/>` au niveau du scheme (ADR 0005). `dcterms:source <URL>` au niveau de chaque concept ayant un `import_source_id`.
  - Filtrage par scheme via `scheme_code`. `statuses` configurable (`approved` + `published` par défaut).
  - CLI : `nephos export turtle [SCHEME] [--output/-o FILE] [--format/-f turtle|xml|json-ld|n3]`. Sans `-o` : sortie sur stdout. Avec `-o` : table Rich récapitulative.
  - 6 tests d'intégration (`tests/integration/test_exporter_skos.py`).
  - **Validation live** : export du scheme `grandeurs-cf` complet (5023 concepts) en 2 secondes, 35154 lignes Turtle valide ; le payload est re-parsable par rdflib (round-trip OK). Critère ADR 0001 atteint (export validable par outil tiers — Skosmos / SKOS-Play à brancher en aval).
- **Validation SHACL des concepts** (E5-01) — premier validateur sémantique Nephos.
  - `shapes/nephos_skos_core.ttl` — 5 shapes SHACL : URI Nephos (ADR 0003), notation regex (ADR 0003), prefLabel ≥ 1 + `uniqueLang` (SKOS S14), `PublishedConcept` virtuel imposant FR+EN (ADR 0004), pas de self-broader (SKOS S27).
  - `nephos.validators.shacl_runner.SHACLValidator` — charge les concepts publiés/approuvés depuis Postgres comme graphe RDF (concept, notation, prefLabel multilingue, broader internes), applique pyshacl avec les shapes Core et retourne un `SHACLValidationReport` structuré (conforms, concepts validés, violations/warnings/infos, rapport texte complet).
  - Mode `treat_as_published=True` (option CLI `--strict`) : force tous les concepts à être validés contre la shape `PublishedConcept`. Sert à identifier la **file d'attente de traduction FR** sur les imports automatiques.
  - Filtrage par scheme (`--scheme CODE`) pour cibler une partie du référentiel.
  - CLI : `nephos validate shacl [--scheme CODE] [--strict] [--report]`. Sortie Rich avec compteurs ; option `--report` affiche le rapport pyshacl complet en cas de non-conformité.
  - 5 tests d'intégration : concept conforme, concept sans prefLabel viole, mode strict impose FR+EN, filtre scheme isole le sous-graphe, base vide reste conforme.
  - **Validation live** sur le pipeline complet (QUDT puis CF) : 5023 concepts CF conformes en mode normal (URI valides, notations conformes, prefLabel@en présents, pas de self-broader). En mode `--strict`, 5023 violations attendues — la file de traduction FR est identifiée par construction.

- **Mapping symboles CF↔QUDT** (E4-04b) — `nephos.importers._unit_symbols.normalize_cf_to_qudt(s)` :
  - Convertit la notation CF (tokens séparés par espaces, exposants signés sans `^`) vers la notation QUDT (numérateur·...· / dénominateur, exposants Unicode).
  - Cas couverts : ``"m s-1"`` → ``"m/s"``, ``"kg m-2 s-1"`` → ``"kg/(m²·s)"``, ``"W m-2 K-1"`` → ``"W/(m²·K)"``, ``"m2 s-2"`` → ``"m²/s²"``, conservation des cas triviaux (``K``, ``Pa``, ``1``, ``%``, ``°C``).
  - Tokens non-parsables : la chaîne d'entrée est rendue inchangée (`_resolve_unit` la traite comme une non-correspondance).
  - Intégré dans `_resolve_unit` du CF importer comme deuxième candidat de match (entre le brut et les variantes texte simples).
  - **Gain mesuré en live** sur l'import complet QUDT puis CF :
    - Avant E4-04b : 560 / 5023 unités résolues (**11,2 %**).
    - Après E4-04b : 4022 / 5023 unités résolues (**80,1 %**).
    - +3462 résolutions, facteur ×7. Le millier restant correspond aux unités CF rares ou exotiques que QUDT ne couvre pas par symbole strict.
  - 18 tests unitaires hors Postgres (`tests/test_unit_symbols.py`).

- **`QUDTUnitsImporter`** (E4-04) — second import concret, alimente `vocab.unite` à grande échelle.
  - Parse le Turtle QUDT 2.1 via `rdflib` (URL officielle ou fichier local pour tests/dev).
  - Pour chaque ressource `?u a qudt:Unit` extrait : URI QUDT, `qudt:symbol`, `rdfs:label@en`, `dcterms:description`, `qudt:conversionMultiplier`, `qudt:conversionOffset`, `qudt:applicableSystem`, `qudt:hasQuantityKind` (multiples).
  - Détection SI canonique : `applicableSystem sou:SI` + `multiplier ∈ {1, NULL}` + `offset ∈ {0, NULL}`. Le degré Celsius (offset 273.15) reste donc non-canonique malgré son appartenance à SI.
  - Idempotence par `qudt_uri` (UPDATE en place) ; rapprochement par `symbole` pour enrichir une unité préexistante (cas seed). Collisions de symbole skip + warning.
  - Respect de `has_local_override` (compte en `nb_overrides_protected`).
  - **Validation live** : 2490 unités QUDT importées en 11s. Après QUDT, le re-import CF résout 560 unités (vs 17 avant) — gain de 543 résolutions par symbole strict. Le reste relève du mapping symboles CF↔QUDT (item E4-04b à venir : CF écrit `m s-1`, QUDT écrit `m/s`).
  - 7 tests d'intégration sur fixture Turtle mini (`qudt_units_mini.ttl`, 4 unités) : création + champs renseignés, idempotence avec UPDATE en place, dry-run, rapprochement par symbole sur unité existante, override local protégé, transform pur (extract + parsing).
  - CLI : `nephos import qudt-units [--dry-run] [--source PATH_OR_URL]`.

- **`CFStandardNamesImporter`** (E4-02) — premier import concret consommant le framework E4-01.
  - Parse l'XML CF Standard Names (URL officielle par défaut, fichier local en fallback pour tests/dev).
  - Normalise les notations CF en minuscules pour respecter ADR 0003 (URI Nephos `^[a-z0-9][a-z0-9_-]*$`). L'identifiant CF original (qui peut contenir des majuscules pour les isotopes : `13C`, `18O`) est conservé dans `concept_physical.cf_standard_name`. Les `prefLabel@en` humanisés (underscores → espaces) gardent la casse originale pour préserver la sémantique scientifique.
  - Crée le scheme `grandeurs-cf` à la première importation.
  - Pour chaque entrée : `vocab.concept` (status `approved` — ADR 0004 : `published` requiert FR), `concept_label@en` (pref), `concept_note@en` (definition depuis `<description>`), `concept_in_scheme`, `concept_mapping` (`exactMatch` vers la fiche CF officielle), `concept_physical` (`value_type='scalar'`, `cf_standard_name`, `unit_canonical_id` résolu best-effort via `vocab.unite.symbole`).
  - Idempotent par URI : re-run même version → 0 création / N skipped. Re-run nouvelle version → mise à jour de `import_version` et `last_synced_at`. `has_local_override = TRUE` est respecté (override préservé, comptabilisé en `nb_overrides_protected`).
  - **Validation live** : import du fichier officiel CF v93 (~5023 concepts) en **16 secondes** end-to-end. Le critère ADR 0001 (≥ 5000 concepts en < 5 minutes) est largement atteint.
  - 8 tests d'intégration sur fixture XML mini (4 entrées) : création complète, idempotence, dry-run, résolution d'unité, override local protégé, note de warning sur unités non résolues, parsing transform pur.
  - CLI : `nephos import cf [--dry-run] [--source PATH_OR_URL]` invoque le pipeline complet et affiche le rapport en table Rich.

- **ADR 0013 — Adopter Claude Code GitHub Action comme agent reviewer** (`docs/adr/0013-agent-reviewer-claude-code-action.md`). Acte le choix de `anthropics/claude-code-action@v1` authentifié via OAuth Max (sans coût marginal au token), pour produire à chaque ouverture/synchronisation de PR un rapport structuré en 6 sections + verdict explicite. Le rapport est un **éclairage** pour le reviewer humain — pas un statut bloquant ni un droit de merge. Hors-périmètre : auto-approval, persistance des rapports, PRs depuis forks externes (à traiter ultérieurement avec un workflow `pull_request_target` sécurisé séparé).
- **`.github/workflows/agent-review.yml`** — workflow d'exécution de l'agent reviewer. Triggers : `pull_request: [opened, synchronize, reopened]` (volontairement pas `pull_request_target` pour ne pas exposer le secret OAuth aux PR depuis forks) + `workflow_dispatch` pour relance manuelle. Concurrence par branche avec `cancel-in-progress`. Permissions minimales : `contents: read`, `pull-requests: write`, `issues: write`. Pas de droit de merge ni d'écriture sur le code. Skip des PRs en draft pour économiser le quota Max. Prompt versionné qui charge le contexte ADR pertinent et impose le format de rapport (6 sections + verdict).
- Item `E1-12` du backlog marqué ✅ (l'activation effective dépend de l'ajout du secret `CLAUDE_CODE_OAUTH_TOKEN` côté GitHub par le mainteneur — étape manuelle, validée dans la procédure de l'ADR 0013).

### Ajouté (suite)

- **Framework ETL `nephos.etl`** (E4-01) — orchestration générique des imports depuis les sources standards.
  - `nephos.etl.base` : `Importer` (ABC avec `discover_version`, `extract`, `transform`, `load`), `ImportResult` (dataclass slots avec compteurs), `SourceCode` (NewType pour traçabilité du code amont).
  - `nephos.etl.runner` : `ImportRunner` orchestrateur transactionnel (extract → transform → load dans une même transaction ; rollback complet en cas d'exception ; trace `failed` dans `gov.imports` persistée hors-transaction). Mode `dry_run` (extract+transform sans écrire).
  - `nephos.etl.journal` : `open_run`, `close_run`, `mark_failed`, `resolve_source`. Gère les trois statuts (`success`/`partial`/`failed`/`aborted`) prévus par le schéma v4.
  - `nephos.etl.exceptions` : `ImportError`, `ImportSourceError`, `ImportValidationError`.
  - `nephos.db` : helper `connect(autocommit=False)` centralisé pour psycopg.
  - 5 tests d'intégration : création de concepts + journal `success`, idempotence (re-run skip), échec → rollback complet + journal `failed`, dry-run sans écriture, source non déclarée → `ImportError`.
  - CLI `nephos import cf` accepte désormais `--dry-run` (squelette en attente de l'`Importer` concret CF, item E4-02).
- **ADR 0011 — Protection technique de la branche `main`** (`docs/adr/0011-protection-technique-branche-main.md`). Acte le passage de la chaîne de revue de CONTRIBUTING.md d'une politique contractuelle à un **enforcement technique** via les Branch Protection Rules GitHub (PR obligatoire, ≥1 review humaine, status checks verts, linear history, no admin bypass, no force push, no deletion). Commande `gh api` complète versionnée dans l'ADR. Procédure de rollback documentée. Couvre l'item `E1-11` (passe à ✅ une fois la commande exécutée).
- **ADR 0012 — Gestion de la vulnérabilité PYSEC-2022-42969** (`docs/adr/0012-gestion-vulnerabilite-py-pysec-2022-42969.md`). Acte l'ignore explicite et exclusif de cette CVE (paquet `py` 1.11.0 EOL, sans fix publié, transitive sans impact réel sur la pile). Justification, conditions de sortie (`CS1` fix amont, `CS2` retrait de l'arbre, `CS3` chemin d'exécution réel découvert), procédure de réévaluation annuelle. Item `E9-05` créé dans le backlog pour la remédiation à long terme.

### Corrigé

- **CI `Security` job** — `pip-audit` échouait sur `PYSEC-2022-42969` (CVE sur `py` 1.11.0, paquet EOL sans fix publié, tiré comme transitive sans impact réel sur notre code). Ajout d'un `--ignore-vuln PYSEC-2022-42969` documenté dans le workflow. À retirer si une version corrigée de `py` apparaît ou si on parvient à le faire sortir de l'arbre.
- **`schema_v4_skos.sql`** — bug bloquant détecté lors de la première application réelle sur PostgreSQL 16. La contrainte `UNIQUE (source_concept_id, target_concept_id, relation, COALESCE(scheme_id, 0))` sur `vocab.concept_semantic_relation` est invalide en PostgreSQL (les expressions ne sont pas autorisées dans une contrainte UNIQUE inline). Remplacée par un `CREATE UNIQUE INDEX uq_csr_relation_scope` séparé, qui accepte les expressions. Bug attrapé par `docker compose up postgres` lors de l'installation des outils.
- **`src/nephos/cli.py`** — `nephos --version` renvoyait exit code 2 (Typer considérait la sous-commande manquante malgré la callback). Ajout de `invoke_without_command=True` à l'application racine. Test `test_version_flag_prints_version` désormais vert.

### Modifié

- **`pyproject.toml`** — migration de `[tool.uv].dev-dependencies` (déprécié) vers `[dependency-groups].dev` (PEP 735). Aucun changement fonctionnel.
- **Formatage Ruff** : 4 fichiers reformatés et 7 patterns `with` imbriqués combinés en `with A, B:` après `ruff check --fix && ruff format`. Tests, mypy strict et ruff désormais tous verts (46/46 tests passent localement contre PostgreSQL 16 dans docker-compose).

### Ajouté

- **`Dockerfile`** multi-stage (E3-08) :
  - Builder `python:3.12-slim-bookworm` avec `build-essential` + `uv` pinné en version, `uv sync --frozen --no-dev` pour la couche dépendances reproductible.
  - Runtime `python:3.12-slim-bookworm` minimal : `libpq5` (psycopg), `libxml2` + `libxslt1.1` (lxml pour CF), `ca-certificates` (HTTPS sources amont). Utilisateur non-root `nephos` créé avec `groupadd`/`useradd --system`. Le venv et le code source sont copiés depuis le builder. `ENTRYPOINT ["nephos"]`, `CMD ["--help"]`. `NEPHOS_LOG_FORMAT=json` par défaut en runtime conteneurisé.
  - `.dockerignore` complet (exclut `.git`, caches, `.venv`, `tests/`, `docs/`, `.env`, schéma v3 déprécié, etc.).
- **`docker-compose.yml`** (E3-10) :
  - Service `postgres` (image `postgres:16-alpine`) avec volume nommé `nephos-pg-data`, healthcheck `pg_isready`, schéma v4 monté en `docker-entrypoint-initdb.d` (appliqué automatiquement à la création du volume).
  - Service `nephos` (build du Dockerfile local) en profil `cli` — n'est pas lancé par `compose up` par défaut, mais via `compose run --rm nephos <commande>`.
- **Tests d'intégrité du schéma v4** :
  - `tests/conftest.py` — fixtures `db_conn` (recrée le schéma avant chaque test via le DROP/CREATE en tête de `schema_v4_skos.sql`, skip propre si `NEPHOS_DATABASE_URL` non défini) et `admin_user_id`. Connexion `psycopg` autocommit.
  - `tests/integration/test_schema_constraints.py` — 23 tests sur les contraintes : URI `^https?://`, `notation` `^[a-z0-9][a-z0-9_-]*$`, prefLabel unique par `(concept, lang)`, BCP 47 sur `lang`, `valid_to > valid_from`, `source_concept ≠ target_concept`, `range_min ≤ range_max`, FK obligatoire sur `concept_mapping.target_source_id`, `value_type` dans l'enum.
  - `tests/integration/test_schema_views.py` — 8 tests sur les vues : `v_concepts_actifs` (publié + FR + EN visible, draft invisible), `v_concepts_traduction_pending` (file d'attente FR+EN), `v_concept_descendants` / `v_concept_ancestors` (résolution récursive avec cas à profondeur 2 et **test de tolérance aux cycles** garantissant qu'une boucle accidentelle ne fait pas exploser la requête), `v_concepts_mesurables` (jointure typage physique).
  - `tests/integration/test_schema_audit.py` — 6 tests sur les triggers : INSERT loggé, UPDATE avec `changed_columns` filtré (sans `modified_at`/`modified_by`/`version`), STATUS_CHANGE distingué de UPDATE, DELETE loggé, triggers attachés à `scheme`, `concept`, `unite`.
  - Couvre `E2-07` du backlog.
- **Tests unitaires hors Postgres** :
  - `tests/test_cli.py` — 5 tests : `--help`, `--version`, et chaque sous-commande non implémentée renvoie un code 0 avec message clair (Typer `CliRunner`).
  - `tests/test_logging.py` — 5 tests : format `text` et `json`, propagation des `extra=`, idempotence de `configure_logging`, respect du niveau.
  - Couvre `E3-11` du backlog.
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
| [0011](docs/adr/0011-protection-technique-branche-main.md) | Protection technique de la branche `main` (Branch Protection Rules) | Accepté |
| [0012](docs/adr/0012-gestion-vulnerabilite-py-pysec-2022-42969.md) | Gestion de la vulnérabilité PYSEC-2022-42969 (paquet `py` EOL) | Accepté |
| [0013](docs/adr/0013-agent-reviewer-claude-code-action.md) | Adopter Claude Code GitHub Action comme agent reviewer | Accepté |
| [0014](docs/adr/0014-adapter-protection-pour-mainteneur-unique.md) | Adapter la chaîne de revue au cas du mainteneur unique (supersède partiellement 0011) | Accepté |
