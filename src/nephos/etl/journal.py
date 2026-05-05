"""Journal des imports : interactions avec la table `gov.imports`."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from nephos.etl.base import ImportResult, SourceCode


@dataclass(slots=True)
class ImportJournalEntry:
    """Identifiants d'une exécution journalisée."""

    import_id: int
    source_code: SourceCode
    import_source_id: int
    version: str


def resolve_source(conn: psycopg.Connection, source_code: SourceCode) -> int:
    """Retourne l'`import_source_id` associé au code, lève si introuvable."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT import_source_id FROM gov.import_sources WHERE code = %s",
            (source_code,),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"Source d'import '{source_code}' non déclarée dans gov.import_sources.")
    return int(row[0])


def open_run(
    conn: psycopg.Connection,
    source_code: SourceCode,
    version: str,
    user_id: int | None = None,
) -> ImportJournalEntry:
    """Crée une ligne `gov.imports` en statut `success` (par défaut) et la retourne.

    Le statut sera mis à jour à la fin par `close_run` ou `mark_failed`.
    On commence en `success` plutôt qu'en `partial` pour éviter le bruit
    quand le run se termine effectivement bien — les transitions sont
    toujours possibles.
    """
    src_id = resolve_source(conn, source_code)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO gov.imports
              (import_source_id, version, imported_by, status)
            VALUES (%s, %s, %s, 'success')
            RETURNING import_id
            """,
            (src_id, version, user_id),
        )
        row = cur.fetchone()
        assert row is not None
    return ImportJournalEntry(
        import_id=int(row[0]),
        source_code=source_code,
        import_source_id=src_id,
        version=version,
    )


def close_run(
    conn: psycopg.Connection,
    entry: ImportJournalEntry,
    result: ImportResult,
) -> None:
    """Met à jour la ligne `gov.imports` avec les compteurs finaux."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE gov.imports SET
              nb_entites       = %s,
              nb_creations     = %s,
              nb_modifications = %s,
              nb_skipped       = %s,
              notes            = %s,
              status           = 'success'
            WHERE import_id = %s
            """,
            (
                result.nb_entites,
                result.nb_creations,
                result.nb_modifications,
                result.nb_skipped,
                result.notes,
                entry.import_id,
            ),
        )


def mark_failed(
    conn: psycopg.Connection,
    entry: ImportJournalEntry,
    error_message: str,
) -> None:
    """Marque le run en échec, avec message d'erreur en `notes`.

    Cette fonction est invoquée hors-transaction (autocommit) pour
    garantir que la trace d'échec est persistée même si la transaction
    principale est rollback-ée.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE gov.imports SET
              status = 'failed',
              notes  = %s
            WHERE import_id = %s
            """,
            (error_message[:8000], entry.import_id),
        )
