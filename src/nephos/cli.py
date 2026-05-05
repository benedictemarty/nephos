"""CLI principal de Nephos."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from nephos import __version__
from nephos.config import get_settings
from nephos.logging import configure_logging

app: typer.Typer = typer.Typer(
    name="nephos",
    help="Référentiel SKOS de métadonnées météorologiques.",
    no_args_is_help=True,
    add_completion=False,
)

import_app: typer.Typer = typer.Typer(
    help="Imports depuis les sources standards (CF, QUDT, WMO, …)."
)
db_app: typer.Typer = typer.Typer(help="Gestion du schéma et des migrations PostgreSQL.")
export_app: typer.Typer = typer.Typer(help="Exports RDF/SKOS du référentiel.")
validate_app: typer.Typer = typer.Typer(help="Validation SHACL des concepts.")

app.add_typer(import_app, name="import")
app.add_typer(db_app, name="db")
app.add_typer(export_app, name="export")
app.add_typer(validate_app, name="validate")

console: Console = Console()


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Affiche la version et quitte."),
    ] = False,
) -> None:
    """Initialise le logging applicatif puis dispatch vers la sous-commande."""
    configure_logging()
    if version:
        console.print(f"nephos {__version__}")
        raise typer.Exit


@app.command()
def info() -> None:
    """Affiche la configuration courante (sources, base, dossier de travail)."""
    settings = get_settings()
    table = Table(title="Configuration Nephos", show_header=False)
    table.add_column("Clé", style="cyan", no_wrap=True)
    table.add_column("Valeur")
    table.add_row("version", __version__)
    table.add_row("database_url", str(settings.database_url))
    table.add_row("uri_base", settings.uri_base)
    table.add_row("log_level", settings.log_level)
    table.add_row("log_format", settings.log_format)
    table.add_row("work_dir", str(settings.work_dir))
    console.print(table)


# ----- import (squelette) -----


@import_app.command("status")
def import_status() -> None:
    """Affiche l'état de synchronisation de chaque source standard."""
    console.print("[yellow]Pas encore implémenté.[/yellow] Voir item E4-09 du backlog.")


@import_app.command("cf")
def import_cf() -> None:
    """Importe les CF Standard Names depuis cfconventions.org."""
    console.print("[yellow]Pas encore implémenté.[/yellow] Voir item E4-02 du backlog.")


# ----- db (squelette) -----


@db_app.command("apply")
def db_apply() -> None:
    """Applique le schéma SKOS v4 sur la base configurée."""
    console.print(
        "[yellow]Pas encore implémenté.[/yellow] "
        "En attendant, utiliser : psql -d <db> -f schema_v4_skos.sql"
    )


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Applique les migrations Alembic en attente."""
    console.print("[yellow]Pas encore implémenté.[/yellow] Voir item E3-09 du backlog.")


# ----- export (squelette) -----


@export_app.command("turtle")
def export_turtle(
    scheme: Annotated[str, typer.Argument(help="Code du scheme à exporter.")],
) -> None:
    """Exporte un scheme SKOS au format Turtle (.ttl)."""
    console.print(
        f"[yellow]Pas encore implémenté.[/yellow] "
        f"Demande : export Turtle de '{scheme}'. Voir item E6-01 du backlog."
    )


# ----- validate (squelette) -----


@validate_app.command("shacl")
def validate_shacl() -> None:
    """Valide les concepts contre les shapes SHACL Nephos."""
    console.print("[yellow]Pas encore implémenté.[/yellow] Voir items E5-01..03 du backlog.")


if __name__ == "__main__":  # pragma: no cover
    app()
