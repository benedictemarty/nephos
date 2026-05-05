"""Tests des triggers d'audit étendus (E2-04).

Vérifie que les triggers attachés à `concept_label`, `concept_note`,
`concept_in_scheme`, `concept_semantic_relation`, `concept_mapping`,
`concept_physical` et `gov.proposals` remplissent correctement
`gov.audit_log` (INSERT / UPDATE / DELETE).
"""

from __future__ import annotations

import pytest
from psycopg import Connection

pytestmark = pytest.mark.integration


def _audit_rows(
    conn: Connection, schema: str, table: str, entity_id: int
) -> list[tuple[str, list[str] | None]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT action, changed_columns FROM gov.audit_log "
            "WHERE schema_name = %s AND table_name = %s AND entity_id = %s "
            "ORDER BY performed_at",
            (schema, table, entity_id),
        )
        return [(str(action), changed) for action, changed in cur.fetchall()]


def _seed_concept(conn: Connection, notation: str = "x") -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) "
            "VALUES (%s, %s, 'approved') RETURNING concept_id",
            (f"https://w3id.org/nephos/vocab/test/{notation}", notation),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _seed_scheme(conn: Connection, code: str = "t") -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.scheme (uri, code, title) VALUES (%s, %s, %s) RETURNING scheme_id",
            (f"https://w3id.org/nephos/vocab/{code}", code, f"T {code}"),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


class TestAuditTriggerExtended:
    def test_concept_label_insert_logged(self, db_conn: Connection) -> None:
        cid = _seed_concept(db_conn)
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'en', 'pref', 'Hello') RETURNING concept_label_id",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None
            lid = int(row[0])
        rows = _audit_rows(db_conn, "vocab", "concept_label", lid)
        assert len(rows) == 1
        assert rows[0][0] == "INSERT"

    def test_concept_note_update_logged(self, db_conn: Connection) -> None:
        cid = _seed_concept(db_conn, "n")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_note (concept_id, lang, kind, value) "
                "VALUES (%s, 'en', 'definition', 'first') RETURNING concept_note_id",
                (cid,),
            )
            row = cur.fetchone()
            assert row is not None
            nid = int(row[0])
            cur.execute(
                "UPDATE vocab.concept_note SET value = 'second' WHERE concept_note_id = %s",
                (nid,),
            )
        rows = _audit_rows(db_conn, "vocab", "concept_note", nid)
        actions = [r[0] for r in rows]
        assert actions == ["INSERT", "UPDATE"]
        # `value` doit apparaître dans changed_columns du UPDATE.
        assert rows[1][1] is not None and "value" in rows[1][1]

    def test_concept_in_scheme_insert_and_delete_logged(self, db_conn: Connection) -> None:
        cid = _seed_concept(db_conn, "is")
        sid = _seed_scheme(db_conn, "isc")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) "
                "VALUES (%s, %s) RETURNING concept_in_scheme_id",
                (cid, sid),
            )
            row = cur.fetchone()
            assert row is not None
            cisid = int(row[0])
            cur.execute(
                "DELETE FROM vocab.concept_in_scheme WHERE concept_in_scheme_id = %s",
                (cisid,),
            )
        rows = _audit_rows(db_conn, "vocab", "concept_in_scheme", cisid)
        assert [r[0] for r in rows] == ["INSERT", "DELETE"]

    def test_concept_semantic_relation_logged(self, db_conn: Connection) -> None:
        a = _seed_concept(db_conn, "ra")
        b = _seed_concept(db_conn, "rb")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_semantic_relation "
                "(source_concept_id, target_concept_id, relation) "
                "VALUES (%s, %s, 'related') RETURNING relation_id",
                (a, b),
            )
            row = cur.fetchone()
            assert row is not None
            rid = int(row[0])
        rows = _audit_rows(db_conn, "vocab", "concept_semantic_relation", rid)
        assert rows == [("INSERT", None)]

    def test_concept_mapping_logged(self, db_conn: Connection) -> None:
        cid = _seed_concept(db_conn, "mc")
        with db_conn.cursor() as cur:
            cur.execute("SELECT import_source_id FROM gov.import_sources WHERE code = 'CF'")
            row = cur.fetchone()
            assert row is not None
            src_id = int(row[0])
            cur.execute(
                "INSERT INTO vocab.concept_mapping "
                "(concept_id, target_source_id, target_uri, mapping_relation) "
                "VALUES (%s, %s, 'https://example.org/y', 'closeMatch') "
                "RETURNING mapping_id",
                (cid, src_id),
            )
            row = cur.fetchone()
            assert row is not None
            mid = int(row[0])
        rows = _audit_rows(db_conn, "vocab", "concept_mapping", mid)
        assert [r[0] for r in rows] == ["INSERT"]

    def test_concept_physical_logged(self, db_conn: Connection) -> None:
        cid = _seed_concept(db_conn, "ph")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_physical (concept_id, value_type) VALUES (%s, 'scalar')",
                (cid,),
            )
        rows = _audit_rows(db_conn, "vocab", "concept_physical", cid)
        assert [r[0] for r in rows] == ["INSERT"]

    def test_proposals_logged(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO gov.proposals "
                "(target_schema, target_table, action, proposed_payload, "
                " justification, created_by) "
                "VALUES ('vocab', 'concept', 'CREATE', '{}', 'test', 1) "
                "RETURNING proposal_id"
            )
            row = cur.fetchone()
            assert row is not None
            pid = int(row[0])
            cur.execute(
                "UPDATE gov.proposals SET status = 'under_review' WHERE proposal_id = %s",
                (pid,),
            )
        rows = _audit_rows(db_conn, "gov", "proposals", pid)
        # INSERT puis STATUS_CHANGE (la fonction distingue via la colonne `status`).
        assert [r[0] for r in rows] == ["INSERT", "STATUS_CHANGE"]
