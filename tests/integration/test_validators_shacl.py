"""Tests d'intégration de `nephos.validators.SHACLValidator` (E5-01).

Vérifie le bout-en-bout : concepts en base → graphe RDF → pyshacl
→ rapport structuré.
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


def _add_pref_label(conn: psycopg.Connection, concept_id: int, lang: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
            "VALUES (%s, %s, 'pref', %s)",
            (concept_id, lang, value),
        )


class TestSHACLValidator:
    def test_valid_concepts_conform(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/temperature_air",
            "temperature_air",
        )
        _add_pref_label(db_conn, cid, "en", "Air temperature")

        validator = SHACLValidator()
        report = validator.validate(db_conn)

        assert report.concepts_validated == 1
        assert report.conforms, report.raw_report

    def test_concept_without_pref_label_violates(self, db_conn: psycopg.Connection) -> None:
        _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/orphan",
            "orphan",
        )

        report = SHACLValidator().validate(db_conn)
        assert not report.conforms
        assert report.violations >= 1
        assert "prefLabel" in report.raw_report

    def test_strict_mode_requires_fr_and_en(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/grandeurs/half_translated",
            "half_translated",
        )
        _add_pref_label(db_conn, cid, "en", "Half translated")
        # Pas de FR → violation en mode strict.

        report_lax = SHACLValidator(treat_as_published=False).validate(db_conn)
        assert report_lax.conforms

        report_strict = SHACLValidator(treat_as_published=True).validate(db_conn)
        assert not report_strict.conforms
        assert "fr" in report_strict.raw_report.lower()

    def test_filter_by_scheme(self, db_conn: psycopg.Connection) -> None:
        # Crée 2 schemes et un concept dans chacun
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.scheme (uri, code, title) "
                "VALUES (%s, 'a', 'A') RETURNING scheme_id",
                ("https://w3id.org/nephos/vocab/a",),
            )
            row = cur.fetchone()
            assert row is not None
            scheme_a = int(row[0])
            cur.execute(
                "INSERT INTO vocab.scheme (uri, code, title) "
                "VALUES (%s, 'b', 'B') RETURNING scheme_id",
                ("https://w3id.org/nephos/vocab/b",),
            )
            row = cur.fetchone()
            assert row is not None
            scheme_b = int(row[0])

        cid_a = _create_concept(db_conn, "https://w3id.org/nephos/vocab/a/x", "x")
        cid_b = _create_concept(db_conn, "https://w3id.org/nephos/vocab/b/y", "y")
        _add_pref_label(db_conn, cid_a, "en", "X")
        _add_pref_label(db_conn, cid_b, "en", "Y")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES "
                "(%s, %s), (%s, %s)",
                (cid_a, scheme_a, cid_b, scheme_b),
            )

        # Validation limitée au scheme 'a' → 1 concept seulement.
        report = SHACLValidator().validate(db_conn, scheme_code="a")
        assert report.concepts_validated == 1

    def test_no_concepts_returns_conforms(self, db_conn: psycopg.Connection) -> None:
        report = SHACLValidator().validate(db_conn)
        assert report.concepts_validated == 0
        assert report.conforms
