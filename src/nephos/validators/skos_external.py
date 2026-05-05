"""Validation des exports SKOS par un outil tiers (E6-03).

Au lieu d'un déploiement Skosmos (lourd, JVM) ou d'un appel à
SKOS-Play (en ligne, hors CI), Nephos s'appuie sur la bibliothèque
Python ``skosify`` (MIT, NatLibFi) qui implémente les vérifications
SKOS standard sur un graphe RDF :

- ``hierarchy_cycles`` — cycles dans ``broader`` (SKOS S22 / S27).
- ``disjoint_relations`` — superposition ``broader``/``related``
  (SKOS S27).
- ``preflabel_uniqueness`` — au plus un ``prefLabel`` par langue
  (SKOS S14).
- ``hierarchical_redundancy`` — relations ``broader`` redondantes
  (concept relié à un ancêtre déjà accessible transitivement).
- ``label_overlap`` — un même libellé partagé entre deux concepts
  distincts dans ``prefLabel`` / ``altLabel``.

Le graphe d'entrée est produit via ``SKOSExporter`` (E6-01) — c'est
exactement le même artefact que celui publié vers les consommateurs.
Le validateur n'écrit pas en base, ne « corrige » rien (toutes les
fonctions ``skosify.check`` sont appelées avec ``fix=False``) :
elles loguent les anomalies, qu'on intercepte via un handler
``logging`` dédié.

Voir backlog E6-03.
"""

from __future__ import annotations

import dataclasses
import logging
import re

import psycopg
import rdflib

from nephos.exporters import SKOSExporter
from nephos.logging import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass(slots=True)
class SkosExternalIssue:
    """Une anomalie SKOS détectée par ``skosify``."""

    check: str
    """Nom du check qui l'a produite (ex. ``"hierarchy_cycles"``)."""

    severity: str
    """Niveau de log : ``"warning"`` ou ``"error"``."""

    message: str
    """Texte humain reproduisant le diagnostic skosify."""


@dataclasses.dataclass(slots=True)
class SkosExternalReport:
    """Résultat d'une exécution de ``SkosExternalValidator``."""

    nb_concepts: int
    issues: list[SkosExternalIssue]
    serialization_format: str = "turtle"

    @property
    def conforms(self) -> bool:
        return not self.issues

    def by_check(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.check] = counts.get(issue.check, 0) + 1
        return counts


_CHECK_PATTERNS: dict[str, re.Pattern[str]] = {
    "hierarchy_cycles": re.compile(r"hierarchy\s+cycle", re.IGNORECASE),
    "disjoint_relations": re.compile(
        r"connected\s+by\s+both|both.*broader.*related|disjoint", re.IGNORECASE
    ),
    "preflabel_uniqueness": re.compile(r"more\s+than\s+one\s+preflabel", re.IGNORECASE),
    "hierarchical_redundancy": re.compile(
        r"redundant\s+hierarchical|broader.*ancestor", re.IGNORECASE
    ),
    "label_overlap": re.compile(r"label.*overlap|same.*label", re.IGNORECASE),
}


def _classify(message: str) -> str:
    for check, pattern in _CHECK_PATTERNS.items():
        if pattern.search(message):
            return check
    return "unknown"


class _CapturingHandler(logging.Handler):
    """Handler logging en mémoire pour capturer les warnings skosify."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class SkosExternalValidator:
    """Valide un export SKOS par les checks ``skosify`` standards."""

    def __init__(
        self,
        *,
        scheme_code: str | None = None,
        preflabel_policy: str = "shortest",
    ) -> None:
        self._scheme_code = scheme_code
        self._preflabel_policy = preflabel_policy

    def validate(self, conn: psycopg.Connection) -> SkosExternalReport:
        """Exporte le sous-ensemble cible puis exécute les checks skosify."""
        exporter = SKOSExporter()
        export_result = exporter.export(conn, scheme_code=self._scheme_code, fmt="turtle")
        graph = rdflib.Graph().parse(data=export_result.payload, format="turtle")

        # Import retardé pour conserver `skosify` en dépendance optionnelle.
        from skosify import check as skosify_check

        handler = _CapturingHandler()
        root = logging.getLogger()
        previous_level = root.level
        root.addHandler(handler)
        try:
            root.setLevel(logging.WARNING)
            skosify_check.hierarchy_cycles(graph, fix=False)
            skosify_check.disjoint_relations(graph, fix=False)
            skosify_check.preflabel_uniqueness(graph, policy=self._preflabel_policy)
            skosify_check.hierarchical_redundancy(graph, fix=False)
            skosify_check.label_overlap(graph, fix=False)
        finally:
            root.removeHandler(handler)
            root.setLevel(previous_level)

        issues = [
            SkosExternalIssue(
                check=_classify(record.getMessage()),
                severity=record.levelname.lower(),
                message=record.getMessage(),
            )
            for record in handler.records
        ]
        return SkosExternalReport(
            nb_concepts=export_result.nb_concepts,
            issues=issues,
        )
