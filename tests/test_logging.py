"""Tests unitaires du module `nephos.logging`."""

from __future__ import annotations

import json
import logging

import pytest

from nephos.config import Settings
from nephos.logging import configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Restaure l'état du logger racine après chaque test."""
    yield
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.WARNING)


def _make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql://nephos:nephos@localhost/test",
        "log_level": "INFO",
        "log_format": "text",
    }
    base.update(overrides)
    return Settings.model_validate(base)


def test_configure_logging_text_format(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_make_settings(log_format="text", log_level="INFO"))
    get_logger("nephos.test").info("hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.err
    assert "nephos.test" in captured.err


def test_configure_logging_json_format(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_make_settings(log_format="json", log_level="INFO"))
    get_logger("nephos.test").info("structured")
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "nephos.test"
    assert payload["message"] == "structured"
    assert "ts" in payload


def test_json_format_includes_extra_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(_make_settings(log_format="json", log_level="INFO"))
    get_logger("nephos.test").info("with extra", extra={"source": "CF", "count": 42})
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["source"] == "CF"
    assert payload["count"] == 42


def test_configure_logging_is_idempotent() -> None:
    configure_logging(_make_settings())
    handlers_before = list(logging.getLogger().handlers)
    configure_logging(_make_settings())
    handlers_after = list(logging.getLogger().handlers)
    assert len(handlers_after) == len(handlers_before) == 1


def test_log_level_respected(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(_make_settings(log_format="text", log_level="ERROR"))
    log = get_logger("nephos.test")
    log.info("not shown")
    log.error("shown")
    captured = capsys.readouterr()
    assert "not shown" not in captured.err
    assert "shown" in captured.err
