# Nephos

> Référentiel SKOS de métadonnées météorologiques. Vocabulaires alignés sur CF Conventions, WMO Codes Registry et QUDT.

---

## Qu'est-ce que c'est ?

**Nephos** est un référentiel de **métadonnées descriptives** pour les données météorologiques. Il fournit un dictionnaire normatif et structuré des notions du domaine — grandeurs physiques, phénomènes, méthodes, niveaux verticaux, indices climatiques, événements, processus, espèces chimiques — afin que producteurs et consommateurs de données météo se référent aux mêmes concepts.

C'est un **socle sémantique partagé**, pas un entrepôt de données ni un catalogue applicatif. Il décrit *les notions*, pas *les mesures*, et pas *les instances physiques* (stations, instruments, modèles).

### Pourquoi ?

Le champ météo est traversé par plusieurs vocabulaires internationaux maintenus par des organismes de référence (CF Conventions, WMO Codes Registry, QUDT, NERC BODC, ECMWF). Aucun référentiel local francophone n'agrège, n'aligne et n'expose ces vocabulaires sous une forme exploitable et gouvernée. Nephos comble ce manque en :

- réutilisant ces vocabulaires en s'alignant dessus (mappings SKOS), plutôt qu'en les réinventant ;
- introduisant ses propres concepts métier locaux quand ils sont absents des standards ;
- exposant le tout sous un modèle SKOS unifié, multi-hiérarchique et versionné.

### Ce qui est dans le périmètre

- Concepts (grandeurs, phénomènes, processus, indices, événements…), organisés en *concept schemes* multi-hiérarchiques.
- Alignements (`skos:exactMatch`, `closeMatch`, `broadMatch`…) vers les sources standards.
- Unités de mesure, leurs dimensions et conversions, alignées sur QUDT.
- Cycle de vie : workflow de validation, audit, propositions de modification.

### Ce qui est explicitement hors périmètre

- Les **observations et mesures** (Nephos décrit, ne stocke pas).
- Les **instances physiques** (stations, instruments, radars, satellites, modèles).
- Les **fiches dataset / produits** (mais les briques pour les composer existent).

Ce choix est acté en [ADR 0001](docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md) (option A : concepts uniquement).

---

## Architecture en une page

```
┌──────────────────────────────────────────────────────────────────┐
│                       Sources externes                           │
│  CF Standard Names · QUDT · WMO Codes Registry · ECMWF · NERC    │
└──────────────────────────┬───────────────────────────────────────┘
                           │  Pipeline d'import (Python)
                           │  rdflib · pyshacl · lxml
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Nephos — modèle SKOS Core                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  scheme · concept · concept_label · concept_in_scheme      │  │
│  │  concept_semantic_relation (broader/related/*Match)        │  │
│  │  concept_note (definition/scopeNote/example)               │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Extension typage physique : concept_physical · unite      │  │
│  └────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Gouvernance : users · roles · statuses · audit_log        │  │
│  │  proposals · imports · import_sources                      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                            PostgreSQL 14+                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │  API (à décider — ADR 0006)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│           Consommateurs : applis météo, catalogage,              │
│              outils de découverte, exports RDF/SKOS              │
└──────────────────────────────────────────────────────────────────┘
```

**Trois étages indépendants** :

1. **SKOS Core** — la sémantique pure (concepts, schemes, relations, labels, notes).
2. **Typage physique** — pour les concepts mesurables (unité canonique, dimension, plage, précision).
3. **Gouvernance** — workflow de validation, audit, traçabilité d'import.

Voir [ADR 0001](docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md) pour le détail.

---

## État actuel

Le projet est en phase de **bootstrap** : décisions architecturales actées, code applicatif à venir.

| Domaine | Statut |
|---|---|
| Décisions architecturales structurantes | 3 ADR acceptés sur ~9 prévus |
| Schéma SQL v3 (héritage) | Présent dans `schema_referentiel_v3.sql`, **déprécié** — conservé pour référence |
| Schéma SQL v4 SKOS | Présent dans `schema_v4_skos.sql` — modèle SKOS + typage physique + gouvernance |
| Pipeline d'import Python | À écrire (EPIC E4 du backlog) |
| API de consultation | À spécifier (ADR 0006 à rédiger) |

Voir le [BACKLOG.md](BACKLOG.md) pour la trajectoire détaillée.

---

## Démarrage

### Prérequis

- PostgreSQL 14+ (référence : 14, 15 ou 16).
- `psql` ou tout client SQL équivalent.

