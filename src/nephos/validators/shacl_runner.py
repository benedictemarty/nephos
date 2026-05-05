"""Validation SHACL des concepts Nephos contre les shapes Core (E5-01).

Construit un graphe RDF à partir des concepts en base, puis exécute
``pyshacl`` pour valider contre `shapes/nephos_skos_core.ttl`.

La construction du graphe est paresseuse côté SQL : on lit les concepts
publiés / approuvés (filtrables par scheme) et on ne charge que les
triplets nécessaires aux shapes (URI, notation, prefLabel, broader).

Voir ADR 0010 (validation comme outil consommateur), ADR 0001/0003/0004
(invariants validés).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import psycopg
import rdflib
from pyshacl import validate as pyshacl_validate
from rdflib import Literal as RdfLiteral
from rdflib import URIRef
from rdflib.namespace import SKOS

from nephos.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SHAPES = Path(__file__).resolve().parents[3] / "shapes" / "nephos_skos_core.ttl"
NEPHOS_NS = rdflib.Namespace("https://w3id.org/nephos/shapes/")

ValidationOutcome = Literal["conforms", "violations"]


@dataclasses.dataclass(slots=True)
class SHACLValidationReport:
    """Résumé exploitable d'une exécution SHACL."""

    outcome: ValidationOutcome
    concepts_validated: int
    violations: int
    warnings: int
    infos: int
    raw_report: str  # rapport texte complet de pyshacl

    @property
    def conforms(self) -> bool:
        return self.outcome == "conforms"


class SHACLValidator:
    """Construit le graphe RDF des concepts et applique les shapes Nephos."""

    def __init__(
        self,
        shapes_path: Path | None = None,
        *,
        statuses: Iterable[str] = ("approved", "published"),
        treat_as_published: bool = False,
    ) -> None:
        """`treat_as_published=True` force la validation comme si les
        concepts étaient en statut ``published`` (impose ADR 0004 :
        prefLabel@fr ET @en).
        """
        self._shapes_path = shapes_path or DEFAULT_SHAPES
        self._statuses = tuple(statuses)
        self._treat_as_published = treat_as_published

    def build_graph(self, conn: psycopg.Connection, scheme_code: str | None = None) -> rdflib.Graph:
        """Charge les concepts depuis la base et construit un graphe RDF."""
        graph = rdflib.Graph()
        published_class = NEPHOS_NS["PublishedConcept"]

        with conn.cursor() as cur:
            scheme_filter = ""
            params: tuple[object, ...] = (list(self._statuses),)
            if scheme_code is not None:
                scheme_filter = (
                    " AND EXISTS (SELECT 1 FROM vocab.concept_in_scheme cis "
                    "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
                    "WHERE cis.concept_id = c.concept_id AND s.code = %s) "
                )
                params = (list(self._statuses), scheme_code)
            # `scheme_filter` est un fragment SQL constant interne — pas
            # de concaténation de valeur utilisateur. La valeur de
            # `scheme_code` passe par un placeholder %s ci-dessous.
            base_sql = (
                "SELECT c.concept_id, c.uri, c.notation, c.status "
                "FROM vocab.concept c WHERE c.status = ANY(%s) "
            )
            sql = base_sql + scheme_filter  # nosec B608 — scheme_filter constant interne
            cur.execute(sql, params)
            concepts = list(cur.fetchall())

        concept_uris: dict[int, URIRef] = {}
        for concept_id, uri, notation, status in concepts:
            uri_ref = URIRef(uri)
            concept_uris[int(concept_id)] = uri_ref
            graph.add((uri_ref, rdflib.RDF.type, SKOS.Concept))
            graph.add((uri_ref, SKOS.notation, RdfLiteral(notation)))
            if self._treat_as_published or status == "published":
                graph.add((uri_ref, rdflib.RDF.type, NEPHOS_NS["PublishedConcept"]))

        if not concept_uris:
            return graph

        ids_tuple = tuple(concept_uris.keys())
        with conn.cursor() as cur:
            cur.execute(
                "SELECT concept_id, lang, value FROM vocab.concept_label "
                "WHERE kind = 'pref' AND concept_id = ANY(%s)",
                (list(ids_tuple),),
            )
            for concept_id, lang, value in cur.fetchall():
                uri_ref = concept_uris.get(int(concept_id))
                if uri_ref is None:
                    continue
                graph.add((uri_ref, SKOS.prefLabel, RdfLiteral(value, lang=lang)))

            cur.execute(
                "SELECT source_concept_id, target_concept_id "
                "FROM vocab.concept_semantic_relation "
                "WHERE relation = 'broader' "
                "AND source_concept_id = ANY(%s) "
                "AND target_concept_id = ANY(%s)",
                (list(ids_tuple), list(ids_tuple)),
            )
            for src, tgt in cur.fetchall():
                src_uri = concept_uris.get(int(src))
                tgt_uri = concept_uris.get(int(tgt))
                if src_uri is not None and tgt_uri is not None:
                    graph.add((src_uri, SKOS.broader, tgt_uri))

        # Marqueur pour le rapport
        _ = published_class
        return graph

    def validate(
        self,
        conn: psycopg.Connection,
        scheme_code: str | None = None,
    ) -> SHACLValidationReport:
        data_graph = self.build_graph(conn, scheme_code=scheme_code)
        nb_concepts = len(set(data_graph.subjects(rdflib.RDF.type, SKOS.Concept)))

        if nb_concepts == 0:
            return SHACLValidationReport(
                outcome="conforms",
                concepts_validated=0,
                violations=0,
                warnings=0,
                infos=0,
                raw_report="Aucun concept à valider.",
            )

        shapes_graph = rdflib.Graph().parse(source=str(self._shapes_path), format="turtle")
        conforms, results_graph, results_text = pyshacl_validate(
            data_graph=data_graph,
            shacl_graph=shapes_graph,
            inference="none",
            advanced=True,
            allow_warnings=True,
            meta_shacl=False,
        )
        violations, warnings_, infos = _count_severities(results_graph)
        return SHACLValidationReport(
            outcome="conforms" if conforms else "violations",
            concepts_validated=nb_concepts,
            violations=violations,
            warnings=warnings_,
            infos=infos,
            raw_report=str(results_text),
        )


def _count_severities(report_graph: rdflib.Graph) -> tuple[int, int, int]:
    """Compte les violations / warnings / infos dans un rapport SHACL."""
    sh = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    violations = 0
    warnings_ = 0
    infos = 0
    for _, _, severity in report_graph.triples((None, sh.resultSeverity, None)):
        if severity == sh.Violation:
            violations += 1
        elif severity == sh.Warning:
            warnings_ += 1
        elif severity == sh.Info:
            infos += 1
    return violations, warnings_, infos
