"""Export SKOS depuis Postgres vers RDF (Turtle / RDF-XML / JSON-LD).

Construit un graphe RDF cohérent avec le modèle SKOS Core et le
sérialise dans le format demandé (Turtle par défaut). L'export honore :

- ADR 0001 : modèle SKOS Core, multi-hiérarchie, mappings cross-source.
- ADR 0003 : URI canoniques `https://w3id.org/nephos/vocab/...`.
- ADR 0004 : labels multilingues préservés.
- ADR 0005 : `dcterms:license` sur le scheme (CC-BY 4.0), `dcterms:source`
  sur chaque concept ayant un `import_source_id` (préservation de
  l'attribution amont).
- ADR 0010 : aucun stockage modifié par l'export — lecture seule.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from typing import Literal

import psycopg
import rdflib
from rdflib import Literal as RdfLiteral
from rdflib import URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

from nephos.logging import get_logger

logger = get_logger(__name__)

NEPHOS_NS = rdflib.Namespace("https://w3id.org/nephos/vocab/")
QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")
CC_BY_4 = URIRef("https://creativecommons.org/licenses/by/4.0/")

ExportFormat = Literal["turtle", "xml", "json-ld", "n3"]


@dataclasses.dataclass(slots=True)
class ExportResult:
    """Statistiques d'un export RDF."""

    format: ExportFormat
    nb_concepts: int
    nb_schemes: int
    nb_labels: int
    nb_notes: int
    nb_relations: int
    nb_mappings: int
    payload: str  # contenu sérialisé


