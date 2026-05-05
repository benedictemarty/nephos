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
from nephos.importers import (
    WMO_PRESETS,
    CFAreaTypeImporter,
    CFStandardNamesImporter,
    ECMWFMappingsImporter,
    QUDTUnitsImporter,
    WMOCodesImporter,
)
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

    Lit la vue `gov.v_imports_status` qui agrège, par source d'import :
    nombre de versions importées, dernier import, nombre de concepts
    issus de cette source, et nombre d'overrides locaux.
    """
    from nephos.db import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT source, source_nom, licence, nb_versions_importees, "
            "derniere_import, nb_concepts, nb_overrides_locaux "
            "FROM gov.v_imports_status ORDER BY source"
        )
        rows = cur.fetchall()

    table = Table(title="État des imports Nephos")
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Nom")
    table.add_column("Licence", style="dim")
    table.add_column("Versions", justify="right")
    table.add_column("Dernier import", style="dim")
    table.add_column("Concepts", justify="right")
    table.add_column("Overrides", justify="right")

    for source, nom, licence, nb_versions, derniere, nb_concepts, nb_overrides in rows:
        table.add_row(
            str(source),
            str(nom or ""),
            str(licence or ""),
            str(nb_versions or 0),
            derniere.strftime("%Y-%m-%d %H:%M") if derniere else "—",
            str(nb_concepts or 0),
            str(nb_overrides or 0),
        )
    console.print(table)


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


@import_app.command("cf-area")
def import_cf_area(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="N'écrit rien en base.")] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            help="URL ou chemin local vers le fichier XML CF Area Type. Par défaut : URL officielle.",
        ),
    ] = None,
) -> None:
    """Importe les CF Area Type depuis cfconventions.org."""
    src: str | Path | None = None
    if source is not None:
        src = Path(source) if Path(source).exists() else source
    importer = CFAreaTypeImporter(source=src)
    _run_and_print(importer, dry_run, "CF Area Type Table")


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


@import_app.command("ecmwf-mappings")
def import_ecmwf_mappings(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="N'écrit rien en base.")] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            help="URL ou chemin local vers cfName.def. Par défaut : ecmwf/eccodes develop.",
        ),
    ] = None,
) -> None:
    """Pose des `closeMatch` CF Standard Names → ECMWF Parameter Database (E4-06)."""
    src: str | Path | None = None
    if source is not None:
        src = Path(source) if Path(source).exists() else source
    importer = ECMWFMappingsImporter(source=src)
    _run_and_print(importer, dry_run, "ECMWF Parameter mappings")


@import_app.command("wmo-codes")
def import_wmo_codes(
    code_list: Annotated[
        str | None,
        typer.Option(
            "--code-list",
            help=(
                "Clé d'une code list WMO préconfigurée (ex. 'bufr-0-02-001'). "
                "Mutuellement exclusif avec --register-url."
            ),
        ),
    ] = None,
    register_url: Annotated[
        str | None,
        typer.Option(
            "--register-url",
            help="URL Turtle d'un register WMO custom (mode avancé).",
        ),
    ] = None,
    scheme_code: Annotated[
        str | None,
        typer.Option("--scheme-code", help="Code Nephos cible (avec --register-url)."),
    ] = None,
    scheme_title: Annotated[
        str | None,
        typer.Option("--scheme-title", help="Titre humain du scheme (avec --register-url)."),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="N'écrit rien en base.")] = False,
    list_presets: Annotated[
        bool,
        typer.Option("--list-presets", help="Affiche les presets WMO disponibles et quitte."),
    ] = False,
) -> None:
    """Importe une code list WMO depuis le WMO Codes Registry (E4-05)."""
    if list_presets:
        table = Table(title="Presets WMO disponibles")
        table.add_column("Clé", style="cyan", no_wrap=True)
        table.add_column("Scheme Nephos")
        table.add_column("Register URL", style="dim")
        for key, preset in sorted(WMO_PRESETS.items()):
            table.add_row(key, preset.scheme_code, preset.register_url)
        console.print(table)
        return

    if code_list is not None and register_url is not None:
        console.print("[red]--code-list et --register-url sont mutuellement exclusifs.[/red]")
        raise typer.Exit(code=2)

    if code_list is not None:
        try:
            importer = WMOCodesImporter.from_preset(code_list)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from exc
        title = f"WMO Codes — {code_list}"
    elif register_url is not None:
        if not scheme_code or not scheme_title:
            console.print("[red]--register-url exige --scheme-code et --scheme-title.[/red]")
            raise typer.Exit(code=2)
        importer = WMOCodesImporter(
            register_url=register_url, scheme_code=scheme_code, scheme_title=scheme_title
        )
        title = f"WMO Codes — {scheme_code}"
    else:
        console.print(
            "[red]Préciser --code-list <preset> ou --register-url <url> "
            "(voir --list-presets).[/red]"
        )
        raise typer.Exit(code=2)

    _run_and_print(importer, dry_run, title)


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
    table.add_row("Deprecated (disparus)", str(result.nb_deprecated_disappeared))
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
    scheme: Annotated[
        str | None,
        typer.Argument(help="Code du scheme à exporter (par défaut : tout)."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Fichier de sortie (sinon stdout)."),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Format RDF : turtle (défaut), xml (RDF/XML), json-ld, n3.",
        ),
    ] = "turtle",
) -> None:
    """Exporte un scheme SKOS (ou tout le référentiel) au format RDF demandé."""
    from nephos.db import connect
    from nephos.exporters import SKOSExporter

    valid_formats = {"turtle", "xml", "json-ld", "n3"}
    if fmt not in valid_formats:
        console.print(f"[red]Format invalide : {fmt}.[/red] Choisir parmi {valid_formats}.")
        raise typer.Exit(code=2)

    exporter = SKOSExporter()
    with connect() as conn:
        result = exporter.export(conn, scheme_code=scheme, fmt=fmt)  # type: ignore[arg-type]

    if output is not None:
        output.write_text(result.payload, encoding="utf-8")
        msg = f"Export écrit dans {output}"
    else:
        console.print(result.payload)
        msg = "Export envoyé sur stdout"

    if output is not None:
        table = Table(title=f"Export SKOS ({result.format})")
        table.add_column("Métrique", style="cyan")
        table.add_column("Valeur", justify="right")
        table.add_row("Schemes", str(result.nb_schemes))
        table.add_row("Concepts", str(result.nb_concepts))
        table.add_row("Labels", str(result.nb_labels))
        table.add_row("Notes", str(result.nb_notes))
        table.add_row("Relations internes", str(result.nb_relations))
        table.add_row("Mappings externes", str(result.nb_mappings))
        table.add_row("Sortie", msg)
        console.print(table)


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


@validate_app.command("quality")
def validate_quality(
    scheme: Annotated[
        str | None,
        typer.Option("--scheme", help="Limite le rapport à un scheme (code)."),
    ] = None,
    show_samples: Annotated[
        bool,
        typer.Option("--samples/--no-samples", help="Affiche les URI exemples par catégorie."),
    ] = True,
    fail_on_error: Annotated[
        bool,
        typer.Option(
            "--fail-on-error",
            help="Sortie code 2 s'il existe au moins une anomalie de sévérité 'error'.",
        ),
    ] = False,
) -> None:
    """Rapport de qualité du référentiel (E5-04) — anomalies structurelles."""
    from nephos.db import connect
    from nephos.validators import QualityReporter

    reporter = QualityReporter(scheme_code=scheme)
    with connect() as conn:
        report = reporter.run(conn)

    title = "Rapport qualité Nephos"
    if scheme:
        title += f" (scheme={scheme})"
    table = Table(title=title)
    table.add_column("Catégorie", style="cyan")
    table.add_column("Sévérité", style="dim")
    table.add_column("Compteur", justify="right")
    if show_samples:
        table.add_column("Exemples")

    severity_style = {"error": "red", "warning": "yellow", "info": "dim"}
    for finding in report.findings:
        sev = f"[{severity_style.get(finding.severity, 'white')}]{finding.severity}[/]"
        cells = [finding.label, sev, str(finding.count)]
        if show_samples:
            cells.append(", ".join(finding.samples) if finding.samples else "—")
        table.add_row(*cells)

    console.print(table)
    console.print(f"\nTotal anomalies : [bold]{report.total_anomalies}[/bold]")

    if fail_on_error and report.has_errors:
        raise typer.Exit(code=2)


@validate_app.command("all")
def validate_all(
    scheme: Annotated[
        str | None,
        typer.Option("--scheme", help="Limite la validation à un scheme (code)."),
    ] = None,
    treat_as_published: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Force la validation SHACL en mode publié (impose FR+EN, ADR 0004).",
        ),
    ] = False,
    fail_on_error: Annotated[
        bool,
        typer.Option(
            "--fail-on-error",
            help="Exit 2 si SHACL non conforme OU quality détecte ≥ 1 erreur (E5-05).",
        ),
    ] = False,
) -> None:
    """Validation combinée SHACL + qualité sur un sous-ensemble du référentiel (E5-05).

    Cible alignée avec les commandes individuelles `validate shacl` et
    `validate quality` mais expose un point d'entrée unique pour la
    CI / le pipeline ETL : un seul code de retour, deux rapports
    successifs, même filtre `--scheme`.
    """
    from nephos.db import connect
    from nephos.validators import QualityReporter, SHACLValidator

    shacl_validator = SHACLValidator(treat_as_published=treat_as_published)
    quality_reporter = QualityReporter(scheme_code=scheme)

    with connect() as conn:
        shacl_report = shacl_validator.validate(conn, scheme_code=scheme)
        quality_report = quality_reporter.run(conn)

    summary_title = "Validation combinée Nephos"
    if scheme:
        summary_title += f" (scheme={scheme})"
    summary = Table(title=summary_title)
    summary.add_column("Étape", style="cyan")
    summary.add_column("Indicateur")
    summary.add_column("Valeur", justify="right")
    summary.add_row(
        "SHACL", "Conforme", "[green]oui[/green]" if shacl_report.conforms else "[red]non[/red]"
    )
    summary.add_row("SHACL", "Concepts validés", str(shacl_report.concepts_validated))
    summary.add_row("SHACL", "Violations", str(shacl_report.violations))
    summary.add_row("SHACL", "Warnings", str(shacl_report.warnings))
    summary.add_row(
        "Qualité",
        "Erreurs structurelles",
        f"[red]{sum(f.count for f in quality_report.findings if f.severity == 'error')}[/red]"
        if quality_report.has_errors
        else "[green]0[/green]",
    )
    summary.add_row("Qualité", "Total anomalies", str(quality_report.total_anomalies))
    console.print(summary)

    has_failure = (not shacl_report.conforms) or quality_report.has_errors
    if fail_on_error and has_failure:
        raise typer.Exit(code=2)


if __name__ == "__main__":  # pragma: no cover
    app()
