"""Tests d'intégration de `ECMWFMappingsImporter` (E4-06)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from nephos.etl.runner import ImportRunner
from nephos.importers.ecmwf_mappings import (
    ECMWFMappingsImporter,
    _build_ecmwf_url,
    _iter_entries,
)

pytestmark = pytest.mark.integration

CFNAME_FIXTURE = Path(__file__).parent / "fixtures" / "cfname_mini.def"


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _seed_cf_concepts(conn: psycopg.Connection, names: list[str]) -> None:
    """Crée le scheme `grandeurs-cf` et y attache les concepts demandés."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.scheme (uri, code, title, status)
            VALUES ('https://w3id.org/nephos/vocab/grandeurs-cf',
                    'grandeurs-cf', 'CF Standard Names (test)', 'published')
            RETURNING scheme_id
            """
        )
        row = cur.fetchone()
        assert row is not None
        scheme_id = int(row[0])
        for name in names:
            cur.execute(
                """
                INSERT INTO vocab.concept (uri, notation, status)
                VALUES (%s, %s, 'approved')
                RETURNING concept_id
                """,
                (f"https://w3id.org/nephos/vocab/grandeurs-cf/{name}", name),
            )
            row = cur.fetchone()
            assert row is not None
            cur.execute(
                "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
                (int(row[0]), scheme_id),
            )


def _count(conn: psycopg.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


class TestECMWFMappingsImport:
    def test_creates_close_match_for_each_known_cf_name(self, db_conn: psycopg.Connection) -> None:
        _seed_cf_concepts(
            db_conn,
            ["air_temperature", "eastward_wind", "northward_wind", "surface_air_pressure"],
        )
        result = ImportRunner(ECMWFMappingsImporter(source=CFNAME_FIXTURE)).run()

        # 5 entrées dans la fixture, 4 matchent, 1 sans concept Nephos.
        assert result.nb_entites == 5
        assert result.nb_creations == 4
        assert "1 CF name" in (result.notes or "")

        # Mappings closeMatch effectivement insérés vers les URLs ECMWF.
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vocab.concept_mapping "
                "WHERE mapping_relation = 'closeMatch' "
                "AND target_uri LIKE %s",
                ("https://codes.ecmwf.int/grib/param-db/%",),
            )
            row = cur.fetchone()
            assert row is not None
            assert int(row[0]) == 4

    def test_idempotent_rerun(self, db_conn: psycopg.Connection) -> None:
        _seed_cf_concepts(db_conn, ["air_temperature", "eastward_wind"])
        ImportRunner(ECMWFMappingsImporter(source=CFNAME_FIXTURE)).run()
        result2 = ImportRunner(ECMWFMappingsImporter(source=CFNAME_FIXTURE)).run()
        # Aucune création au 2e run, tout est skipped.
        assert result2.nb_creations == 0
        assert result2.nb_skipped == 2

    def test_unmatched_when_no_cf_concept_in_base(self, db_conn: psycopg.Connection) -> None:
        # Aucun concept CF en base → 5 unmatched, 0 creations.
        result = ImportRunner(ECMWFMappingsImporter(source=CFNAME_FIXTURE)).run()
        assert result.nb_creations == 0
        assert "5 CF name" in (result.notes or "")


class TestParseCFNameDef:
    def test_parses_simple_entry(self) -> None:
        text = (
            "#Temperature\n"
            "'air_temperature' = {\n"
            "\t discipline = 0 ;\n"
            "\t parameterCategory = 0 ;\n"
            "\t parameterNumber = 0 ;\n"
            "\t}\n"
        )
        entries = list(_iter_entries(text))
        assert len(entries) == 1
        e = entries[0]
        assert e.cf_name == "air_temperature"
        assert (e.discipline, e.parameter_category, e.parameter_number) == (0, 0, 0)
        assert e.extra == ()

    def test_parses_extra_qualifiers(self) -> None:
        text = (
            "'surface_air_pressure' = {\n"
            "\t discipline = 0 ;\n"
            "\t parameterCategory = 3 ;\n"
            "\t parameterNumber = 0 ;\n"
            "\t typeOfFirstFixedSurface = 1 ;\n"
            "\t}\n"
        )
        entries = list(_iter_entries(text))
        assert entries[0].extra == (("typeOfFirstFixedSurface", 1),)

    def test_skips_entry_without_required_keys(self) -> None:
        text = "'incomplete' = {\n\t discipline = 0 ;\n\t}\n"
        assert list(_iter_entries(text)) == []

    def test_url_format(self) -> None:
        url = _build_ecmwf_url(0, 0, 0)
        assert url == (
            "https://codes.ecmwf.int/grib/param-db/"
            "?discipline=0&parameterCategory=0&parameterNumber=0"
        )
