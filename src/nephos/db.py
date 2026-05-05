"""Helpers de connexion PostgreSQL.

Centralise l'acquisition de connexions psycopg pour le reste du code
applicatif. Pas de pool de connexions au démarrage — la charge attendue
(imports périodiques, peu d'écritures simultanées) ne le justifie pas.
À introduire si le besoin émerge.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from nephos.config import Settings, get_settings


@contextmanager
def connect(
    settings: Settings | None = None, *, autocommit: bool = False
) -> Iterator[psycopg.Connection]:
    """Ouvre une connexion PostgreSQL avec la configuration applicative.

    Par défaut transactionnel (autocommit=False). Le contexte ferme la
    connexion proprement à la sortie ; les erreurs déclenchent un rollback
    automatique.
    """
    settings = settings or get_settings()
    with psycopg.connect(str(settings.database_url), autocommit=autocommit) as conn:
        yield conn
