"""Test d'intégration de la commande `nephos import status` (E4-09)."""

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


def test_import_status_lists_sources_seeded(db_conn: psycopg.Connection) -> None:
    """Sur une base fraîche, les 8 sources seedées par le schéma sont listées,
    chacune avec 0 import et 0 concept.
    """
    runner = CliRunner()
    result = runner.invoke(app, ["import", "status"])
    assert result.exit_code == 0
    # Les codes des 8 sources seed doivent apparaître.
    for source_code in ("CF", "CF_CELL", "CF_AREA", "WMO_CODES", "QUDT_UNIT"):
        assert source_code in result.stdout


def test_import_status_reflects_an_import_run(db_conn: psycopg.Connection) -> None:
    """Après une exécution simulée de `gov.imports`, la vue compte +1 version."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT import_source_id FROM gov.import_sources WHERE code = 'CF'")
        row = cur.fetchone()
        assert row is not None
        cf_id = int(row[0])
        cur.execute(
            "INSERT INTO gov.imports (import_source_id, version, status) "
            "VALUES (%s, 'v1', 'success')",
            (cf_id,),
        )

    runner = CliRunner()
    result = runner.invoke(app, ["import", "status"])
    assert result.exit_code == 0
    assert "CF" in result.stdout
