"""Tests unitaires du CLI (sans dépendance Postgres)."""

from __future__ import annotations

from typer.testing import CliRunner

from nephos.cli import app

runner = CliRunner()


def test_help_does_not_crash() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "nephos" in result.stdout.lower()


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "nephos" in result.stdout.lower()


# `nephos import status` est désormais implémenté (E4-09) et nécessite Postgres ;
# il est couvert par tests/integration/test_cli_import_status.py.


def test_db_apply_returns_placeholder() -> None:
    result = runner.invoke(app, ["db", "apply"])
    assert result.exit_code == 0


def test_validate_shacl_returns_placeholder() -> None:
    result = runner.invoke(app, ["validate", "shacl"])
    assert result.exit_code == 0
