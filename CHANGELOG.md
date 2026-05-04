# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog 1.1.0](https://keepachangelog.com/fr/1.1.0/)
et ce projet adhère au [versionnement sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté

- **ADR 0001** — adoption de SKOS (W3C) comme socle conceptuel du référentiel de métadonnées météo (`docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md`). Acte la refonte du modèle `vocab.types_grandeur` + `vocab.champs` en taxonomie multi-hiérarchique, restreint le périmètre aux concepts (option A) et exclut explicitement les tables `catalog.*`, `vocab.acteurs` et `vocab.licences`. Définit la stratégie de remplissage par import majoritaire (CF, QUDT, WMO) plutôt que par saisie manuelle.
- Initialisation du dépôt Git (branche `main`).
- `schema_referentiel_v3.sql` — schéma PostgreSQL initial du référentiel météorologique (v3, 873 lignes, schémas `gov` / `vocab` / `catalog`).
- `CLAUDE.md` — guide d'architecture à destination de Claude Code.
- `.gitignore` — exclusions standard (OS, éditeurs, dumps PostgreSQL, secrets, caches Python).

### Décisions d'architecture (ADR)

| ID | Titre | Statut |
|----|-------|--------|
| [0001](docs/adr/0001-adopter-skos-comme-socle-du-referentiel.md) | Adopter SKOS comme socle du référentiel de métadonnées météo | Accepté |
