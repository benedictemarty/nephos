"""Tests d'intégration du framework ETL avec une source factice.

Vérifie que `ImportRunner` :
- crée la ligne `gov.imports` dès l'ouverture
- met à jour les compteurs en succès
- marque le run `failed` en cas d'exception du chargement
- rollback la transaction de chargement quand l'`Importer` lève
- supporte le mode `dry_run` sans écrire en base
- ne crée pas de doublons concept lors d'un re-run idempotent
"""

from __future__ import annotations

import os

import psycopg
import pytest

from nephos.etl.base import Importer, ImportResult, SourceCode
from nephos.etl.exceptions import ImportError as EtlImportError
from nephos.etl.runner import ImportRunner, RunOptions

pytestmark = pytest.mark.integration


# ----------------------------------------------------------------------
# Fixtures spécifiques : on a besoin d'une URL stable pendant le test
# parce que ImportRunner ouvre ses propres connexions via nephos.db.
# ----------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """Propage l'URL de test dans l'environnement pour `nephos.db.connect`."""
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    # `nephos.db.connect` lit la config via `get_settings()` qui relit
    # l'environnement à chaque appel — il suffit de garantir que la
    # variable est en place pendant la durée du test.
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


# ----------------------------------------------------------------------
# Importer factice : trois entrées, transform = passe-plat,
# load = INSERT idempotent dans vocab.concept.
# ----------------------------------------------------------------------


class FakeImporter(Importer):
    source_code = SourceCode("CF")
    source_format = "fake"

    def __init__(
        self,
        version: str = "1.0",
        entries: list[dict[str, object]] | None = None,
        fail_on_load: bool = False,
    ) -> None:
        self._version = version
        self._entries = entries or [
            {"uri": "https://w3id.org/nephos/vocab/test/a", "notation": "a"},
            {"uri": "https://w3id.org/nephos/vocab/test/b", "notation": "b"},
            {"uri": "https://w3id.org/nephos/vocab/test/c", "notation": "c"},
        ]
        self._fail_on_load = fail_on_load

    def discover_version(self) -> str:
        return self._version

    def extract(self) -> object:
        return self._entries

    def transform(self, raw: object) -> list[dict[str, object]]:
        assert isinstance(raw, list)
        return raw

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        if self._fail_on_load:
            raise RuntimeError("simulation d'échec")
        nb_creations = 0
        nb_skipped = 0
        with conn.cursor() as cur:
            for e in entries:
                cur.execute(
                    """
                    INSERT INTO vocab.concept (uri, notation, status, import_version)
                    VALUES (%s, %s, 'draft', %s)
                    ON CONFLICT (uri) DO NOTHING
                    """,
                    (e["uri"], e["notation"], version),
                )
                if cur.rowcount == 1:
                    nb_creations += 1
                else:
                    nb_skipped += 1
        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=len(entries),
            nb_creations=nb_creations,
            nb_skipped=nb_skipped,
        )


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def _count_concepts(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM vocab.concept")
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _last_import_status(conn: psycopg.Connection) -> tuple[str, int, int, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, nb_entites, nb_creations, nb_skipped FROM gov.imports "
            "ORDER BY imported_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        assert row is not None
        return (str(row[0]), int(row[1] or 0), int(row[2] or 0), int(row[3] or 0))


class TestImportRunner:
    def test_run_creates_concepts_and_marks_success(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(FakeImporter(version="v1")).run()

        assert result.nb_entites == 3
        assert result.nb_creations == 3
        assert result.nb_skipped == 0
        assert _count_concepts(db_conn) == 3

        status, n, creations, skipped = _last_import_status(db_conn)
        assert status == "success"
        assert n == 3
        assert creations == 3
        assert skipped == 0

    def test_idempotent_rerun_skips_existing(self, db_conn: psycopg.Connection) -> None:
        importer = FakeImporter(version="v1")
        ImportRunner(importer).run()
        result2 = ImportRunner(importer).run()

        assert result2.nb_creations == 0
        assert result2.nb_skipped == 3
        assert _count_concepts(db_conn) == 3

    def test_failure_rolls_back_load_and_marks_failed(self, db_conn: psycopg.Connection) -> None:
        runner = ImportRunner(FakeImporter(version="v1", fail_on_load=True))

        with pytest.raises(EtlImportError):
            runner.run()

        # Aucun concept écrit, mais la ligne gov.imports existe en 'failed'.
        assert _count_concepts(db_conn) == 0
        status, _, _, _ = _last_import_status(db_conn)
        assert status == "failed"

    def test_dry_run_does_not_write(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(FakeImporter(version="v1")).run(RunOptions(dry_run=True))

        assert result.nb_entites == 3
        assert result.nb_creations == 0
        assert _count_concepts(db_conn) == 0
        # En dry-run aucune ligne n'est créée dans gov.imports.
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gov.imports")
            row = cur.fetchone()
            assert row is not None and row[0] == 0


class TestUnknownSource:
    def test_unknown_source_raises(self, db_conn: psycopg.Connection) -> None:
        class UnknownSourceImporter(FakeImporter):
            source_code = SourceCode("DOES_NOT_EXIST")

        runner = ImportRunner(UnknownSourceImporter())
        with pytest.raises(EtlImportError):
            runner.run()
