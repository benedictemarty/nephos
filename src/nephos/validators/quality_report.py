"""Rapport de qualité automatisé du référentiel (E5-04).

Scanne la base à la recherche d'anomalies structurelles non couvertes
(ou complémentaires) au validateur SHACL Core :

- ``concepts_without_pref_label`` — concept(s) sans aucun ``prefLabel``.
- ``concepts_without_scheme`` — concept(s) jamais rattaché(s) à un scheme.
- ``concepts_self_broader`` — concept dont ``broader`` pointe sur lui-même
  (couvert aussi par SHACL S27, redondant pour confiance double).
- ``duplicate_pref_label_lang`` — concept avec deux ``prefLabel`` dans
  la même langue (viole SKOS S14).
- ``duplicate_notation_in_scheme`` — deux concepts distincts partagent
  la même ``notation`` dans le même scheme (ambiguïté de référence).
- ``duplicate_mappings`` — (concept_id, target_uri) avec plusieurs
  ``mapping_relation`` distinctes (incohérent : un concept ne peut pas
  avoir à la fois ``exactMatch`` et ``closeMatch`` vers la même cible).
- ``missing_lang_labels`` — par scheme et langue cible (`fr`, `en`),
  nombre de concepts publiés sans ``prefLabel`` dans cette langue.

Le rapport peut être filtré par ``scheme_code`` pour cibler un
sous-ensemble du référentiel. La sortie est structurée
(``QualityReport`` avec un compteur par catégorie + échantillons
limités), exposée par la CLI ``nephos validate quality``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

import psycopg

from nephos.logging import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass(slots=True)
class QualityFinding:
    """Une catégorie d'anomalie détectée (avec compteur + échantillons)."""

    code: str
    label: str
    severity: str  # "error" | "warning" | "info"
    count: int
    samples: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(slots=True)
class QualityReport:
    """Rapport agrégé d'une exécution de ``QualityReporter``."""

    findings: list[QualityFinding]
    scheme_filter: str | None = None
    target_languages: tuple[str, ...] = ("fr", "en")

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" and f.count > 0 for f in self.findings)

    @property
    def total_anomalies(self) -> int:
        return sum(f.count for f in self.findings)


