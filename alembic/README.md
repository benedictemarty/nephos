# Migrations Alembic — Nephos

Versionne les évolutions du schéma PostgreSQL.

## Pourquoi pas d'autogenerate

Nephos n'utilise pas SQLAlchemy comme ORM : le schéma est défini en
SQL pur dans `schema_v4_skos.sql`. Alembic sert uniquement à versionner
les évolutions du schéma sous forme de scripts (`op.execute(SQL)` ou
appels `op.create_table` / `op.add_column` selon le confort). La cible
de métadonnées (`target_metadata`) reste à `None`.

## Convention de nommage

Format `file_template` configuré dans `alembic.ini` :

```
YYYYMMDD_HHMM_<slug>_<rev>.py
```

Exemple : `20260505_0000_init_schema_v4_skos_0001.py`

## Workflow

```bash
# Créer une nouvelle migration vide
uv run alembic revision -m "ajout colonne X"

# Appliquer toutes les migrations en attente
uv run alembic upgrade head

# Revenir à la révision précédente
uv run alembic downgrade -1

# Voir l'état courant
uv run alembic current

# Voir l'historique
uv run alembic history --verbose
```

L'URL de connexion est lue depuis la configuration applicative
(`nephos.config.Settings.database_url`), elle-même alimentée par
`NEPHOS_DATABASE_URL` ou `.env`.

## Première migration : `0001 — init schema v4 SKOS`

Applique en bloc le contenu de `schema_v4_skos.sql`. C'est le **point
de départ versionné** du modèle. Toute évolution future devra :

- soit ajouter une colonne / contrainte / index via `op.execute(SQL)` ;
- soit refondre une table avec migration de données dans `upgrade()`.

Le `downgrade()` de cette migration initiale supprime les schémas
`gov` et `vocab` (cohérent avec le `DROP SCHEMA … CASCADE` en tête
du fichier SQL).
