"""Nephos — référentiel SKOS de métadonnées météorologiques."""

from importlib.metadata import PackageNotFoundError, version

__version__: str
try:
    __version__ = version("nephos")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
