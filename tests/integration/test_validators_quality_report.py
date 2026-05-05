"""Tests d'intégration de `QualityReporter` (E5-04)."""

from __future__ import annotations

import os

import psycopg
import pytest

from nephos.validators.quality_report import QualityReporter

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _ensure_scheme(conn: psycopg.Connection, code: str = "test") -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.scheme (uri, code, title, status) VALUES (%s, %s, %s, 'approved') "
            "RETURNING scheme_id",
            (f"https://w3id.org/nephos/vocab/{code}", code, f"Scheme test {code}"),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _add_concept(
    conn: psycopg.Connection,
    *,
    notation: str,
    scheme_id: int | None,
    status: str = "approved",
    pref_labels: dict[str, str] | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) VALUES (%s, %s, %s) "
            "RETURNING concept_id",
            (f"https://w3id.org/nephos/vocab/test/{notation}", notation, status),
        )
        row = cur.fetchone()
        assert row is not None
        concept_id = int(row[0])
        if scheme_id is not None:
            cur.execute(
                "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
                (concept_id, scheme_id),
            )
        if pref_labels:
            for lang, value in pref_labels.items():
                cur.execute(
                    "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
                    "VALUES (%s, %s, 'pref', %s)",
                    (concept_id, lang, value),
                )
    return concept_id


def _findings_by_code(conn: psycopg.Connection, **kwargs: object) -> dict[str, int]:
    reporter = QualityReporter(**kwargs)  # type: ignore[arg-type]
    report = reporter.run(conn)
    return {f.code: f.count for f in report.findings}


