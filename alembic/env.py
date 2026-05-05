"""Environnement Alembic pour Nephos.

L'URL de la base est lue depuis la configuration applicative
(`nephos.config.Settings`), elle-même alimentée par les variables
d'environnement préfixées `NEPHOS_` ou un fichier `.env`.

Le projet n'utilise pas SQLAlchemy comme ORM : le schéma est défini
en SQL pur (`schema_v4_skos.sql`), et Alembic sert uniquement à
versionner les évolutions sous forme de scripts SQL ou de blocs
`op.execute(...)`. `target_metadata` reste à `None`.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from nephos.config import get_settings

# Configuration Alembic injectée par le runtime
config = context.config

# Charge les loggers définis dans alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injecte l'URL réelle depuis la config Nephos
settings = get_settings()
config.set_main_option("sqlalchemy.url", str(settings.database_url))

# Pas de modèles SQLAlchemy dans ce projet : autogenerate désactivé.
target_metadata = None


def run_migrations_offline() -> None:
    """Migrations en mode 'offline' — émission de SQL sur stdout."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrations en mode 'online' — connexion réelle à la base."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
