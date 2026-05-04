# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository scope

Single PostgreSQL DDL script: `schema_referentiel_v3.sql`. Defines a meteorological reference data hub (vocabularies + physical-instance catalogs + governance/audit). No application code, no build system, no tests. Target: **PostgreSQL 14+**.

## Applying the schema

The script is destructive — it begins with `DROP SCHEMA ... CASCADE` for the three schemas it owns (`gov`, `vocab`, `catalog`) before recreating them. Never run it against a database holding data you intend to keep.

```bash
# Local apply (creates a fresh DB if you want isolation)
createdb referentiel_meteo
psql -d referentiel_meteo -f schema_referentiel_v3.sql

# Re-apply (safe — the script drops & recreates its own schemas only)
psql -d referentiel_meteo -f schema_referentiel_v3.sql

# Syntax check without executing (Postgres has no real --dry-run; use a throwaway DB)
psql -d "$(mktemp -u pgcheck_XXXX)" --single-transaction -f schema_referentiel_v3.sql
```

The script ends with seed data (statuses, roles, the `system` + `admin` users, import sources, acteurs, licences, units, types, champs). Re-running it resets all of that.

## Architecture — what to read multiple sections together to understand

Three schemas with a deliberate dependency direction: `gov` ← `vocab` ← `catalog`. `catalog` references `vocab` (e.g. `catalog.stations.operateur_id → vocab.acteurs`); `vocab` references `gov` (every entity's `status`, `created_by`, `import_source_id`). Nothing in `gov` depends on the other two.

- **`gov.*`** — governance plumbing: `users`, `roles`, `user_roles` (with optional `scope`), `statuses` (the workflow lookup), `import_sources`, `imports` (run log), `audit_log` (filled by trigger), `proposals` (change-request workflow with its own status enum, separate from entity statuses).
- **`vocab.*`** — semantic vocabularies: `acteurs`, `licences`, `codes_qualite`, `niveaux_validation`, `niveaux_traitement`, `unites`, `methodes`, `types_grandeur`, `champs`. `champs` is the central node — typed variable definitions referencing `types_grandeur`, `methodes`, and (optionally overriding) `unites`.
- **`catalog.*`** — physical instances: `stations`, `instruments`, `modeles`, `grilles_def`, `radars`, `plateformes_sat`, `capteurs_sat`, `canaux_sat`. `instruments` and `radars` hang off `stations`; `capteurs_sat` off `plateformes_sat`; `canaux_sat` off `capteurs_sat`.

### The four cross-cutting column groups (every `vocab.*` and `catalog.*` table)

When adding or modifying a table, replicate the pattern exactly — views, triggers, and the import workflow all assume it:

1. **Workflow** — `status TEXT NOT NULL DEFAULT 'draft' REFERENCES gov.statuses(status)`. Lifecycle: `draft → proposed → approved → published → deprecated → retired`.
2. **Temporality** — `valid_from TIMESTAMPTZ NOT NULL DEFAULT now()`, `valid_to TIMESTAMPTZ` (NULL = open-ended).
3. **Versioning + audit** — `version INTEGER NOT NULL DEFAULT 1`, `created_by/at`, `modified_by/at` (FK to `gov.users`).
4. **Import traceability** (only on tables that can be sourced externally) — `import_source_id`, `import_version`, `last_synced_at`, `has_local_override`. A few small lookup tables (`niveaux_validation`, `niveaux_traitement`, `methodes`, several `catalog` join tables) intentionally omit these — keep that distinction.

### Audit trigger — the convention that makes it work

`gov.audit_trigger_func()` is generic and reads the PK column name from `TG_ARGV[0]`, falling back to `TG_TABLE_NAME || '_id'`. Two consequences:

- When attaching it, pass the explicit PK if the column doesn't follow the default (e.g. `vocab.champs` PK is `champ_id`, but `vocab.types_grandeur` PK is `type_id` — both need explicit args).
- The function diff-logs JSONB but ignores `modified_at`, `modified_by`, `version` when computing `changed_columns`. UPDATE rows where `status` actually changed are logged as `STATUS_CHANGE` instead of `UPDATE`.

Triggers are currently attached to `vocab.champs`, `vocab.types_grandeur`, `vocab.unites`, `catalog.stations`. The schema explicitly notes "Reproduire pour les autres tables selon besoin" — adding a new audited table means a new `CREATE TRIGGER` block at the end of section 4.

### Business views (section 6) — what consumers depend on

- `vocab.v_champs_actifs` — joins `champs` to `types_grandeur`, `unites` (with override fallback `COALESCE(uo.symbole, ud.symbole)`), `methodes`. Filters `status='published'` AND inside `[valid_from, valid_to)`. This is the *public-facing read API* of the vocabulary.
- `gov.v_proposals_pending`, `gov.v_audit_recent`, `gov.v_imports_status` — operational dashboards. The last one UNION-ALLs `import_source_id` columns across five tables; if you add a new import-traced table, add it to that UNION or it won't appear in the sync status.

### Seed data conventions

- Status `'published'` is required for an entity to surface through `v_champs_actifs` and similar views — drafts are invisible.
- All seeded `created_by` values are `2` (the `admin` user inserted just above). Keep that pattern when adding seeds; user 1 is `system` (reserved for automated imports).
- Unit conversions follow `value_si = value * facteur_conversion + offset_conversion`. Canonical SI units have `est_si_canonique=TRUE` and `unite_si_canonique_id=NULL`; derived units point back to their canonical.

## Editing this schema

- Re-running the script is the iteration loop — there is no migration tool here. Treat each edit as a full rewrite of the target schemas.
- Preserve French comments and `COMMENT ON` clauses; they are part of the deliverable.
- The file is ASCII-safe except for unit symbols and physics dimensions (`°C`, `M·L⁻¹·T⁻²`, `ρHV`). Keep UTF-8.
