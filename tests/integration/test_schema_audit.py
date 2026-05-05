"""Tests des triggers d'audit (`gov.audit_log`).

Vérifie que les triggers attachés à `scheme`, `concept` et `unite`
remplissent correctement `gov.audit_log` et distinguent
INSERT / UPDATE / STATUS_CHANGE / DELETE.
"""

from __future__ import annotations

import pytest
from psycopg import Connection

pytestmark = pytest.mark.integration


def _audit_rows(conn: Connection, table: str, entity_id: int) -> list[tuple[str, list[str] | None]]:
    """Retourne (action, changed_columns) pour les entrées d'audit d'un objet."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT action, changed_columns FROM gov.audit_log "
            "WHERE schema_name = 'vocab' AND table_name = %s AND entity_id = %s "
            "ORDER BY performed_at",
            (table, entity_id),
        )
        return [(str(action), changed) for action, changed in cur.fetchall()]


class TestAuditTrigger:
    def test_insert_logs_insert(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) "
                "VALUES ('https://w3id.org/nephos/vocab/test/x', 'x', 'draft') "
                "RETURNING concept_id"
            )
            row = cur.fetchone()
            assert row is not None
            cid = int(row[0])

        rows = _audit_rows(db_conn, "concept", cid)
        assert len(rows) == 1
        assert rows[0][0] == "INSERT"

    def test_update_logs_update_with_changed_columns(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) "
                "VALUES ('https://w3id.org/nephos/vocab/test/x', 'x', 'draft') "
                "RETURNING concept_id"
            )
            row = cur.fetchone()
            assert row is not None
            cid = int(row[0])
            # Modification d'une colonne hors gouvernance
            cur.execute(
                "UPDATE vocab.concept SET notation = 'x_renamed' WHERE concept_id = %s",
                (cid,),
            )

        rows = _audit_rows(db_conn, "concept", cid)
        assert [r[0] for r in rows] == ["INSERT", "UPDATE"]
        assert rows[1][1] is not None
        assert "notation" in rows[1][1]
        # modified_at / modified_by / version sont volontairement filtrés
        assert "modified_at" not in rows[1][1]

    def test_status_change_logs_status_change(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) "
                "VALUES ('https://w3id.org/nephos/vocab/test/x', 'x', 'draft') "
                "RETURNING concept_id"
            )
            row = cur.fetchone()
            assert row is not None
            cid = int(row[0])
            cur.execute(
                "UPDATE vocab.concept SET status = 'proposed' WHERE concept_id = %s",
                (cid,),
            )

        rows = _audit_rows(db_conn, "concept", cid)
        assert [r[0] for r in rows] == ["INSERT", "STATUS_CHANGE"]

    def test_delete_logs_delete(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) "
                "VALUES ('https://w3id.org/nephos/vocab/test/x', 'x', 'draft') "
                "RETURNING concept_id"
            )
            row = cur.fetchone()
            assert row is not None
            cid = int(row[0])
            cur.execute("DELETE FROM vocab.concept WHERE concept_id = %s", (cid,))

        rows = _audit_rows(db_conn, "concept", cid)
        assert [r[0] for r in rows] == ["INSERT", "DELETE"]

    def test_audit_trigger_attached_to_scheme(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.scheme (uri, code, title) "
                "VALUES ('https://w3id.org/nephos/vocab/test', 'test', 'Test') "
                "RETURNING scheme_id"
            )
            row = cur.fetchone()
            assert row is not None
            sid = int(row[0])

        rows = _audit_rows(db_conn, "scheme", sid)
        assert len(rows) == 1
        assert rows[0][0] == "INSERT"

    def test_audit_trigger_attached_to_unite(self, db_conn: Connection) -> None:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.unite (symbole, nom, est_si_canonique, status) "
                "VALUES ('K', 'Kelvin', TRUE, 'published') RETURNING unite_id"
            )
            row = cur.fetchone()
            assert row is not None
            uid = int(row[0])

        rows = _audit_rows(db_conn, "unite", uid)
        assert len(rows) == 1
        assert rows[0][0] == "INSERT"
