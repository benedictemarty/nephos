"""Tests d'intégration de `nephos.exporters.SKOSExporter` (E6-01).

Vérifie que l'export Turtle produit un graphe RDF cohérent avec
le modèle SKOS Core.
"""

from __future__ import annotations

import os

import psycopg
import pytest
import rdflib
from rdflib.namespace import DCTERMS, SKOS

from nephos.exporters import SKOSExporter

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _create_scheme(conn: psycopg.Connection, code: str, uri: str, title: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.scheme (uri, code, title, status) "
            "VALUES (%s, %s, %s, 'published') RETURNING scheme_id",
            (uri, code, title),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


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


def _add_label(conn: psycopg.Connection, cid: int, lang: str, kind: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
            "VALUES (%s, %s, %s, %s)",
            (cid, lang, kind, value),
        )


def _add_in_scheme(conn: psycopg.Connection, cid: int, sid: int, is_top: bool = False) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id, is_top_concept) "
            "VALUES (%s, %s, %s)",
            (cid, sid, is_top),
        )


def _parse_turtle(payload: str) -> rdflib.Graph:
    graph = rdflib.Graph()
    graph.parse(data=payload, format="turtle")
    return graph


class TestSKOSExporter:
    def test_export_basic_concept(self, db_conn: psycopg.Connection) -> None:
        sid = _create_scheme(db_conn, "test", "https://w3id.org/nephos/vocab/test", "Test Scheme")
        cid = _create_concept(
            db_conn,
            "https://w3id.org/nephos/vocab/test/concept_a",
            "concept_a",
            status="published",
        )
        _add_label(db_conn, cid, "fr", "pref", "Concept A")
        _add_label(db_conn, cid, "en", "pref", "Concept A (en)")
        _add_label(db_conn, cid, "fr", "alt", "alias-a")
        _add_in_scheme(db_conn, cid, sid, is_top=True)

        result = SKOSExporter().export(db_conn)

        assert result.nb_schemes == 1
        assert result.nb_concepts == 1
        assert result.nb_labels == 3  # 2 pref + 1 alt

        graph = _parse_turtle(result.payload)
        concept_uri = rdflib.URIRef("https://w3id.org/nephos/vocab/test/concept_a")
        scheme_uri = rdflib.URIRef("https://w3id.org/nephos/vocab/test")

        # Triplets attendus
        assert (concept_uri, rdflib.RDF.type, SKOS.Concept) in graph
        assert (scheme_uri, rdflib.RDF.type, SKOS.ConceptScheme) in graph
        assert (concept_uri, SKOS.inScheme, scheme_uri) in graph
        assert (concept_uri, SKOS.topConceptOf, scheme_uri) in graph
        assert (scheme_uri, SKOS.hasTopConcept, concept_uri) in graph

        # Labels multilingues
        labels_fr = list(graph.objects(concept_uri, SKOS.prefLabel))
        assert any(isinstance(le, rdflib.Literal) and le.language == "fr" for le in labels_fr)
        assert any(isinstance(le, rdflib.Literal) and le.language == "en" for le in labels_fr)

        # Licence sur le scheme (CC-BY 4.0 selon ADR 0005)
        licenses = list(graph.objects(scheme_uri, DCTERMS.license))
        assert rdflib.URIRef("https://creativecommons.org/licenses/by/4.0/") in licenses

    def test_filter_by_scheme(self, db_conn: psycopg.Connection) -> None:
        sa = _create_scheme(db_conn, "a", "https://w3id.org/nephos/vocab/a", "A")
        sb = _create_scheme(db_conn, "b", "https://w3id.org/nephos/vocab/b", "B")
        ca = _create_concept(db_conn, "https://w3id.org/nephos/vocab/a/x", "x")
        cb = _create_concept(db_conn, "https://w3id.org/nephos/vocab/b/y", "y")
        _add_label(db_conn, ca, "en", "pref", "X")
        _add_label(db_conn, cb, "en", "pref", "Y")
        _add_in_scheme(db_conn, ca, sa)
        _add_in_scheme(db_conn, cb, sb)

        result = SKOSExporter().export(db_conn, scheme_code="a")
        assert result.nb_schemes == 1
        assert result.nb_concepts == 1

    def test_export_includes_external_mapping(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(db_conn, "https://w3id.org/nephos/vocab/test/x", "x")
        _add_label(db_conn, cid, "en", "pref", "X")
        with db_conn.cursor() as cur:
            cur.execute("SELECT import_source_id FROM gov.import_sources WHERE code = 'CF'")
            row = cur.fetchone()
            assert row is not None
            cf_id = int(row[0])
            cur.execute(
                "INSERT INTO vocab.concept_mapping "
                "(concept_id, target_source_id, target_uri, mapping_relation) "
                "VALUES (%s, %s, %s, 'exactMatch')",
                (cid, cf_id, "https://cfconventions.org/foo"),
            )

        result = SKOSExporter().export(db_conn)
        assert result.nb_mappings == 1
        graph = _parse_turtle(result.payload)
        assert (
            rdflib.URIRef("https://w3id.org/nephos/vocab/test/x"),
            SKOS.exactMatch,
            rdflib.URIRef("https://cfconventions.org/foo"),
        ) in graph

    def test_export_internal_broader_relation(self, db_conn: psycopg.Connection) -> None:
        parent = _create_concept(db_conn, "https://w3id.org/nephos/vocab/test/parent", "parent")
        child = _create_concept(db_conn, "https://w3id.org/nephos/vocab/test/child", "child")
        _add_label(db_conn, parent, "en", "pref", "Parent")
        _add_label(db_conn, child, "en", "pref", "Child")
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept_semantic_relation "
                "(source_concept_id, target_concept_id, relation) "
                "VALUES (%s, %s, 'broader')",
                (child, parent),
            )

        result = SKOSExporter().export(db_conn)
        assert result.nb_relations == 1
        graph = _parse_turtle(result.payload)
        assert (
            rdflib.URIRef("https://w3id.org/nephos/vocab/test/child"),
            SKOS.broader,
            rdflib.URIRef("https://w3id.org/nephos/vocab/test/parent"),
        ) in graph

    def test_export_in_multiple_formats(self, db_conn: psycopg.Connection) -> None:
        cid = _create_concept(db_conn, "https://w3id.org/nephos/vocab/test/x", "x")
        _add_label(db_conn, cid, "en", "pref", "X")

        for fmt in ("turtle", "xml", "json-ld"):
            result = SKOSExporter().export(db_conn, fmt=fmt)  # type: ignore[arg-type]
            assert result.nb_concepts == 1
            assert len(result.payload) > 0

    def test_empty_export_returns_minimal_graph(self, db_conn: psycopg.Connection) -> None:
        result = SKOSExporter().export(db_conn)
        assert result.nb_concepts == 0
        # Le payload doit rester du Turtle valide même vide.
        graph = _parse_turtle(result.payload)
        assert len(graph) == 0
