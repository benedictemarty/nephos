"""Tests d'intégration des shapes SHACL Nephos métier (E5-02).

Vérifie les invariants spécifiques au modèle Nephos qui vont au-delà
de SKOS Core : concept mesurable typé, concept numérique avec unité,
attribution requise sur publié, alerte si orphelin de scheme.
"""

from __future__ import annotations

import os

import psycopg
import pytest

from nephos.validators import SHACLValidator

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _create_concept(
    conn: psycopg.Connection,
    uri: str,
    notation: str,
    status: str = "approved",
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) VALUES (%s, %s, %s) "
            "RETURNING concept_id",
            (uri, notation, status),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _add_pref_label(conn: psycopg.Connection, cid: int, lang: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
            "VALUES (%s, %s, 'pref', %s)",
            (cid, lang, value),
        )


def _create_scheme(conn: psycopg.Connection, code: str, uri: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.scheme (uri, code, title) "
            "VALUES (%s, %s, %s) RETURNING scheme_id",
            (uri, code, f"Test {code}"),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _add_in_scheme(conn: psycopg.Connection, cid: int, sid: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) " "VALUES (%s, %s)",
            (cid, sid),
        )


class TestNephosMetierShapes:
    def test_numeric_concept_without_unit_emits_warning(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp", "temp")
        _add_pref_label(db_conn, cid, "en", "Temperature")
        sid = _create_scheme(db_conn, "grandeurs", "https://w3id.org/nephos/vocab/grandeurs")
        _add_in_scheme(db_conn, cid, sid)
        # concept_physical scalar SANS unité → NumericMeasurableShape Warning.
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_physical (concept_id, value_type) "
                "VALUES (%s, 'scalar')",
                (cid,),
            )

        report = SHACLValidator().validate(db_conn)
        assert report.warnings >= 1, report.raw_report
        # Le rapport mentionne explicitement l'unité manquante.
        assert "unité" in report.raw_report or "hasUnit" in report.raw_report

    def test_numeric_concept_with_unit_passes(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(db_conn, "https://w3id.org/nephos/vocab/grandeurs/temp", "temp")
        _add_pref_label(db_conn, cid, "en", "Temperature")
        sid = _create_scheme(db_conn, "grandeurs", "https://w3id.org/nephos/vocab/grandeurs")
        _add_in_scheme(db_conn, cid, sid)
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.unite (symbole, nom, est_si_canonique, status) "
                "VALUES ('K', 'Kelvin', TRUE, 'published') RETURNING unite_id"
            )
            row = cur.fetchone()
            assert row is not None
            unit_id = int(row[0])
            cur.execute(
                "INSERT INTO vocab.concept_physical "
                "(concept_id, value_type, unit_canonical_id) "
                "VALUES (%s, 'scalar', %s)",
                (cid, unit_id),
            )

        report = SHACLValidator().validate(db_conn)
        assert report.violations == 0
        # Le warning sur l'unité manquante n'est pas levé puisque l'unité existe.
        assert "hasUnit" not in report.raw_report

    def test_orphan_concept_emits_warning(self, db_conn: psycopg.Connection) -> None:
        # Concept sans concept_in_scheme → InSchemeShape Warning.
        cid = _create_concept(db_conn, "https://w3id.org/nephos/vocab/grandeurs/orphan", "orphan")
        _add_pref_label(db_conn, cid, "en", "Orphan")
        report = SHACLValidator().validate(db_conn)
        assert report.warnings >= 1
        assert "ConceptScheme" in report.raw_report or "scheme" in report.raw_report.lower()

    def test_concept_in_scheme_no_warning(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(db_conn, "https://w3id.org/nephos/vocab/grandeurs/x", "x")
        _add_pref_label(db_conn, cid, "en", "X")
        sid = _create_scheme(db_conn, "grandeurs", "https://w3id.org/nephos/vocab/grandeurs")
        _add_in_scheme(db_conn, cid, sid)
        report = SHACLValidator().validate(db_conn)
        assert report.warnings == 0
        assert report.violations == 0
