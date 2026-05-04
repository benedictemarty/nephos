# ADR 0002 — Python comme stack d'implémentation du pipeline sémantique

- **Statut** : Accepté
- **Date** : 2026-05-05
- **Décideurs** : à compléter (sponsor métier, lead dev)
- **Étiquettes** : architecture, stack, ETL, sémantique
- **Lié à** : [ADR 0001 — Adopter SKOS comme socle du référentiel](0001-adopter-skos-comme-socle-du-referentiel.md)
- **Différé** : choix de la façade API (REST custom, GraphQL, auto-génération sur Postgres) — voir ADR 0003 à venir.

---

## 1. Contexte et énoncé du problème

L'ADR 0001 fixe SKOS comme modèle conceptuel et PostgreSQL comme moteur de stockage. Il reste à choisir le langage d'implémentation pour les briques applicatives qui *manipulent du sémantique* :

1. **Pipeline d'import** depuis les sources standards (CF Standard Names en XML, QUDT en OWL/RDF, WMO Codes Registry en RDF/SKOS via Linked Data, ECMWF en JSON, NERC BODC en SPARQL).
2. **Validation des concepts importés** contre des contraintes structurelles (un seul `prefLabel` par langue, broader cohérent, intégrité des mappings…).
3. **Export RDF/SKOS** à la demande pour interopérabilité (Skosmos, VocBench, catalogues INSPIRE).
4. **Outillage CLI** pour les opérateurs (lancer un import, vérifier l'état d'une source, rejouer un re-sync, exporter un sous-ensemble).

La préférence initiale exprimée était Go. La revue d'architecture a évalué cette préférence au regard de la nature du projet (référentiel sémantique avec lourde manipulation RDF/SKOS) et de l'écosystème disponible.

**Hors périmètre de cette ADR** : le choix de la façade API (PostgREST, FastAPI, Hasura, pg_graphql…) est différé à l'ADR 0003. Cette décision n'est pas urgente tant que le pipeline d'import et la modélisation SKOS ne sont pas en place, et elle dépend de critères qui ne sont pas encore stabilisés (besoins métiers d'endpoints non-CRUD, stratégie d'authentification, type d'API attendu par les consommateurs).

## 2. Drivers de décision

| # | Driver | Pourquoi c'est important |
|---|---|---|
| D1 | **Maturité de l'écosystème sémantique** | Le projet vit ou meurt par sa capacité à parser, manipuler et exporter du RDF/SKOS. C'est le bottleneck. |
| D2 | **Validation SHACL** | Référentiel normatif → contraintes structurelles à valider à chaque import. Implémentations rares. |
| D3 | **Coût et vélocité d'implémentation** | ETL pour 6 sources standards : à coder une fois pour toutes, avec un effort raisonnable. |
| D4 | **Performance et opérabilité** | Charge attendue : trafic faible (référentiel = peu de QPS), imports périodiques. La performance brute n'est pas un driver. |
| D5 | **Compétences équipe** | Préférence Go exprimée. Compétences Python existantes ou acquérables. |
| D6 | **Réversibilité du choix** | Possibilité d'ajouter ultérieurement un service Go ciblé sans refonte. |

## 3. Options considérées

### Option A — Tout-Go

ETL, validation et export en Go. Bibliothèques RDF Go (`knakk/rdf`, `piprate/json-gold`, `deiu/rdf2go`).

### Option B — Tout-Python (retenue)

ETL, validation et export en Python (`rdflib`, `pyshacl`, `lxml`, `SPARQLWrapper`).

### Option C — Tout-Java

ETL, validation et export sur Apache Jena ou RDF4J. C'est l'écosystème historiquement le plus complet pour le sémantique.

### Option D — Polyglotte Python + Go

