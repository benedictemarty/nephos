"""init schema v4 SKOS

Migration initiale Nephos. Applique le contenu de `schema_v4_skos.sql`
en bloc — point de départ versionné du modèle SKOS.

Revision ID: 0001
Revises:
Create Date: 2026-05-05

"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

# Identifiants de révision Alembic
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _read_schema_sql() -> str:
    """Charge le fichier SQL du schéma v4 depuis la racine du dépôt."""
    repo_root = Path(__file__).resolve().parents[2]
    sql_path = repo_root / "schema_v4_skos.sql"
    return sql_path.read_text(encoding="utf-8")


def upgrade() -> None:
    """Applique le schéma v4 SKOS complet."""
    op.execute(_read_schema_sql())


def downgrade() -> None:
    """Supprime les schémas créés par le v4 SKOS.

    Le schéma v4 est destructif à l'application (DROP SCHEMA … CASCADE),
    le downgrade rétablit donc simplement l'état pré-application en
    supprimant les schémas créés.
    """
    op.execute("DROP SCHEMA IF EXISTS vocab CASCADE;")
    op.execute("DROP SCHEMA IF EXISTS gov CASCADE;")
