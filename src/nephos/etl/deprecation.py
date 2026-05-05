"""Détection des concepts disparus côté source (E4-08).

Quand un import ré-aspire la totalité d'une source amont, certains
concepts présents en base peuvent ne plus apparaître côté source —
soit retirés du standard, soit renommés. La règle Nephos : on ne
**supprime jamais** de concept (l'historique reste lisible), on les
passe en ``status='deprecated'``.

Mécanique : après le ``load``, tous les concepts ``import_version``
qui ne correspondent **pas** à la version courante de l'import, dans
les schemes ciblés par l'importer (`Importer.target_scheme_codes`),
et **sans** ``has_local_override`` actif, sont marqués deprecated.
``has_local_override = TRUE`` protège les modifications curées
manuellement.
"""

from __future__ import annotations

import psycopg

from nephos.logging import get_logger

logger = get_logger(__name__)


def mark_disappeared_concepts(
    conn: psycopg.Connection,
    *,
    source_id: int,
    current_version: str,
    scheme_codes: tuple[str, ...],
) -> int:
    """Passe en `deprecated` les concepts disparus de la source.

    Critères du UPDATE :
    - ``c.import_source_id = source_id`` ;
    - ``c.import_version IS NOT NULL AND c.import_version <> current_version`` ;
    - ``c.has_local_override = FALSE`` ;
    - ``c.status NOT IN ('deprecated', 'retired')`` ;
    - le concept est rattaché à au moins l'un des ``scheme_codes`` cibles.

    Si ``scheme_codes`` est vide, retourne 0 sans toucher la base —
    sécurité contre une mauvaise config qui marquerait tout le
    référentiel deprecated.

    Retourne le nombre de concepts effectivement marqués.
    """
    if not scheme_codes:
        return 0

    sql = """
        UPDATE vocab.concept c
           SET status = 'deprecated',
               modified_at = now()
         WHERE c.import_source_id = %s
           AND c.import_version IS NOT NULL
           AND c.import_version <> %s
           AND c.has_local_override = FALSE
           AND c.status NOT IN ('deprecated', 'retired')
           AND EXISTS (
                 SELECT 1
                   FROM vocab.concept_in_scheme cis
                   JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id
                  WHERE cis.concept_id = c.concept_id
                    AND s.code = ANY(%s)
           )
    """
    with conn.cursor() as cur:
        cur.execute(sql, (source_id, current_version, list(scheme_codes)))
        nb = cur.rowcount or 0
    if nb:
        logger.info(
            "Concepts marqués deprecated (disparus côté source)",
            extra={
                "source_id": source_id,
                "current_version": current_version,
                "scheme_codes": list(scheme_codes),
                "nb_deprecated": nb,
            },
        )
    return nb


def _resolve_source_id(conn: psycopg.Connection, source_code: str) -> int:
    """Résout le ``source_code`` vers son ``import_source_id`` numérique."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT import_source_id FROM gov.import_sources WHERE code = %s",
            (source_code,),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"Source d'import '{source_code}' inconnue.")
    return int(row[0])
