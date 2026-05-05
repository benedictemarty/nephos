"""Orchestrateur d'import — `ImportRunner`.

Pilote le cycle de vie d'un `Importer` :

  1. Découverte de la version amont (`discover_version`).
  2. Pré-check de re-sync : a-t-on déjà cette version sans modifs locales ?
  3. Ouverture d'une ligne `gov.imports` (status `success` à la création).
  4. Extract → transform.
  5. Load (transactionnel).
  6. Clôture du journal avec compteurs.
  7. En cas d'exception : rollback de la transaction de chargement,
     puis mise à jour du journal en `failed` (autocommit) avec message
     d'erreur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nephos.db import connect

if TYPE_CHECKING:
    import psycopg
from nephos.etl.base import Importer, ImportResult
from nephos.etl.exceptions import ImportError, ImportSourceError, ImportValidationError
from nephos.etl.journal import close_run, open_run
from nephos.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class RunOptions:
    """Options d'exécution d'un import."""

    force: bool = False
    """Réimporter même si la version amont est déjà chargée."""

    user_id: int | None = None
    """Utilisateur Nephos à attribuer au run (pour audit)."""

    dry_run: bool = False
    """Si vrai, n'écrit rien en base — affiche les compteurs estimés."""

    validate_after: bool = True
    """Exécute une validation SHACL Nephos Core après le `load`. Le résultat
    est ajouté en `notes` du `ImportResult`. Item E5-03 du backlog."""

    strict_validation: bool = False
    """Si vrai et `validate_after=True`, une violation SHACL bloque l'import :
    rollback de la transaction de chargement et `ImportValidationError`
    levée. Sinon, les violations sont consignées en notes mais n'arrêtent
    pas le pipeline."""

    detect_disappeared: bool = True
    """Marque en `deprecated` les concepts présents en base mais absents
    de la nouvelle version (E4-08). Effectif uniquement si l'importer
    déclare ses `target_scheme_codes()`. Les concepts avec
    `has_local_override = TRUE` sont préservés."""


