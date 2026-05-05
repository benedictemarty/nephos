"""Test d'intégration de `nephos validate all` (E5-05)."""

from __future__ import annotations

import os

import psycopg
import pytest
from typer.testing import CliRunner

from nephos.cli import app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _propagate_db_url(db_conn: psycopg.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("NEPHOS_DATABASE_URL")
    if url is None:
        pytest.skip("NEPHOS_DATABASE_URL requis")
    monkeypatch.setenv("NEPHOS_DATABASE_URL", url)


def _ensure_clean_scheme(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.scheme (uri, code, title, status) "
            "VALUES ('https://w3id.org/nephos/vocab/test', 'test', 'Test', 'approved') "
            "RETURNING scheme_id"
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _add_concept_with_label(conn: psycopg.Connection, scheme_id: int, notation: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) "
            "VALUES (%s, %s, 'approved') RETURNING concept_id",
            (f"https://w3id.org/nephos/vocab/test/{notation}", notation),
        )
        row = cur.fetchone()
        assert row is not None
        cid = int(row[0])
        cur.execute(
            "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
            (cid, scheme_id),
        )
        cur.execute(
            "INSERT INTO vocab.concept_label (concept_id, lang, kind, value) "
            "VALUES (%s, 'en', 'pref', %s)",
            (cid, notation.upper()),
        )


def test_validate_all_clean_base_exits_zero(db_conn: psycopg.Connection) -> None:
    scheme_id = _ensure_clean_scheme(db_conn)
    _add_concept_with_label(db_conn, scheme_id, "ok")

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "all", "--scheme", "test"])
    assert result.exit_code == 0
    assert "SHACL" in result.stdout
    assert "Qualité" in result.stdout


def test_validate_all_fail_on_error_exits_two_when_quality_finds_error(
    db_conn: psycopg.Connection,
) -> None:
    """Concept sans prefLabel ⇒ qualité signale une erreur ⇒ exit 2 avec --fail-on-error."""
    scheme_id = _ensure_clean_scheme(db_conn)
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) "
            "VALUES ('https://w3id.org/nephos/vocab/test/orph', 'orph', 'approved') "
            "RETURNING concept_id"
        )
        row = cur.fetchone()
        assert row is not None
        cur.execute(
            "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
            (int(row[0]), scheme_id),
        )

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "all", "--scheme", "test", "--fail-on-error"])
    assert result.exit_code == 2


def test_validate_all_without_fail_flag_exits_zero_even_with_errors(
    db_conn: psycopg.Connection,
) -> None:
    """Sans `--fail-on-error`, le code de retour reste 0 même si erreurs détectées."""
    scheme_id = _ensure_clean_scheme(db_conn)
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO vocab.concept (uri, notation, status) "
            "VALUES ('https://w3id.org/nephos/vocab/test/orph2', 'orph2', 'approved') "
            "RETURNING concept_id"
        )
        row = cur.fetchone()
        assert row is not None
        cur.execute(
            "INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id) VALUES (%s, %s)",
            (int(row[0]), scheme_id),
        )

    runner = CliRunner()
    result = runner.invoke(app, ["validate", "all", "--scheme", "test"])
    assert result.exit_code == 0