class TestQualityReportFindings:
    def test_clean_base_has_no_anomalies(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(db_conn, notation="x", scheme_id=scheme_id, pref_labels={"en": "X", "fr": "X"})
        counts = _findings_by_code(db_conn)
        # Tous à 0 sauf potentiellement les concepts seed du schema_v4_skos.sql.
        assert counts["concepts_self_broader"] == 0
        assert counts["duplicate_pref_label_lang"] == 0
        assert counts["duplicate_notation_in_scheme"] == 0
        assert counts["duplicate_mappings"] == 0

    def test_concepts_without_pref_label_detected(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(db_conn, notation="orphan", scheme_id=scheme_id)
        counts = _findings_by_code(db_conn, scheme_code="test")
        assert counts["concepts_without_pref_label"] >= 1

    def test_concepts_without_scheme_detected(self, db_conn: psycopg.Connection) -> None:
        _add_concept(db_conn, notation="floating", scheme_id=None, pref_labels={"en": "Floating"})
        counts = _findings_by_code(db_conn)
        assert counts["concepts_without_scheme"] >= 1

    def test_self_broader_detector_returns_zero_when_db_blocks_it(
        self, db_conn: psycopg.Connection
    ) -> None:
        """Le schéma v4 a une CHECK constraint qui empêche self-broader.

        Le détecteur reste utile en défense en profondeur (si la
        contrainte est levée par migration future ou bypass admin) ;
        on vérifie juste qu'il retourne 0 sur une base saine.
        """
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(db_conn, notation="ok", scheme_id=scheme_id, pref_labels={"en": "OK"})
        counts = _findings_by_code(db_conn, scheme_code="test")
        assert counts["concepts_self_broader"] == 0

    def test_duplicate_pref_label_lang_blocked_by_db(self, db_conn: psycopg.Connection) -> None:
        """La contrainte `uq_concept_pref_lang` empêche déjà les doublons.

        Le détecteur reste exécuté (défense en profondeur) ; on
        vérifie qu'il retourne 0 sur une base nominale.
        """
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(db_conn, notation="ok2", scheme_id=scheme_id, pref_labels={"en": "OK"})
        counts = _findings_by_code(db_conn, scheme_code="test")
        assert counts["duplicate_pref_label_lang"] == 0

    def test_duplicate_notation_in_scheme_detected(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        # Deux concepts distincts (URI différents) avec la même notation dans le même scheme.
        # Postgres l'autorise (la contrainte unique porte sur l'URI, pas sur (notation, scheme)).
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vocab.concept (uri, notation, status) VALUES "
                "('https://w3id.org/nephos/vocab/test/a', 'shared', 'approved'),"
                "('https://w3id.org/nephos/vocab/test/b', 'shared', 'approved') "
                "RETURNING concept_id"
            )
            ids = [int(r[0]) for r in cur.fetchall()]
            for cid in ids:
                cur.execute(
                    "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
                    (cid, scheme_id),
                )
        counts = _findings_by_code(db_conn, scheme_code="test")
        assert counts["duplicate_notation_in_scheme"] == 1

    def test_duplicate_mappings_detected(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        cid = _add_concept(db_conn, notation="m", scheme_id=scheme_id, pref_labels={"en": "M"})
        with db_conn.cursor() as cur:
            cur.execute("SELECT import_source_id FROM gov.import_sources WHERE code = 'CF'")
            row = cur.fetchone()
            assert row is not None
            src_id = int(row[0])
            for relation in ("exactMatch", "closeMatch"):
                cur.execute(
                    "INSERT INTO vocab.concept_mapping "
                    "(concept_id, target_source_id, target_uri, mapping_relation) "
                    "VALUES (%s, %s, 'https://example.org/X', %s)",
                    (cid, src_id, relation),
                )
        counts = _findings_by_code(db_conn, scheme_code="test")
        assert counts["duplicate_mappings"] == 1

    def test_missing_pref_label_fr_for_published(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(
            db_conn,
            notation="onlyfr",
            scheme_id=scheme_id,
            status="published",
            pref_labels={"fr": "Truc"},
        )
        _add_concept(
            db_conn,
            notation="onlyen",
            scheme_id=scheme_id,
            status="published",
            pref_labels={"en": "Thing"},
        )
        counts = _findings_by_code(db_conn, scheme_code="test")
        # Seul "onlyen" manque le FR ; "onlyfr" manque l'EN.
        assert counts["missing_pref_label_fr"] == 1
        assert counts["missing_pref_label_en"] == 1


class TestQualityReportFiltering:
    def test_scheme_filter_isolates_concepts(self, db_conn: psycopg.Connection) -> None:
        scheme_a = _ensure_scheme(db_conn, "scheme-a")
        scheme_b = _ensure_scheme(db_conn, "scheme-b")
        # Anomalie dans scheme-b uniquement.
        _add_concept(db_conn, notation="orphan_b", scheme_id=scheme_b)
        # Concept clean dans scheme-a.
        _add_concept(db_conn, notation="ok_a", scheme_id=scheme_a, pref_labels={"en": "A"})

        counts_a = _findings_by_code(db_conn, scheme_code="scheme-a")
        counts_b = _findings_by_code(db_conn, scheme_code="scheme-b")
        # L'orphelin n'est compté que côté b.
        assert counts_a["concepts_without_pref_label"] == 0
        assert counts_b["concepts_without_pref_label"] == 1


class TestQualityReportShape:
    def test_report_has_severity_and_samples(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(db_conn, notation="orph1", scheme_id=scheme_id)
        _add_concept(db_conn, notation="orph2", scheme_id=scheme_id)
        report = QualityReporter(scheme_code="test", sample_limit=2).run(db_conn)
        finding = next(f for f in report.findings if f.code == "concepts_without_pref_label")
        assert finding.severity == "error"
        assert finding.count == 2
        assert len(finding.samples) == 2
        assert all(s.startswith("https://w3id.org/nephos/vocab/test/") for s in finding.samples)
        assert report.has_errors is True

    def test_total_anomalies_aggregates(self, db_conn: psycopg.Connection) -> None:
        scheme_id = _ensure_scheme(db_conn)
        _add_concept(db_conn, notation="orph", scheme_id=scheme_id)
        report = QualityReporter(scheme_code="test").run(db_conn)
        assert report.total_anomalies >= 1
