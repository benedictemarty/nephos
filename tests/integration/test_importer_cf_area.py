"""Tests d'intégration de `CFAreaTypeImporter` (E4-03)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from nephos.etl.runner import ImportRunner
from nephos.importers.cf_area_type import CFAreaTypeImporter

pytestmark = pytest.mark.integration

CF_AREA_FIXTURE = Path(__file__).parent / "fixtures" / "cf_area_mini.xml"


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _count(conn: psycopg.Connection, sql: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


class TestCFAreaImport:
    def test_import_creates_concepts_and_scheme(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(CFAreaTypeImporter(source=CF_AREA_FIXTURE)).run()

        assert result.version == "13"
        assert result.nb_entites == 4
        assert result.nb_creations == 4

        # 4 concepts dans le scheme `area-types-cf`.
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.scheme WHERE code = 'area-types-cf'",
            )
            == 1
        )
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept WHERE notation IN "
                "('air', 'land', 'sea_ice', 'bare_ground')",
            )
            == 4
        )

        # 3 définitions (bare_ground a une description vide qui devient None).
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept_note WHERE kind = 'definition'",
            )
            == 3
        )

        # Mappings exactMatch vers la fiche CF Area Type officielle.
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept_mapping WHERE mapping_relation = 'exactMatch'",
            )
            == 4
        )

        # Pas de concept_physical (CF Area Type ne porte pas d'unité).
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept_physical") == 0

    def test_idempotent_rerun(self, db_conn: psycopg.Connection) -> None:
        ImportRunner(CFAreaTypeImporter(source=CF_AREA_FIXTURE)).run()
        result2 = ImportRunner(CFAreaTypeImporter(source=CF_AREA_FIXTURE)).run()
        assert result2.nb_creations == 0
        assert result2.nb_skipped == 4

    def test_import_source_id_propagated(self, db_conn: psycopg.Connection) -> None:
        """Le `concept.import_source_id` est bien renseigné sur les insertions."""
        ImportRunner(CFAreaTypeImporter(source=CF_AREA_FIXTURE)).run()
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vocab.concept c "
                "JOIN gov.import_sources s ON s.import_source_id = c.import_source_id "
                "WHERE s.code = 'CF_AREA'"
            )
            row = cur.fetchone()
            assert row is not None
            assert int(row[0]) == 4
