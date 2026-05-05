"""Permet `python -m nephos`."""

from nephos.cli import app


def main() -> None:
    """Point d'entrée explicite (sortie typée pour mypy strict)."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
