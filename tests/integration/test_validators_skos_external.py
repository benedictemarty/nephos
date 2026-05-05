"""Tests d'intégration de `SkosExternalValidator` (E6-03)."""

from __future__ import annotations

import os

import psycopg
import pytest

from nephos.validators.skos_external import (
    SkosExternalValidator,
    _classify,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _seed_scheme(conn: psycopg.Connection, code: str = "test") -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.scheme (uri, code, title, status) "
            "VALUES (%s, %s, %s, 'published') RETURNING scheme_id",
            (f"https://w3id.org/nephos/vocab/{code}", code, f"Test {code}"),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _add_concept(
    conn: psycopg.Connection, scheme_id: int, notation: str, label_en: str = ""
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) "
            "VALUES (%s, %s, 'published') RETURNING concept_id",
            (f"https://w3id.org/nephos/vocab/test/{notation}", notation),
        )
        row = cur.fetchone()
        assert row is not None
        cid = int(row[0])
        cur.execute(
            "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
            (cid, scheme_id),
        )
        if label_en:
            cur.execute(
                "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                "VALUES (%s, 'en', 'pref', %s)",
                (cid, label_en),
            )
    return cid


class TestSkosExternalValidator:
    def test_clean_export_conforms(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _seed_scheme(db_conn)
        _add_concept(db_conn, scheme_id, "alpha", "Alpha")
        _add_concept(db_conn, scheme_id, "beta", "Beta")

        report = SkosExternalValidator(scheme_code="test").validate(db_conn)
        assert report.conforms is True
        assert report.nb_concepts == 2
        assert report.issues == []

    def test_hierarchy_cycle_detected(self, db_conn: psycopg.Connection) -> None:
        """Cycle broader entre 2 concepts → check `hierarchy_cycles` doit signaler."""
        scheme_id = _seed_scheme(db_conn)
        a = _add_concept(db_conn, scheme_id, "a", "A")
        b = _add_concept(db_conn, scheme_id, "b", "B")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_semantic_relation "
                "(source_concept_id, target_concept_id, relation) "
                "VALUES (%s, %s, 'broader'), (%s, %s, 'broader')",
                (a, b, b, a),
            )

        report = SkosExternalValidator(scheme_code="test").validate(db_conn)
        assert report.conforms is False
        assert any(i.check == "hierarchy_cycles" for i in report.issues)

    def test_disjoint_broader_related_detected(self, db_conn: psycopg.Connection) -> None:
        """SKOS S27 : un même couple ne doit pas être à la fois broader ET related."""
        scheme_id = _seed_scheme(db_conn)
        a = _add_concept(db_conn, scheme_id, "x", "X")
        b = _add_concept(db_conn, scheme_id, "y", "Y")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_semantic_relation "
                "(source_concept_id, target_concept_id, relation) "
                "VALUES (%s, %s, 'broader'), (%s, %s, 'related')",
                (a, b, a, b),
            )

        report = SkosExternalValidator(scheme_code="test").validate(db_conn)
        assert report.conforms is False
        assert any(i.check == "disjoint_relations" for i in report.issues)


class TestClassify:
    def test_known_patterns(self) -> None:
        assert _classify("Hierarchy cycle detected at b -> a") == "hierarchy_cycles"
        assert (
            _classify("Concepts X and Y connected by both skos:broader and skos:related")
            == "disjoint_relations"
        )
        assert _classify("Resource X has more than one prefLabel@en") == "preflabel_uniqueness"
        assert _classify("Redundant hierarchical relationship") == "hierarchical_redundancy"
        assert _classify("Same label found in two concepts") == "label_overlap"

    def test_unknown_message_falls_back(self) -> None:
        assert _classify("Some other warning") == "unknown"


class TestReportShape:
    def test_by_check_aggregates_counts(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _seed_scheme(db_conn)
        a = _add_concept(db_conn, scheme_id, "p", "P")
        b = _add_concept(db_conn, scheme_id, "q", "Q")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_semantic_relation "
                "(source_concept_id, target_concept_id, relation) "
                "VALUES (%s, %s, 'broader'), (%s, %s, 'broader')",
                (a, b, b, a),
            )
        report = SkosExternalValidator(scheme_code="test").validate(db_conn)
        counts = report.by_check()
        assert counts.get("hierarchy_cycles", 0) >= 1
