"""Tests d'intégration de la validation SHACL post-import (E5-03).

Vérifie que `ImportRunner` peut chaîner une validation SHACL après le
`load`, soit en mode informatif (notes), soit en mode strict (rollback).
"""

from __future__ import annotations

import os

import psycopg
import pytest

from nephos.etl.base import Importer, ImportResult, SourceCode
from nephos.etl.exceptions import ImportValidationError
from nephos.etl.runner import ImportRunner, RunOptions

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


class _ConformingImporter(Importer):
    """Insère 1 concept valide (URI Nephos, notation conforme, prefLabel@en)."""

    source_code = SourceCode("CF")
    source_format = "fake"

    def discover_version(self) -> str:
        return "test-conforming"

    def extract(self) -> object:
        return None

    def transform(self, raw: object) -> list[dict[str, object]]:
        return []

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) "
                "VALUES (%s, %s, 'approved') RETURNING concept_id",
                ("https://w3id.org/nephos/vocab/test/foo", "foo"),
            )
            row = cur.fetchone()
            assert row is not None
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'en', 'pref', 'Foo')",
                (int(row[0]),),
            )
        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=1,
            nb_creations=1,
        )


class _ViolatingImporter(_ConformingImporter):
    """Insère 1 concept invalide : URI hors namespace Nephos."""

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) " "VALUES (%s, %s, 'approved')",
                ("https://example.org/wrong-namespace/foo", "foo"),
            )
        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=1,
            nb_creations=1,
        )


def _count(conn: psycopg.Connection, sql: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


class TestPostImportValidation:
    def test_default_runs_validation_and_records_notes(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(_ConformingImporter()).run()
        assert result.notes is not None
        assert "SHACL" in result.notes
        assert "0 violation" in result.notes
        # Les concepts insérés sont préservés
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept") == 1

    def test_disabled_validation_leaves_no_notes(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(_ConformingImporter()).run(RunOptions(validate_after=False))
        assert result.notes is None or "SHACL" not in (result.notes or "")

    def test_violations_in_lax_mode_record_but_do_not_block(
        self, db_conn: psycopg.Connection
    ) -> None:
        result = ImportRunner(_ViolatingImporter()).run(RunOptions(strict_validation=False))
        assert result.notes is not None
        assert "violation" in result.notes.lower()
        # Le concept invalide est commité (mode lax)
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept") == 1

    def test_violations_in_strict_mode_rollback(self, db_conn: psycopg.Connection) -> None:
        with pytest.raises(ImportValidationError):
            ImportRunner(_ViolatingImporter()).run(RunOptions(strict_validation=True))
        # Rollback : le concept invalide n'est pas en base
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept") == 0
        # Le journal `gov.imports` est marqué failed
        with db_conn.cursor() as cur:
            cur.execute("SELECT status FROM gov.imports ORDER BY imported_at DESC LIMIT 1")
            row = cur.fetchone()
            assert row is not None
            assert str(row[0]) == "failed"