class QualityReporter:
    """Compose un ``QualityReport`` à partir d'une base PostgreSQL."""

    def __init__(
        self,
        *,
        scheme_code: str | None = None,
        target_languages: Iterable[str] = ("fr", "en"),
        sample_limit: int = 5,
    ) -> None:
        self._scheme_code = scheme_code
        self._target_languages = tuple(target_languages)
        self._sample_limit = sample_limit

    def run(self, conn: psycopg.Connection) -> QualityReport:
        findings = [
            self._concepts_without_pref_label(conn),
            self._concepts_without_scheme(conn),
            self._concepts_self_broader(conn),
            self._duplicate_pref_label_lang(conn),
            self._duplicate_notation_in_scheme(conn),
            self._duplicate_mappings(conn),
        ]
        for lang in self._target_languages:
            findings.append(self._missing_lang_labels(conn, lang))
        return QualityReport(
            findings=findings,
            scheme_filter=self._scheme_code,
            target_languages=self._target_languages,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _scheme_join(self) -> str:
        """Fragment SQL conditionnel pour restreindre à un scheme.

        Retourne une chaîne vide si pas de filtre. Sinon, pose la
        jointure et la clause WHERE additionnelle. Le placeholder
        ``%(scheme_code)s`` est exposé pour `params`.
        """
        if self._scheme_code is None:
            return ""
        return (
            " AND EXISTS ("
            "  SELECT 1 FROM vocab.concept_in_scheme cis2 "
            "  JOIN vocab.scheme s2 ON s2.scheme_id = cis2.scheme_id "
            "  WHERE cis2.concept_id = c.concept_id AND s2.code = %(scheme_code)s"
            ")"
        )

    def _params(self, **extra: object) -> dict[str, object]:
        params: dict[str, object] = dict(extra)
        if self._scheme_code is not None:
            params["scheme_code"] = self._scheme_code
        return params

    def _samples_uri(
        self, conn: psycopg.Connection, sql: str, params: dict[str, object]
    ) -> list[str]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [str(row[0]) for row in cur.fetchall()]

    def _count(self, conn: psycopg.Connection, sql: str, params: dict[str, object]) -> int:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            assert row is not None
            return int(row[0])

    # ------------------------------------------------------------------
    # Détecteurs
    # ------------------------------------------------------------------

    def _concepts_without_pref_label(self, conn: psycopg.Connection) -> QualityFinding:
        scheme_filter = self._scheme_join()
        # nosec B608 — `scheme_filter` est un fragment SQL constant interne.
        base = (
            "FROM vocab.concept c WHERE NOT EXISTS ("
            "  SELECT 1 FROM vocab.concept_label cl "
            "  WHERE cl.concept_id = c.concept_id AND cl.kind = 'pref'"
            ")"
        )
        full = base + scheme_filter
        count = self._count(conn, "SELECT COUNT(*) " + full, self._params())  # nosec B608
        samples = self._samples_uri(
            conn,
            "SELECT c.uri " + full + " ORDER BY c.concept_id LIMIT %(limit)s",  # nosec B608
            self._params(limit=self._sample_limit),
        )
        return QualityFinding(
            code="concepts_without_pref_label",
            label="Concepts sans aucun prefLabel",
            severity="error",
            count=count,
            samples=samples,
        )

    def _concepts_without_scheme(self, conn: psycopg.Connection) -> QualityFinding:
        # Un filtre par scheme n'a pas de sens ici (un concept n'ayant aucun
        # scheme ne sera pas visible dans le scheme cible) → on ignore le filtre.
        if self._scheme_code is not None:
            return QualityFinding(
                code="concepts_without_scheme",
                label="Concepts non rattachés à un scheme",
                severity="warning",
                count=0,
                samples=[],
            )
        sql = (
            "FROM vocab.concept c WHERE NOT EXISTS ("
            "  SELECT 1 FROM vocab.concept_in_scheme cis WHERE cis.concept_id = c.concept_id"
            ")"
        )
        count = self._count(conn, "SELECT COUNT(*) " + sql, {})  # nosec B608
        samples = self._samples_uri(
            conn,
            "SELECT c.uri " + sql + " ORDER BY c.concept_id LIMIT %(limit)s",  # nosec B608
            {"limit": self._sample_limit},
        )
        return QualityFinding(
            code="concepts_without_scheme",
            label="Concepts non rattachés à un scheme",
            severity="warning",
            count=count,
            samples=samples,
        )

    def _concepts_self_broader(self, conn: psycopg.Connection) -> QualityFinding:
        scheme_filter = ""
        params: dict[str, object] = {}
        if self._scheme_code is not None:
            scheme_filter = (
                " AND EXISTS ("
                "  SELECT 1 FROM vocab.concept_in_scheme cis "
                "  JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
                "  WHERE cis.concept_id = c.concept_id AND s.code = %(scheme_code)s"
                ")"
            )
            params["scheme_code"] = self._scheme_code
        base = (
            "FROM vocab.concept_semantic_relation csr "
            "JOIN vocab.concept c ON c.concept_id = csr.source_concept_id "
            "WHERE csr.relation = 'broader' "
            "AND csr.source_concept_id = csr.target_concept_id"
        )
        full = base + scheme_filter
        count = self._count(conn, "SELECT COUNT(*) " + full, params)  # nosec B608
        samples = self._samples_uri(
            conn,
            "SELECT c.uri " + full + " ORDER BY c.concept_id LIMIT %(limit)s",  # nosec B608
            {**params, "limit": self._sample_limit},
        )
        return QualityFinding(
            code="concepts_self_broader",
            label="Concepts dont broader pointe sur eux-mêmes",
            severity="error",
            count=count,
            samples=samples,
        )

    def _duplicate_pref_label_lang(self, conn: psycopg.Connection) -> QualityFinding:
        scheme_filter = self._scheme_join()
        base = (
            "FROM vocab.concept_label cl "
            "JOIN vocab.concept c ON c.concept_id = cl.concept_id "
            "WHERE cl.kind = 'pref' "
            "GROUP BY cl.concept_id, cl.lang, c.uri "
            "HAVING COUNT(*) > 1"
        )
        # On joint le filtre scheme via une sous-requête EXISTS dans le WHERE,
        # avant le GROUP BY, donc on doit insérer scheme_filter avant GROUP BY.
        if scheme_filter:
            base = base.replace(" GROUP BY ", scheme_filter + " GROUP BY ")
        # Comptage : nombre de (concept_id, lang) en doublon.
        count_sql = "SELECT COUNT(*) FROM (SELECT 1 " + base + ") t"  # nosec B608
        count = self._count(conn, count_sql, self._params())
        samples_sql = (
            "SELECT c.uri || ' [' || cl.lang || ']' " + base + " LIMIT %(limit)s"  # nosec B608
        )
        samples = self._samples_uri(conn, samples_sql, self._params(limit=self._sample_limit))
        return QualityFinding(
            code="duplicate_pref_label_lang",
            label="Concept avec plusieurs prefLabel dans la même langue (SKOS S14)",
            severity="error",
            count=count,
            samples=samples,
        )

    def _duplicate_notation_in_scheme(self, conn: psycopg.Connection) -> QualityFinding:
        scheme_clause = ""
        params: dict[str, object] = {}
        if self._scheme_code is not None:
            scheme_clause = " AND s.code = %(scheme_code)s"
            params["scheme_code"] = self._scheme_code
        base = (
            "FROM vocab.concept c "
            "JOIN vocab.concept_in_scheme cis ON cis.concept_id = c.concept_id "
            "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
            "WHERE c.notation IS NOT NULL"
            + scheme_clause
            + " GROUP BY c.notation, s.scheme_id, s.code "
            "HAVING COUNT(*) > 1"
        )
        count_sql = "SELECT COUNT(*) FROM (SELECT 1 " + base + ") t"  # nosec B608
        count = self._count(conn, count_sql, params)
        samples_sql = (
            "SELECT s.code || '/' || c.notation || ' (x' || COUNT(*) || ')' "  # nosec B608
            + base
            + " LIMIT %(limit)s"
        )
        samples = self._samples_uri(conn, samples_sql, {**params, "limit": self._sample_limit})
        return QualityFinding(
            code="duplicate_notation_in_scheme",
            label="Notations dupliquées dans un même scheme",
            severity="error",
            count=count,
            samples=samples,
        )

    def _duplicate_mappings(self, conn: psycopg.Connection) -> QualityFinding:
        scheme_filter = self._scheme_join()
        base = (
            "FROM vocab.concept_mapping cm "
            "JOIN vocab.concept c ON c.concept_id = cm.concept_id "
            "WHERE TRUE"
        )
        full = (
            base
            + scheme_filter
            + (
                " GROUP BY cm.concept_id, cm.target_uri, c.uri "
                "HAVING COUNT(DISTINCT cm.mapping_relation) > 1"
            )
        )
        count_sql = "SELECT COUNT(*) FROM (SELECT 1 " + full + ") t"  # nosec B608
        count = self._count(conn, count_sql, self._params())
        samples_sql = "SELECT c.uri || ' → ' || cm.target_uri " + full + " LIMIT %(limit)s"  # nosec B608
        samples = self._samples_uri(conn, samples_sql, self._params(limit=self._sample_limit))
        return QualityFinding(
            code="duplicate_mappings",
            label="Mappings divergents (relations multiples vers la même cible)",
            severity="error",
            count=count,
            samples=samples,
        )

    def _missing_lang_labels(self, conn: psycopg.Connection, lang: str) -> QualityFinding:
        scheme_filter = self._scheme_join()
        base = (
            "FROM vocab.concept c "
            "WHERE c.status = 'published' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM vocab.concept_label cl "
            "  WHERE cl.concept_id = c.concept_id "
            "  AND cl.kind = 'pref' "
            "  AND cl.lang = %(lang)s"
            ")"
        )
        full = base + scheme_filter
        count = self._count(conn, "SELECT COUNT(*) " + full, self._params(lang=lang))  # nosec B608
        samples = self._samples_uri(
            conn,
            "SELECT c.uri " + full + " ORDER BY c.concept_id LIMIT %(limit)s",  # nosec B608
            self._params(lang=lang, limit=self._sample_limit),
        )
        severity = "warning"  # Manquer une langue ≠ erreur structurelle, mais à corriger.
        return QualityFinding(
            code=f"missing_pref_label_{lang}",
            label=f"Concepts publiés sans prefLabel@{lang} (ADR 0004 si {lang}∈(fr,en))",
            severity=severity,
            count=count,
            samples=samples,
        )