À mesure que le code applicatif arrive, les prérequis Python (3.12+, `uv`) seront ajoutés.

### Appliquer le schéma v4 SKOS

```bash
createdb nephos_dev
psql -d nephos_dev -f schema_v4_skos.sql
```

Le script crée deux schémas (`gov`, `vocab`), pose les tables SKOS Core (`scheme`, `concept`, `concept_label`, `concept_in_scheme`, `concept_semantic_relation`, `concept_note`, `concept_mapping`), l'extension de typage physique (`concept_physical`, `unite`) et le bloc gouvernance (`users`, `roles`, `statuses`, `audit_log`, `proposals`, `imports`, `import_sources`). Triggers d'audit posés sur les tables principales. Données seed : statuts, rôles, deux utilisateurs (`system`, `admin`), 8 sources d'import.

Voir l'en-tête commenté de `schema_v4_skos.sql` pour la lecture détaillée.

### Schéma v3 (déprécié)

`schema_referentiel_v3.sql` est conservé pour référence et ne doit pas être appliqué en production. Voir l'avertissement en tête du fichier.

---

## Documentation

| Document | Rôle |
|---|---|
| [BACKLOG.md](BACKLOG.md) | Backlog projet en 9 EPICs, priorités, sprints candidats |
| [CHANGELOG.md](CHANGELOG.md) | Journal des modifications (Keep a Changelog 1.1.0) |
| [docs/adr/](docs/adr/) | Architecture Decision Records (format MADR) |

### Décisions d'architecture

| ID | Titre | Statut |
|----|-------|--------|
| [0001](docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md) | Adopter SKOS comme socle du référentiel de métadonnées météo | Accepté |
| [0002](docs/adr/0002-python-comme-stack-dimplementation.md) | Python comme stack d'implémentation du pipeline sémantique | Accepté |
| [0003](docs/adr/0003-domaine-uri-w3id-org.md) | Domaine d'URI : `w3id.org/nephos` | Accepté |
| [0004](docs/adr/0004-strategie-multilingue-fr-en.md) | Stratégie multilingue FR + EN obligatoires sur les concepts publiés | Accepté |
| [0005](docs/adr/0005-licences-apache-2-et-cc-by-4.md) | Licences : Apache 2.0 (code) + CC-BY 4.0 (données originales) | Accepté |
| 0006 | Choix de la façade API (REST custom / GraphQL / auto-génération) | À rédiger |
| 0007 | Outil de curation (Directus / VocBench / app custom) | À rédiger |
| 0008 | Conteneurisation et déploiement | À rédiger |
| [0009](docs/adr/0009-strategie-orchestration-etl.md) | Stratégie d'orchestration ETL (Python + GHA → Kestra sur signal) | Accepté |

---

## Méthode

Le projet est mené en **méthode agile**. Chaque modification est tracée :

- Décisions structurantes → ADR au format [MADR](https://adr.github.io/madr/) dans `docs/adr/`.
- Travail à venir → backlog dans `BACKLOG.md`, structuré en EPICs avec priorités, estimations T-shirt et dépendances.
- Évolutions techniques → entrées dans `CHANGELOG.md` à chaque commit.
- Code → versionné en Git, branche par défaut `main`.

### Sources et standards référencés

- [SKOS — Simple Knowledge Organization System](https://www.w3.org/TR/skos-reference/) (W3C)
- [CF Standard Names](https://cfconventions.org/standard-names.html)
- [WMO Codes Registry](https://codes.wmo.int)
- [QUDT — Quantities, Units, Dimensions and Types](https://qudt.org)
- [NERC Vocabulary Server (BODC)](https://vocab.nerc.ac.uk)
- [SHACL — Shapes Constraint Language](https://www.w3.org/TR/shacl/)

---

## Licence

Double licence — voir [ADR 0005](docs/adr/0005-licences-apache-2-et-cc-by-4.md) :

- **Code** (Python à venir, schémas SQL, scripts, workflows, doc d'ingénierie) : [**Apache 2.0**](LICENSE).
- **Données originales** (concepts maison, mappings éditoriaux, traductions) : [**CC-BY 4.0**](DATA_LICENSE).
- **Données importées** des sources standards : licence d'origine préservée, attribution maintenue dans les exports RDF (`dcterms:source`).

Pour utiliser les données du référentiel, citer Nephos :

> Données issues du référentiel Nephos (https://w3id.org/nephos), licence CC-BY 4.0.

---

## Contact

Repo : https://github.com/benedictemarty/nephos
