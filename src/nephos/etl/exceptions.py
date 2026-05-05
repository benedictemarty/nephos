"""Exceptions du framework ETL."""

from __future__ import annotations


class ImportError(Exception):
    """Erreur générique remontée par le pipeline d'import."""


class ImportSourceError(ImportError):
    """La source amont est inaccessible, mal formée, ou répond avec un code d'erreur."""


class ImportValidationError(ImportError):
    """Les données extraites ne respectent pas les contraintes attendues
    (par exemple un concept avec une notation invalide, ou un mapping
    SHACL en échec).
    """
