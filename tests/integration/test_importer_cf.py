"""Tests d'intégration de `CFStandardNamesImporter` (item E4-02).

Vérifie le bout-en-bout import → SKOS sur une fixture XML CF mini
(4 entrées). Pas d'appel réseau : le `source=` pointe sur un fichier
local versionné dans le repo.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from nephos.etl.runner import ImportRunner, RunOptions
from nephos.importers.cf import CFStandardNamesImporter

pytestmark = pytest.mark.integration

CF_FIXTURE = Path(__file__).parent / "fixtures" / "cf_mini.xml"


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


class TestCFImport:
    def test_import_creates_concepts_with_labels_notes_mappings(
        self, db_conn: psycopg.Connection
    ) -> None:
        importer = CFStandardNamesImporter(source=CF_FIXTURE)
        result = ImportRunner(importer).run()

        assert result.version == "87"
        assert result.nb_entites == 4
        assert result.nb_creations == 4
        assert result.nb_modifications == 0
        assert result.nb_skipped == 0

        # 4 concepts insérés en status 'approved'
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept WHERE status = 'approved'") == 4

        # prefLabel@en humanisé (underscores → espaces)
        assert (
            _scalar(
                db_conn,
                "SELECT value FROM vocab.concept_label "
                "WHERE lang = 'en' AND kind = 'pref' "
                "AND value = %s",
                ("air temperature",),
            )
            == "air temperature"
        )

        # Définition EN posée pour chaque concept ayant une description
        assert (
            _count(db_conn, "SELECT COUNT(*) FROM vocab.concept_note WHERE kind = 'definition'")
            == 4
        )

        # Mapping vers la fiche CF officielle
        target = _scalar(
            db_conn,
            "SELECT target_uri FROM vocab.concept_mapping cm "
            "JOIN vocab.concept c ON c.concept_id = cm.concept_id "
            "WHERE c.notation = %s AND cm.mapping_relation = 'exactMatch'",
            ("air_temperature",),
        )
        assert isinstance(target, str)
        assert target.startswith("https://cfconventions.org/")
        assert target.endswith("#air_temperature")

        # Scheme `grandeurs-cf` créé une seule fois et tous les concepts y sont
        scheme_id = _scalar(
            db_conn, "SELECT scheme_id FROM vocab.scheme WHERE code = 'grandeurs-cf'"
        )
        assert (
            _count(
                db_conn,
                f"SELECT COUNT(*) FROM vocab.concept_in_scheme WHERE scheme_id = {scheme_id}",
            )
            == 4
        )

        # concept_physical : value_type='scalar', cf_standard_name renseigné
        assert (
            _scalar(
                db_conn,
                "SELECT cf_standard_name FROM vocab.concept_physical cp "
                "JOIN vocab.concept c ON c.concept_id = cp.concept_id "
                "WHERE c.notation = %s",
                ("wind_speed",),
            )
            == "wind_speed"
        )

    def test_idempotent_rerun_skips_existing(self, db_conn: psycopg.Connection) -> None:
        importer = CFStandardNamesImporter(source=CF_FIXTURE)
        ImportRunner(importer).run()

        # 2e run : même version → tout skipped
        importer2 = CFStandardNamesImporter(source=CF_FIXTURE)
        result2 = ImportRunner(importer2).run()
        assert result2.nb_creations == 0
        assert result2.nb_skipped == 4

        # Toujours 4 concepts (pas de doublons)
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept") == 4

    def test_dry_run_writes_nothing(self, db_conn: psycopg.Connection) -> None:
        importer = CFStandardNamesImporter(source=CF_FIXTURE)
        result = ImportRunner(importer).run(RunOptions(dry_run=True))
        assert result.nb_entites == 4
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.concept") == 0
        assert _count(db_conn, "SELECT COUNT(*) FROM vocab.scheme") == 0

    def test_canonical_unit_resolved_when_known(self, db_conn: psycopg.Connection) -> None:
        # On précharge l'unité 'K' dans vocab.unite (le seed du schéma ne
        # la fournit pas — c'est volontaire, les unités viendront via QUDT).
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.unite (symbole, nom, est_si_canonique, status) "
                "VALUES ('K', 'Kelvin', TRUE, 'published')"
            )

        ImportRunner(CFStandardNamesImporter(source=CF_FIXTURE)).run()

        # air_temperature doit être lié à l'unité K
        unit_symbole = _scalar(
            db_conn,
            "SELECT u.symbole FROM vocab.concept_physical cp "
            "JOIN vocab.unite u ON u.unite_id = cp.unit_canonical_id "
            "JOIN vocab.concept c ON c.concept_id = cp.concept_id "
            "WHERE c.notation = 'air_temperature'",
        )
        assert unit_symbole == "K"

    def test_local_override_is_protected(self, db_conn: psycopg.Connection) -> None:
        ImportRunner(CFStandardNamesImporter(source=CF_FIXTURE)).run()

        # Modifie un concept localement et marque has_local_override
        with db_conn.cursor() as cur:
            cur.execute(
                "UPDATE vocab.concept SET notation = 'air_temperature_renamed', "
                "has_local_override = TRUE WHERE notation = 'air_temperature'"
            )

        # Re-run d'import : l'override doit être préservé
        result = ImportRunner(CFStandardNamesImporter(source=CF_FIXTURE)).run()
        assert result.nb_overrides_protected == 1

        # La notation locale survit
        assert (
            _count(
                db_conn,
                "SELECT COUNT(*) FROM vocab.concept WHERE notation = 'air_temperature_renamed'",
            )
            == 1
        )

    def test_unknown_unit_records_warning_note(self, db_conn: psycopg.Connection) -> None:
        # Sans 'm s-1' dans vocab.unite, la résolution échoue pour wind_speed
        result = ImportRunner(CFStandardNamesImporter(source=CF_FIXTURE)).run()
        assert result.notes is not None
        assert "non résolue" in result.notes


class TestCFTransform:
    """Tests du transform sans toucher à la base — vérifient le parsing XML."""

    def test_transform_extracts_all_entries(self) -> None:
        importer = CFStandardNamesImporter(source=CF_FIXTURE)
        version = importer.discover_version()
        raw = importer.extract()
        entries = importer.transform(raw)
        assert version == "87"
        assert len(entries) == 4
        notations = {e["notation"] for e in entries}
        assert notations == {
            "air_temperature",
            "surface_air_pressure",
            "wind_speed",
            "thunderstorm_count",
        }

    def test_transform_humanizes_pref_label(self) -> None:
        importer = CFStandardNamesImporter(source=CF_FIXTURE)
        importer.discover_version()
        entries = importer.transform(importer.extract())
        labels = {e["notation"]: e["pref_label_en"] for e in entries}
        assert labels["air_temperature"] == "air temperature"
        assert labels["surface_air_pressure"] == "surface air pressure"
