"""Tests d'intégration de `QUDTUnitsImporter` (item E4-04).

Vérifie le bout-en-bout import → vocab.unite sur une fixture Turtle
mini (4 unités). Pas d'appel réseau : le `source=` pointe sur un
fichier local versionné dans le repo.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from nephos.etl.runner import ImportRunner, RunOptions
from nephos.importers.qudt_units import QUDTUnitsImporter

pytestmark = pytest.mark.integration

QUDT_FIXTURE = Path(__file__).parent / "fixtures" / "qudt_units_mini.ttl"


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


def _scalar(conn: psycopg.Connection, sql: str, params: tuple[object, ...] = ()) -> object:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        assert row is not None
        return row[0]


class TestQUDTImport:
    def test_import_creates_units_with_qudt_uri(self, db_conn: psycopg.Connection) -> None:
        importer = QUDTUnitsImporter(source=QUDT_FIXTURE)
        result = ImportRunner(importer).run()

        assert result.version == "2.1.47"
        assert result.nb_entites == 4
        assert result.nb_creations == 4
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.unite WHERE qudt_uri IS NOT NULL") == 4

        # Kelvin importée comme SI canonique sans offset
        row = _scalar(
            db_conn,
            "SELECT row_to_json(u) FROM vocab.unite u WHERE symbole = %s",
            ("K",),
        )
        assert isinstance(row, dict)
        assert row["nom"] == "Kelvin"
        assert row["est_si_canonique"] is True
        assert row["facteur_conversion"] == 1.0
        assert row["qudt_uri"] == "http://qudt.org/vocab/unit/K"

        # Degré Celsius importée avec offset → pas SI canonique
        row_c = _scalar(
            db_conn,
            "SELECT row_to_json(u) FROM vocab.unite u WHERE symbole = %s",
            ("°C",),
        )
        assert isinstance(row_c, dict)
        assert row_c["est_si_canonique"] is False
        assert row_c["offset_conversion"] == 273.15

    def test_idempotent_rerun_updates_in_place(self, db_conn: psycopg.Connection) -> None:
        ImportRunner(QUDTUnitsImporter(source=QUDT_FIXTURE)).run()
        result2 = ImportRunner(QUDTUnitsImporter(source=QUDT_FIXTURE)).run()
        assert result2.nb_creations == 0
        # 2e run met à jour les lignes existantes (re-set des champs).
        assert result2.nb_modifications == 4
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.unite") == 4

    def test_dry_run_writes_nothing(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(QUDTUnitsImporter(source=QUDT_FIXTURE)).run(RunOptions(dry_run=True))
        assert result.nb_entites == 4
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.unite") == 0

    def test_existing_unit_with_same_symbol_is_enriched(self, db_conn: psycopg.Connection) -> None:
        # Cas réaliste : une unité 'K' existe déjà (par ex. ajoutée par seed
        # ou par un autre import) sans qudt_uri.
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.unite (symbole, nom, status) VALUES ('K', 'kelvin (seed)', 'published')"
            )

        ImportRunner(QUDTUnitsImporter(source=QUDT_FIXTURE)).run()

        # La ligne existante doit avoir été enrichie, pas dédupliquée.
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.unite WHERE symbole = 'K'") == 1
        qudt_uri = _scalar(
            db_conn,
            "SELECT qudt_uri FROM vocab.unite WHERE symbole = 'K'",
        )
        assert qudt_uri == "http://qudt.org/vocab/unit/K"

    def test_local_override_is_protected(self, db_conn: psycopg.Connection) -> None:
        ImportRunner(QUDTUnitsImporter(source=QUDT_FIXTURE)).run()

        # Modifie une unité localement
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE vocab.unite SET nom = 'Kelvin (custom)', has_local_override = TRUE "
                "WHERE symbole = 'K'"
            )

        result = ImportRunner(QUDTUnitsImporter(source=QUDT_FIXTURE)).run()
        assert result.nb_overrides_protected == 1
        nom = _scalar(db_conn, "SELECT nom FROM vocab.unite WHERE symbole = 'K'")
        assert nom == "Kelvin (custom)"


class TestQUDTTransform:
    def test_transform_extracts_all_units(self) -> None:
        importer = QUDTUnitsImporter(source=QUDT_FIXTURE)
        version = importer.discover_version()
        entries = importer.transform(importer.extract())
        assert version == "2.1.47"
        assert len(entries) == 4
        symbols = {e["symbol"] for e in entries}
        assert symbols == {"K", "Pa", "m/s", "°C"}

    def test_transform_marks_si_canonical_when_no_offset(self) -> None:
        importer = QUDTUnitsImporter(source=QUDT_FIXTURE)
        importer.discover_version()
        entries = {e["symbol"]: e for e in importer.transform(importer.extract())}
        assert entries["K"]["is_si_canonical"] is True
        assert entries["Pa"]["is_si_canonical"] is True
        assert entries["°C"]["is_si_canonical"] is False  # offset 273.15