class SKOSExporter:
    """Construit et sérialise le graphe RDF d'un sous-ensemble du référentiel."""

    def __init__(
        self,
        *,
        statuses: Iterable[str] = ("approved", "published"),
    ) -> None:
        self._statuses = tuple(statuses)

    def build_graph(
        self,
        conn: psycopg.Connection,
        scheme_code: str | None = None,
    ) -> tuple[rdflib.Graph, dict[str, int]]:
        """Construit le graphe RDF et retourne (graph, stats)."""
        graph = rdflib.Graph()
        graph.bind("skos", SKOS)
        graph.bind("dcterms", DCTERMS)
        graph.bind("rdfs", RDFS)
        graph.bind("owl", OWL)
        graph.bind("qudt", QUDT)

        scheme_uris = self._add_schemes(conn, graph, scheme_code)
        concept_uris = self._add_concepts(conn, graph, scheme_code)
        nb_labels = self._add_labels(conn, graph, concept_uris)
        nb_notes = self._add_notes(conn, graph, concept_uris)
        self._add_in_scheme(conn, graph, concept_uris, scheme_uris)
        nb_relations = self._add_semantic_relations(conn, graph, concept_uris)
        nb_mappings = self._add_external_mappings(conn, graph, concept_uris)

        stats = {
            "nb_schemes": len(scheme_uris),
            "nb_concepts": len(concept_uris),
            "nb_labels": nb_labels,
            "nb_notes": nb_notes,
            "nb_relations": nb_relations,
            "nb_mappings": nb_mappings,
        }
        return graph, stats

    def export(
        self,
        conn: psycopg.Connection,
        *,
        scheme_code: str | None = None,
        fmt: ExportFormat = "turtle",
    ) -> ExportResult:
        graph, stats = self.build_graph(conn, scheme_code=scheme_code)
        rdflib_format = "turtle" if fmt == "turtle" else fmt
        # `graph.serialize` retourne `str` selon les stubs rdflib modernes.
        payload = str(graph.serialize(format=rdflib_format))
        return ExportResult(
            format=fmt,
            nb_concepts=stats["nb_concepts"],
            nb_schemes=stats["nb_schemes"],
            nb_labels=stats["nb_labels"],
            nb_notes=stats["nb_notes"],
            nb_relations=stats["nb_relations"],
            nb_mappings=stats["nb_mappings"],
            payload=payload,
        )

    # ------------------------------------------------------------------
    # Helpers privés — chargement par étapes
    # ------------------------------------------------------------------

    def _add_schemes(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        scheme_code: str | None,
    ) -> dict[int, URIRef]:
        with conn.cursor() as cur:
            if scheme_code is None:
                cur.execute(
                    "SELECT scheme_id, uri, code, title, description, default_license "
                    "FROM vocab.scheme"
                )
            else:
                cur.execute(
                    "SELECT scheme_id, uri, code, title, description, default_license "
                    "FROM vocab.scheme WHERE code = %s",
                    (scheme_code,),
                )
            rows = cur.fetchall()

        result: dict[int, URIRef] = {}
        for scheme_id, uri, _code, title, description, license_str in rows:
            scheme_uri = URIRef(uri)
            graph.add((scheme_uri, RDF.type, SKOS.ConceptScheme))
            if title:
                graph.add((scheme_uri, DCTERMS.title, RdfLiteral(title, lang="fr")))
            if description:
                graph.add((scheme_uri, DCTERMS.description, RdfLiteral(description, lang="fr")))
            graph.add((scheme_uri, DCTERMS.license, _license_uri(license_str)))
            result[int(scheme_id)] = scheme_uri
        return result

    def _add_concepts(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        scheme_code: str | None,
    ) -> dict[int, URIRef]:
        base_sql = (
            "SELECT c.concept_id, c.uri, c.notation, c.import_source_id "
            "FROM vocab.concept c WHERE c.status = ANY(%s) "
        )
        params: tuple[object, ...] = (list(self._statuses),)
        if scheme_code is not None:
            base_sql += (
                "AND EXISTS (SELECT 1 FROM vocab.concept_in_scheme cis "
                "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
                "WHERE cis.concept_id = c.concept_id AND s.code = %s) "
            )
            params = (list(self._statuses), scheme_code)

        with conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()

            # Récupère les codes des sources d'import pour `dcterms:source`.
            cur.execute("SELECT import_source_id, url FROM gov.import_sources")
            source_urls = {int(sid): url for sid, url in cur.fetchall() if url}

        result: dict[int, URIRef] = {}
        for concept_id, uri, notation, import_source_id in rows:
            concept_uri = URIRef(uri)
            graph.add((concept_uri, RDF.type, SKOS.Concept))
            graph.add((concept_uri, SKOS.notation, RdfLiteral(notation)))
            if import_source_id is not None:
                source_url = source_urls.get(int(import_source_id))
                if source_url:
                    graph.add((concept_uri, DCTERMS.source, URIRef(source_url)))
            result[int(concept_id)] = concept_uri
        return result

    def _add_labels(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        concept_uris: dict[int, URIRef],
    ) -> int:
        if not concept_uris:
            return 0
        kind_predicate = {
            "pref": SKOS.prefLabel,
            "alt": SKOS.altLabel,
            "hidden": SKOS.hiddenLabel,
        }
        ids = list(concept_uris.keys())
        nb = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT concept_id, lang, kind, value FROM vocab.concept_label "
                "WHERE concept_id = ANY(%s)",
                (ids,),
            )
            for concept_id, lang, kind, value in cur.fetchall():
                pred = kind_predicate.get(str(kind))
                target = concept_uris.get(int(concept_id))
                if pred is None or target is None:
                    continue
                graph.add((target, pred, RdfLiteral(value, lang=lang)))
                nb += 1
        return nb

    def _add_notes(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        concept_uris: dict[int, URIRef],
    ) -> int:
        if not concept_uris:
            return 0
        kind_predicate = {
            "definition": SKOS.definition,
            "scopeNote": SKOS.scopeNote,
            "example": SKOS.example,
            "historyNote": SKOS.historyNote,
            "editorialNote": SKOS.editorialNote,
            "changeNote": SKOS.changeNote,
        }
        ids = list(concept_uris.keys())
        nb = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT concept_id, lang, kind, value FROM vocab.concept_note "
                "WHERE concept_id = ANY(%s)",
                (ids,),
            )
            for concept_id, lang, kind, value in cur.fetchall():
                pred = kind_predicate.get(str(kind))
                target = concept_uris.get(int(concept_id))
                if pred is None or target is None:
                    continue
                graph.add((target, pred, RdfLiteral(value, lang=lang)))
                nb += 1
        return nb

    def _add_in_scheme(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        concept_uris: dict[int, URIRef],
        scheme_uris: dict[int, URIRef],
    ) -> None:
        if not concept_uris or not scheme_uris:
            return
        with conn.cursor() as cur:
            cur.execute(
                "SELECT concept_id, scheme_id, is_top_concept FROM vocab.concept_in_scheme "
                "WHERE concept_id = ANY(%s) AND scheme_id = ANY(%s)",
                (list(concept_uris.keys()), list(scheme_uris.keys())),
            )
            for concept_id, scheme_id, is_top in cur.fetchall():
                concept_uri = concept_uris[int(concept_id)]
                scheme_uri = scheme_uris[int(scheme_id)]
                graph.add((concept_uri, SKOS.inScheme, scheme_uri))
                if bool(is_top):
                    graph.add((scheme_uri, SKOS.hasTopConcept, concept_uri))
                    graph.add((concept_uri, SKOS.topConceptOf, scheme_uri))

    def _add_semantic_relations(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        concept_uris: dict[int, URIRef],
    ) -> int:
        if not concept_uris:
            return 0
        relation_predicate = {
            "broader": SKOS.broader,
            "narrower": SKOS.narrower,
            "related": SKOS.related,
            "exactMatch": SKOS.exactMatch,
            "closeMatch": SKOS.closeMatch,
            "broadMatch": SKOS.broadMatch,
            "narrowMatch": SKOS.narrowMatch,
            "relatedMatch": SKOS.relatedMatch,
        }
        ids = list(concept_uris.keys())
        nb = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_concept_id, target_concept_id, relation "
                "FROM vocab.concept_semantic_relation "
                "WHERE source_concept_id = ANY(%s) AND target_concept_id = ANY(%s)",
                (ids, ids),
            )
            for src, tgt, rel in cur.fetchall():
                pred = relation_predicate.get(str(rel))
                src_uri = concept_uris.get(int(src))
                tgt_uri = concept_uris.get(int(tgt))
                if pred is None or src_uri is None or tgt_uri is None:
                    continue
                graph.add((src_uri, pred, tgt_uri))
                nb += 1
        return nb

    def _add_external_mappings(
        self,
        conn: psycopg.Connection,
        graph: rdflib.Graph,
        concept_uris: dict[int, URIRef],
    ) -> int:
        if not concept_uris:
            return 0
        relation_predicate = {
            "exactMatch": SKOS.exactMatch,
            "closeMatch": SKOS.closeMatch,
            "broadMatch": SKOS.broadMatch,
            "narrowMatch": SKOS.narrowMatch,
            "relatedMatch": SKOS.relatedMatch,
        }
        ids = list(concept_uris.keys())
        nb = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT concept_id, target_uri, mapping_relation "
                "FROM vocab.concept_mapping WHERE concept_id = ANY(%s)",
                (ids,),
            )
            for concept_id, target_uri, rel in cur.fetchall():
                pred = relation_predicate.get(str(rel))
                src_uri = concept_uris.get(int(concept_id))
                if pred is None or src_uri is None:
                    continue
                graph.add((src_uri, pred, URIRef(target_uri)))
                nb += 1
        return nb


def _license_uri(license_str: str | None) -> URIRef:
    """Mappe le code de licence stocké en base vers son URI canonique."""
    code = (license_str or "").upper()
    if code in {"CC-BY-4.0", "CC BY 4.0", "CCBY4.0"}:
        return CC_BY_4
    # Par défaut, on déclare CC-BY 4.0 conformément à ADR 0005 (données
    # originales Nephos). Les sources amont ont leurs propres URIs
    # référencées via dcterms:source au niveau de chaque concept.
    return CC_BY_4
