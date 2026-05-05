"""CLI principal de Nephos."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from nephos import __version__
from nephos.config import get_settings
from nephos.etl.runner import ImportRunner, RunOptions
from nephos.importers import CFStandardNamesImporter, QUDTUnitsImporter
from nephos.logging import configure_logging

app: typer.Typer = typer.Typer(
    name="nephos",
    help="Référentiel SKOS de métadonnées météorologiques.",
    no_args_is_help=True,
    add_completion=False,
    invoke_without_command=True,
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


# ----- import -----


@import_app.command("status")
def import_status() -> None:
    """Affiche l'état de synchronisation de chaque source standard.

    Implémentation complète : item E4-09 du backlog.
    Pour l'instant, un SELECT sur la vue `gov.v_imports_status`
    suffira (à ajouter quand E4-09 sera traité).
    """
    console.print("[yellow]Pas encore implémenté.[/yellow] Voir item E4-09 du backlog.")


@import_app.command("cf")
def import_cf(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="N'écrit rien en base.")] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            help="URL ou chemin local vers le fichier XML CF. Par défaut : URL officielle.",
        ),
    ] = None,
) -> None:
    """Importe les CF Standard Names depuis cfconventions.org."""
    src: str | Path | None = None
    if source is not None:
        src = Path(source) if Path(source).exists() else source
    importer = CFStandardNamesImporter(source=src)
    _run_and_print(importer, dry_run, "CF Standard Names")


@import_app.command("qudt-units")
def import_qudt_units(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="N'écrit rien en base.")] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            help="URL ou chemin local vers le Turtle QUDT. Par défaut : URL officielle.",
        ),
    ] = None,
) -> None:
    """Importe les unités QUDT depuis qudt.org."""
    src: str | Path | None = None
    if source is not None:
        src = Path(source) if Path(source).exists() else source
    importer = QUDTUnitsImporter(source=src)
    _run_and_print(importer, dry_run, "QUDT Units")


def _run_and_print(importer: object, dry_run: bool, title: str) -> None:
    """Exécute l'import et affiche un rapport Rich uniforme.

    Le typage de `importer` reste `object` ici pour éviter une dépendance
    rigide sur l'ABC `Importer` (le runner accepte tout `Importer`).
    """
    from nephos.etl.base import Importer as _ImporterABC

    assert isinstance(importer, _ImporterABC)
    result = ImportRunner(importer).run(RunOptions(dry_run=dry_run))
    table = Table(title=f"Import {title} — version {result.version}")
    table.add_column("Métrique", style="cyan")
    table.add_column("Valeur", justify="right")
    table.add_row("Entrées vues", str(result.nb_entites))
    table.add_row("Créations", str(result.nb_creations))
    table.add_row("Modifications", str(result.nb_modifications))
    table.add_row("Inchangées", str(result.nb_skipped))
    table.add_row("Overrides protégés", str(result.nb_overrides_protected))
    if result.notes:
        table.add_row("Notes", result.notes)
    console.print(table)


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
def validate_shacl(
    scheme: Annotated[
        str | None,
        typer.Option("--scheme", help="Limite la validation à un scheme (code)."),
    ] = None,
    treat_as_published: Annotated[
        bool,
        typer.Option(
            "--strict",
            help=(
                "Force la validation comme si tous les concepts étaient publiés "
                "(impose prefLabel@fr ET @en, ADR 0004)."
            ),
        ),
    ] = False,
    show_report: Annotated[
        bool,
        typer.Option("--report", help="Affiche le rapport SHACL complet (texte)."),
    ] = False,
) -> None:
    """Valide les concepts du référentiel contre les shapes SHACL Nephos Core."""
    from nephos.db import connect
    from nephos.validators import SHACLValidator

    validator = SHACLValidator(treat_as_published=treat_as_published)
    with connect() as conn:
        result = validator.validate(conn, scheme_code=scheme)

    table = Table(title="Validation SHACL — Nephos Core")
    table.add_column("Métrique", style="cyan")
    table.add_column("Valeur", justify="right")
    table.add_row("Conforme", "✅" if result.conforms else "❌")
    table.add_row("Concepts validés", str(result.concepts_validated))
    table.add_row("Violations", str(result.violations))
    table.add_row("Warnings", str(result.warnings))
    table.add_row("Infos", str(result.infos))
    console.print(table)

    if show_report and not result.conforms:
        console.print("\n[bold]Rapport détaillé :[/bold]")
        console.print(result.raw_report)


if __name__ == "__main__":  # pragma: no cover
    app()
