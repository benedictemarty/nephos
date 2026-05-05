"""Fixtures pytest partagées.

Stratégie : on ne lance pas de Postgres embarqué. La base est fournie
extérieurement (service Postgres en CI, conteneur via docker-compose
en dev). L'URL de connexion est lue depuis `NEPHOS_DATABASE_URL`.

Les tests d'intégration sont **isolés par recréation des schémas** dans
une transaction d'init avant chaque test, en appliquant
`schema_v4_skos.sql` à chaque fois. C'est lent mais fiable et évite
toute fuite d'état.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = REPO_ROOT / "schema_v4_skos.sql"


def _database_url() -> str:
    """Retourne l'URL de la base de tests, ou skip si non configurée."""
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if not url:
        pytest.skip(
            "NEPHOS_DATABASE_URL n'est pas définie ; "
            "tests d'intégration sautés (configurer une base PG)."
        )
    return url


@pytest.fixture(scope="session")
def schema_sql() -> str:
    """Charge le contenu du fichier de schéma une seule fois par session."""
    if not SCHEMA_SQL.exists():
        pytest.skip(f"Schéma introuvable : {SCHEMA_SQL}")
    return SCHEMA_SQL.read_text(encoding="utf-8")


@pytest.fixture
def db_conn(schema_sql: str) -> Iterator[psycopg.Connection]:
    """Connexion PostgreSQL avec schéma v4 ré-appliqué avant chaque test.

    Yields une connexion en autocommit. Le schéma est entièrement détruit
    et recréé à chaque test (fiable mais coûteux ; à compenser par un
    nombre de tests raisonnable).
    """
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        # Le script schema_v4_skos.sql commence lui-même par DROP SCHEMA …
        # CASCADE, donc l'isolation est garantie.
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        yield conn


@pytest.fixture
def admin_user_id(db_conn: psycopg.Connection) -> int:
    """Retourne l'id de l'utilisateur 'admin' (créé par le seed du schéma)."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT user_id FROM gov.users WHERE username = 'admin'")
        row = cur.fetchone()
        assert row is not None, "Utilisateur admin manquant dans le seed."
        return int(row[0])