class ImportRunner:
    """Orchestrateur générique d'imports."""

    def __init__(self, importer: Importer) -> None:
        self.importer = importer

    def run(self, options: RunOptions | None = None) -> ImportResult:
        """Exécute le pipeline complet et retourne le résultat.

        Lève `ImportError` (ou sous-classe) en cas d'échec ; le journal
        `gov.imports` est alors marqué `failed`.
        """
        opts = options or RunOptions()
        source_code = self.importer.source_code

        logger.info(
            "Démarrage d'import",
            extra={"source": source_code, "dry_run": opts.dry_run, "force": opts.force},
        )

        try:
            version = self.importer.discover_version()
        except Exception as exc:
            raise ImportSourceError(
                f"Impossible de découvrir la version de '{source_code}' : {exc}"
            ) from exc

        logger.info(
            "Version amont découverte",
            extra={"source": source_code, "version": version},
        )

        if opts.dry_run:
            return self._run_dry(version)

        # Étape transactionnelle : ouverture du journal + extract/transform/load.
        # En cas d'erreur, on rollback la transaction puis on persiste l'échec
        # dans gov.imports via une connexion autocommit séparée.
        try:
            with connect() as conn:
                entry = open_run(conn, source_code, version, opts.user_id)
                conn.commit()  # Garantit que le journal existe même si load échoue.

                logger.info(
                    "Journal ouvert",
                    extra={
                        "source": source_code,
                        "import_id": entry.import_id,
                        "version": version,
                    },
                )

                try:
                    raw = self.importer.extract()
                    entries = self.importer.transform(raw)
                    result = self.importer.load(conn, entries, version)
                    if opts.detect_disappeared:
                        result = self._mark_disappeared(conn, result, version)
                    if opts.validate_after:
                        result = self._run_validation(conn, result, strict=opts.strict_validation)
                    close_run(conn, entry, result)
                    conn.commit()
                except ImportValidationError as exc:
                    conn.rollback()
                    logger.exception(
                        "Validation SHACL post-import en échec, rollback effectué",
                        extra={"source": source_code, "import_id": entry.import_id},
                    )
                    self._record_failure(entry.import_id, str(exc))
                    raise
                except Exception as exc:
                    conn.rollback()
                    logger.exception(
                        "Échec du chargement, rollback effectué",
                        extra={"source": source_code, "import_id": entry.import_id},
                    )
                    self._record_failure(entry.import_id, str(exc))
                    raise ImportError(
                        f"Import '{source_code}' (version {version}) en échec : {exc}"
                    ) from exc

            logger.info(
                "Import terminé",
                extra={
                    "source": source_code,
                    "import_id": entry.import_id,
                    "version": version,
                    "creations": result.nb_creations,
                    "modifications": result.nb_modifications,
                    "skipped": result.nb_skipped,
                    "overrides_protected": result.nb_overrides_protected,
                },
            )
            return result
        except ImportError:
            raise
        except Exception as exc:
            raise ImportError(f"Erreur inattendue durant l'import '{source_code}' : {exc}") from exc

    def _run_dry(self, version: str) -> ImportResult:
        """Mode dry-run : extract + transform sans toucher à la base."""
        raw = self.importer.extract()
        entries = self.importer.transform(raw)
        return ImportResult(
            source_code=self.importer.source_code,
            version=version,
            nb_entites=len(entries),
            notes="dry-run — aucune écriture",
        )

    def _mark_disappeared(
        self,
        conn: psycopg.Connection,
        result: ImportResult,
        version: str,
    ) -> ImportResult:
        """Marque en `deprecated` les concepts disparus côté source (E4-08).

        No-op si l'importer ne déclare pas ses `target_scheme_codes`
        (cas par défaut sécuritaire — ex. ``QUDTUnitsImporter`` qui
        n'alimente pas ``vocab.concept``).
        """
        from nephos.etl.deprecation import _resolve_source_id, mark_disappeared_concepts

        scheme_codes = self.importer.target_scheme_codes()
        if scheme_codes is None:
            return result
        source_id = _resolve_source_id(conn, str(self.importer.source_code))
        nb = mark_disappeared_concepts(
            conn,
            source_id=source_id,
            current_version=version,
            scheme_codes=scheme_codes,
        )
        result.nb_deprecated_disappeared = nb
        if nb:
            suffix = f"{nb} concept(s) marqué(s) deprecated (disparus côté source)"
            result.notes = (result.notes + " | " + suffix) if result.notes else suffix
        return result

    def _run_validation(
        self,
        conn: psycopg.Connection,
        result: ImportResult,
        *,
        strict: bool,
    ) -> ImportResult:
        """Exécute la validation SHACL Nephos Core sur le résultat d'import.

        Imports tardifs (à l'intérieur de la fonction) pour éviter la
        dépendance circulaire `etl ↔ validators` au chargement du module.
        """
        from nephos.validators import SHACLValidator

        validator = SHACLValidator()
        report = validator.validate(conn)
        suffix = (
            f"SHACL : {report.violations} violation(s), "
            f"{report.warnings} warning(s) sur {report.concepts_validated} concept(s)"
        )
        result.notes = (result.notes + " | " + suffix) if result.notes else suffix
        if not report.conforms and strict:
            raise ImportValidationError(
                f"Validation SHACL en échec après import "
                f"({report.violations} violation(s)). Rollback du chargement."
            )
        return result

    def _record_failure(self, import_id: int, message: str) -> None:
        """Persiste l'échec dans gov.imports via une connexion autocommit
        indépendante (la transaction principale est déjà rollback-ée).
        """
        try:
            with connect(autocommit=True) as conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE gov.imports SET status = 'failed', notes = %s WHERE import_id = %s",
                    (message[:8000], import_id),
                )
        except Exception:
            logger.exception(
                "Échec de l'enregistrement du statut 'failed' dans gov.imports",
                extra={"import_id": import_id},
            )


__all__ = ["ImportRunner", "RunOptions"]
