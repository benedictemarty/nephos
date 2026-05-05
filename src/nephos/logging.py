"""Configuration du logging Nephos.

Deux formats supportés (`Settings.log_format`) :
  - `text` : sortie humaine (`%(asctime)s %(levelname)-8s %(name)s — %(message)s`).
  - `json` : sortie structurée (un objet JSON par ligne) — destinée aux
            collecteurs (Loki, Datadog, ELK).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from nephos.config import Settings, get_settings


class _JSONFormatter(logging.Formatter):
    """Formatter qui sérialise chaque LogRecord en un objet JSON par ligne."""

    _STANDARD_ATTRS: frozenset[str] = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "taskName",
            "message",
            "asctime",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Champs ajoutés via `logger.info("...", extra={"key": value})`
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings | None = None) -> None:
    """Configure le logger racine selon la configuration.

    Idempotent : un appel répété remplace les handlers existants.
    """
    settings = settings or get_settings()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(stream=sys.stderr)
    if settings.log_format == "json":
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger pré-configuré pour le module appelant."""
    return logging.getLogger(name)
