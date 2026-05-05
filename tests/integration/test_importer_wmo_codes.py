"""Tests d'intégration de `WMOCodesImporter` (E4-05)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from nephos.etl.runner import ImportRunner
from nephos.importers.wmo_codes import WMO_PRESETS, WMOCodesImporter

pytestmark = pytest.mark.integration

WMO_FIXTURE = Path(__file__).parent / "fixtures" / "wmo_bufr_0_02_001_mini.ttl"


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


def _build_importer() -> WMOCodesImporter:
    return WMOCodesImporter(
        register_url=WMO_FIXTURE,
        scheme_code="wmo-bufr-0-02-001",
        scheme_title="WMO BUFR 0-02-001 — Type of station (test)",
    )


class TestWMOCodesImport:
    def test_import_creates_concepts_scheme_and_mappings(self, db_conn: psycopg.Connection) -> None:
        result = ImportRunner(_build_importer()).run()

        # Le register a 4 membres, version = dct:modified.
        assert result.nb_entites == 4
        assert result.nb_creations == 4
        assert "2014-09-03" in result.version

        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.scheme WHERE code = 'wmo-bufr-0-02-001'",
            )
            == 1
        )
        # 4 concepts avec notations 0..3.
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept WHERE notation IN ('0','1','2','3') "
                "AND uri LIKE '%/wmo-bufr-0-02-001/%'",
            )
            == 4
        )
        # prefLabel@en pour chaque concept.
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept_label cl "
                "JOIN vocab.concept c ON c.concept_id = cl.concept_id "
                "WHERE cl.lang='en' AND cl.kind='pref' "
                "AND c.uri LIKE '%/wmo-bufr-0-02-001/%'",
            )
            == 4
        )
        # exactMatch vers les URIs WMO d'origine.
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept_mapping cm "
                "JOIN vocab.concept c ON c.concept_id = cm.concept_id "
                "WHERE cm.mapping_relation = 'exactMatch' "
                "AND cm.target_uri LIKE 'http://codes.wmo.int/bufr4/codeflag/0-02-001/%'",
            )
            == 4
        )

    def test_idempotent_rerun(self, db_conn: psycopg.Connection) -> None:
        ImportRunner(_build_importer()).run()
        result2 = ImportRunner(_build_importer()).run()
        assert result2.nb_creations == 0
        assert result2.nb_skipped == 4

    def test_import_source_id_propagated(self, db_conn: psycopg.Connection) -> None:
        ImportRunner(_build_importer()).run()
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM vocab.concept c "
                "JOIN gov.import_sources s ON s.import_source_id = c.import_source_id "
                "WHERE s.code = 'WMO_CODES'"
            )
            row = cur.fetchone()
            assert row is not None
            assert int(row[0]) == 4


class TestWMOPresets:
    def test_preset_keys_are_well_formed(self) -> None:
        assert "bufr-0-02-001" in WMO_PRESETS
        for key, preset in WMO_PRESETS.items():
            assert preset.key == key
            assert preset.register_url.startswith("https://codes.wmo.int/")
            assert preset.scheme_code.startswith("wmo-")

    def test_from_preset_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Preset WMO inconnu"):
            WMOCodesImporter.from_preset("inexistant")