ETL et validation en Python (où l'écosystème commande) ; éventuel service applicatif Go ultérieur sur des besoins spécifiques.

## 4. Décision

**Option B retenue** : Python comme stack d'implémentation pour tout ce qui touche au sémantique.

### Périmètre concret

| Brique | Choix | Bibliothèques / outils principaux |
|---|---|---|
| **Pipeline d'import** | Python 3.12+ | `rdflib`, `lxml`, `requests`, `SPARQLWrapper`, `pydantic` |
| **Validation des données importées** | Python | `pyshacl` (implémentation SHACL W3C), shapes SKOS maison |
| **Export RDF/SKOS** | Python | `rdflib` (sérialisation Turtle / RDF/XML / JSON-LD) |
| **CLI opérateurs** | Python | `click` ou `typer` |
| **Migrations de schéma** | Python | `alembic` (en mode raw SQL ou sur SQLAlchemy) |
| **Gestion des dépendances** | `uv` (recommandé) ou `poetry` | Lockfile reproductible |
| **Tests** | `pytest` + `pytest-postgresql` | Tests d'intégration sur Postgres réel |
| **Qualité de code** | `ruff` (lint + format), `mypy` (typage strict) | Pre-commit hooks |

### Versions cibles

- Python 3.12+ (annotations type modernes, `match`, perf).
- PostgreSQL 14+ (déjà fixé en ADR 0001).

### Pas dans le périmètre de cette ADR

- **Façade API** (REST, GraphQL, auto-généré ou custom) → **ADR 0003 à venir**.
- **Frontend de curation** (Directus, VocBench, app custom) → ADR ultérieur.
- **Visualisation et exploration** (Skosmos, etc.) → option ouverte.
- **Service Go éventuel** : non interdit. S'il émerge un besoin spécifique (service temps réel, streaming, intégration dans une chaîne Go existante), un service Go ciblé pourra être ajouté sans refonte. Voir conséquence C5 ci-dessous.

## 5. Conséquences

### Positives

- **(C1) Écosystème sémantique disponible immédiatement** : `rdflib` couvre le parsing/sérialisation des 8 formats RDF principaux, `pyshacl` est l'implémentation SHACL de référence en Python. Les imports CF/QUDT/WMO se réduisent à de l'orchestration ETL classique.
- **(C2) Coût de développement réduit** : ETL estimé à 200–400 lignes Python par source, vs plusieurs milliers de lignes en Go (parser RDF maison) ou Java (boilerplate Jena).
- **(C3) Skill diversifiable** : Python est un acquis utile au-delà du référentiel (data engineering, scripts ops, notebooks d'exploration des concepts).
- **(C4) Cohérence stack future** : le langage est posé pour toute l'évolution du backend ; la façade API choisie en ADR 0003 pourra réutiliser ce stack si elle est en Python (FastAPI), ou rester découplée.
- **(C5) Réversibilité partielle** : un service Go pourra être ajouté ultérieurement pour un besoin ciblé sans toucher au pipeline ETL.

### Négatives / coûts à accepter

- **(C6) Runtime Python à opérer** : interpréteur Python 3.12+ avec dépendances natives (`lxml`, `pyshacl`, `cryptography`). Mitigation : image Docker basée sur `python:3.12-slim`, lockfile figé.
- **(C7) Déploiement Python plus pesant que Go** : packaging avec `uv` ou `poetry`, image à construire, dépendances natives à compiler ou récupérer. Acceptable pour un projet à fréquence de déploiement modérée.
- **(C8) Renoncement Go au démarrage** : la préférence initiale n'est pas honorée. Le projet n'est pas la bonne fenêtre pour valoriser une compétence Go équipe ; cette compétence reste utile pour d'autres briques de la chaîne data.

### Conséquences sur les autres décisions

- **ADR 0003 à venir** : choix de la façade API. Le choix Python du pipeline n'impose pas FastAPI, mais le facilite si cohérence stack souhaitée.
- **ADR à venir** : choix de l'outil de curation (Directus / VocBench / app custom).
- **ADR à venir** : politique de gestion des secrets et auth.
- **ADR à venir** : containerisation et stratégie de déploiement.

## 6. Pros / cons des options non retenues

### Option A — Tout-Go

- **Pros** : binaire unique, ops simple, préférence équipe respectée, perf brute supérieure, concurrence native.
- **Cons** : (a) bibliothèques RDF Go marginales, peu maintenues, sans support SPARQL ni SHACL ; (b) nécessite soit d'écrire un parser SKOS spécifique par source, soit de déléguer la conversion RDF à des outils CLI externes (Apache Jena RIOT en JVM) — perdant alors l'avantage du binaire unique ; (c) pas de validation SHACL automatisable ; (d) la performance brute n'est pas un driver fort de ce projet. **Rejeté** : bloque sur D1, D2, D3.

### Option C — Tout-Java

- **Pros** : Apache Jena et RDF4J sont les implémentations RDF les plus complètes ; SHACL TopBraid mature ; écosystème industriel.
- **Cons** : (a) JVM lourde à opérer ; (b) verbosité de Java ; (c) cycle de développement plus long ; (d) montée en compétence ou recrutement plus coûteux ; (e) bénéfices marginaux sur Python pour ce périmètre. **Rejeté** : surinvestissement face à D3, D5, sans gain proportionné sur D1.

### Option D — Polyglotte Python + Go

- **Pros** : ETL en Python (où l'écosystème commande), Go pour services applicatifs spécifiques.
- **Cons** : au démarrage, aucun besoin Go n'est identifié — l'introduire dès maintenant ajoute du coût de gouvernance sans bénéfice concret. **Différé** : option ouverte plus tard si un besoin spécifique justifie un service Go ciblé (voir C5).

## 7. Validation

Cette décision est validée si :

- [ ] Un import CF Standard Names (~5500 concepts) s'exécute en moins de 5 minutes, avec validation SHACL post-import.
- [ ] Un export RDF/SKOS d'un sous-ensemble (test : un scheme complet) est validé par un outil tiers (Skosmos ou validateur SKOS-Play).
- [ ] Le lockfile de dépendances est versionné et l'environnement reproductible sur une machine vierge en moins de 5 minutes (`uv sync` ou `poetry install`).
- [ ] La couverture de tests sur le pipeline d'import dépasse 80 % et inclut au moins un test d'intégration par source amont.

## 8. Références

- W3C — *SHACL — Shapes Constraint Language* : https://www.w3.org/TR/shacl/
- `rdflib` — bibliothèque Python RDF/SKOS : https://rdflib.readthedocs.io
- `pyshacl` — implémentation SHACL en Python : https://github.com/RDFLib/pySHACL
- `uv` — gestionnaire de dépendances Python rapide : https://github.com/astral-sh/uv
- ADR 0001 — Adopter SKOS comme socle du référentiel
