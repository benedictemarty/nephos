"""Tests d'intégration de la détection des concepts disparus (E4-08)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from nephos.etl.deprecation import _resolve_source_id, mark_disappeared_concepts
from nephos.etl.runner import ImportRunner, RunOptions
from nephos.importers.wmo_codes import WMOCodesImporter

pytestmark = pytest.mark.integration

WMO_FIXTURE = Path(__file__).parent / "fixtures" / "wmo_bufr_0_02_001_mini.ttl"
WMO_FIXTURE_PARTIAL = Path(__file__).parent / "fixtures" / "wmo_bufr_0_02_001_partial.ttl"


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _build_importer(*, partial: bool = False) -> WMOCodesImporter:
    return WMOCodesImporter(
        register_url=WMO_FIXTURE_PARTIAL if partial else WMO_FIXTURE,
        scheme_code="wmo-bufr-0-02-001",
        scheme_title="WMO BUFR 0-02-001 (test)",
    )


def _count(conn: psycopg.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


class TestDeprecationDetection:
    def test_no_disappeared_when_all_seen(self, db_conn: psycopg.Connection) -> None:
        """Un import nominal ne marque aucun concept deprecated."""
        result = ImportRunner(_build_importer()).run()
        assert result.nb_deprecated_disappeared == 0
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept WHERE status='deprecated'",
            )
            == 0
        )

    def test_disappeared_concepts_become_deprecated(self, db_conn: psycopg.Connection) -> None:
        """Import v1 (4 concepts) puis v2 amputée (2 concepts) → 2 deprecated."""
        ImportRunner(_build_importer()).run()
        result = ImportRunner(_build_importer(partial=True)).run()

        assert result.nb_deprecated_disappeared == 2
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept c "
                "JOIN vocab.concept_in_scheme cis ON cis.concept_id = c.concept_id "
                "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
                "WHERE s.code = 'wmo-bufr-0-02-001' AND c.status = 'deprecated'",
            )
            == 2
        )

    def test_local_override_protects_concept(self, db_conn: psycopg.Connection) -> None:
        """`has_local_override = TRUE` empêche le passage en deprecated."""
        ImportRunner(_build_importer()).run()
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE vocab.concept SET has_local_override = TRUE "
                "WHERE notation = '2' "
                "AND EXISTS (SELECT 1 FROM vocab.concept_in_scheme cis "
                "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
                "WHERE cis.concept_id = vocab.concept.concept_id "
                "AND s.code = 'wmo-bufr-0-02-001')"
            )
        result = ImportRunner(_build_importer(partial=True)).run()
        # Seul le concept notation='3' est deprecated. Le '2' est protégé.
        assert result.nb_deprecated_disappeared == 1

    def test_detection_disabled(self, db_conn: psycopg.Connection) -> None:
        """`detect_disappeared=False` saute l'étape même avec import partiel."""
        ImportRunner(_build_importer()).run()
        result = ImportRunner(_build_importer(partial=True)).run(
            RunOptions(detect_disappeared=False)
        )
        assert result.nb_deprecated_disappeared == 0
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept WHERE status='deprecated'",
            )
            == 0
        )


class TestMarkDisappearedHelper:
    def test_empty_scheme_codes_is_safe_noop(self, db_conn: psycopg.Connection) -> None:
        """Sécurité : pas de scheme cible ⇒ aucun UPDATE même si des concepts seraient candidats."""
        ImportRunner(_build_importer()).run()
        source_id = _resolve_source_id(db_conn, "WMO_CODES")
        nb = mark_disappeared_concepts(
            db_conn,
            source_id=source_id,
            current_version="any",
            scheme_codes=(),
        )
        assert nb == 0
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept WHERE status='deprecated'",
            )
            == 0
        )

    def test_scheme_filter_isolates_other_schemes(self, db_conn: psycopg.Connection) -> None:
        """Un import d'une code list ne déprécie pas les concepts d'une autre."""
        # 1er import : preset 0-02-001 (4 concepts).
        ImportRunner(_build_importer()).run()
        # On simule des concepts dans un autre scheme WMO sous la même source.
        with db_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vocab.scheme (uri, code, title, status)
                VALUES ('https://w3id.org/nephos/vocab/wmo-bufr-other',
                        'wmo-bufr-other', 'Autre scheme WMO', 'approved')
                RETURNING scheme_id
                """
            )
            row = cur.fetchone()
            assert row is not None
            other_scheme_id = int(row[0])
            cur.execute("SELECT import_source_id FROM gov.import_sources WHERE code = 'WMO_CODES'")
            source_id_row = cur.fetchone()
            assert source_id_row is not None
            wmo_source_id = int(source_id_row[0])
            cur.execute(
                """
                INSERT INTO vocab.concept
                  (uri, notation, status, import_source_id, import_version, last_synced_at)
                VALUES ('https://w3id.org/nephos/vocab/wmo-bufr-other/x',
                        'x', 'approved', %s, 'OLD-VERSION', now())
                RETURNING concept_id
                """,
                (wmo_source_id,),
            )
            row = cur.fetchone()
            assert row is not None
            other_concept_id = int(row[0])
            cur.execute(
                "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
                (other_concept_id, other_scheme_id),
            )

        # Re-import partiel sur le seul scheme `wmo-bufr-0-02-001`.
        result = ImportRunner(_build_importer(partial=True)).run()

        # 2 deprecated dans 0-02-001, 0 dans 'wmo-bufr-other' (préservé).
        assert result.nb_deprecated_disappeared == 2
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept c "
                "JOIN vocab.concept_in_scheme cis ON cis.concept_id = c.concept_id "
                "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
                "WHERE s.code = 'wmo-bufr-other' AND c.status = 'deprecated'",
            )
            == 0
        )
