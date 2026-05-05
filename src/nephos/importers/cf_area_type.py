"""Importer CF Area Type Table.

Source : https://cfconventions.org/Data/area-type-table/current/src/area-type-table.xml

Vocabulaire CF complémentaire qui décrit des **types de surfaces**
référencés par les concepts CF (par ex. ``land``, ``sea_ice``,
``broadleaf_deciduous_trees``). Structure XML très proche de CF
Standard Names :

```xml
<area_type_table>
  <version_number>13</version_number>
  <entry id="air">
    <description>The area type of "air" ...</description>
  </entry>
  ...
</area_type_table>
```

Différences avec ``CFStandardNamesImporter`` :

- élément racine ``<area_type_table>`` au lieu de ``<standard_name_table>``,
- pas de ``<canonical_units>`` ni de ``<grib>`` / ``<amip>``,
- scheme cible distinct : ``area-types-cf``.

Le typage physique (``concept_physical``) n'est pas posé : ce ne sont
pas des grandeurs mesurables.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import defusedxml.ElementTree as DET
import psycopg
import requests
from lxml import etree  # nosec B410 — parsing fait après validation par defusedxml dans _fetch

from nephos.config import get_settings
from nephos.etl.base import Importer, ImportResult, SourceCode
from nephos.etl.exceptions import ImportSourceError
from nephos.importers.cf import (
    _ensure_concept_in_scheme,
    _resolve_source_id,
    _upsert_cf_mapping,
    _upsert_definition_en,
    _upsert_pref_label_en,
)
from nephos.logging import get_logger

logger = get_logger(__name__)

CF_AREA_DEFAULT_URL = (
    "https://cfconventions.org/Data/area-type-table/current/src/area-type-table.xml"
)
CF_AREA_SCHEME_CODE = "area-types-cf"
CF_AREA_SCHEME_TITLE = "CF Area Type Table — types de surfaces"
CF_AREA_TARGET_BASE = (
    "https://cfconventions.org/Data/area-type-table/current/build/area-type-table.html"
)


@dataclasses.dataclass(slots=True, frozen=True)
class CFAreaEntry:
    """Représentation d'une entry CF Area Type."""

    notation: str
    pref_label_en: str
    description: str | None


class CFAreaTypeImporter(Importer):
    """Importer pour CF Area Type Table — concepts de surfaces."""

    source_code: SourceCode = SourceCode("CF_AREA")
    source_format: str = "XML"

    def __init__(self, source: str | Path | None = None) -> None:
        self._source: str | Path = source if source is not None else CF_AREA_DEFAULT_URL
        self._cached_root: etree._Element | None = None

    def discover_version(self) -> str:
        root = self._fetch()
        version = root.findtext("version_number")
        if not version:
            raise ImportSourceError(
                "Élément <version_number> absent du fichier CF Area Type Table."
            )
        return str(version).strip()

    def extract(self) -> object:
        root = self._fetch()
        return list(_iter_entries(root))

    def transform(self, raw: object) -> list[dict[str, object]]:
        entries = cast("list[CFAreaEntry]", raw)
        return [
            {
                "notation": e.notation.lower(),
                "uri": self._build_uri(e.notation.lower()),
                "pref_label_en": e.pref_label_en,
                "description": e.description,
                "cf_target_uri": f"{CF_AREA_TARGET_BASE}#{e.notation}",
            }
            for e in entries
        ]

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        cf_source_id = _resolve_source_id(conn, self.source_code)
        scheme_id = _ensure_area_scheme(conn, self._build_scheme_uri())

        nb_creations = 0
        nb_modifications = 0
        nb_skipped = 0
        nb_overrides = 0

        for entry in entries:
            notation = cast("str", entry["notation"])
            uri = cast("str", entry["uri"])
            pref_label = cast("str", entry["pref_label_en"])
            description = cast("str | None", entry["description"])
            cf_target_uri = cast("str", entry["cf_target_uri"])

            outcome, concept_id = _upsert_concept(conn, uri, notation, version, cf_source_id)
            if outcome == "created":
                nb_creations += 1
            elif outcome == "skipped":
                nb_skipped += 1
            elif outcome == "override":
                nb_overrides += 1
                continue
            else:  # "updated"
                nb_modifications += 1

            _upsert_pref_label_en(conn, concept_id, pref_label)
            if description:
                _upsert_definition_en(conn, concept_id, description)
            _ensure_concept_in_scheme(conn, concept_id, scheme_id)
            _upsert_cf_mapping(conn, concept_id, cf_source_id, cf_target_uri)

        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=len(entries),
            nb_creations=nb_creations,
            nb_modifications=nb_modifications,
            nb_skipped=nb_skipped,
            nb_overrides_protected=nb_overrides,
        )

    def _fetch(self) -> etree._Element:
        if self._cached_root is not None:
            return self._cached_root
        if isinstance(self._source, Path):
            payload = self._source.read_bytes()
        else:
            parsed = urlparse(self._source)
            if parsed.scheme in ("http", "https"):
                response = requests.get(self._source, timeout=60)
                response.raise_for_status()
                payload = response.content
            else:
                payload = Path(self._source).read_bytes()

        try:
            DET.fromstring(payload)  # nosec B320 — validation defusedxml
            root = etree.fromstring(payload)  # nosec B320 — payload validé
        except (etree.XMLSyntaxError, DET.ParseError) as exc:
            raise ImportSourceError(
                f"XML CF Area Type invalide depuis {self._source} : {exc}"
            ) from exc
        self._cached_root = root
        return root

    def _build_uri(self, notation: str) -> str:
        base = get_settings().uri_base.rstrip("/")
        return f"{base}/{CF_AREA_SCHEME_CODE}/{notation}"

    def _build_scheme_uri(self) -> str:
        base = get_settings().uri_base.rstrip("/")
        return f"{base}/{CF_AREA_SCHEME_CODE}"


def _iter_entries(root: etree._Element) -> Iterator[CFAreaEntry]:
    for entry_elt in root.iter("entry"):
        notation = entry_elt.get("id")
        if not notation:
            continue
        description = entry_elt.findtext("description")
        yield CFAreaEntry(
            notation=notation,
            pref_label_en=notation.replace("_", " "),
            description=(description or "").strip() or None,
        )


def _upsert_concept(
    conn: psycopg.Connection,
    uri: str,
    notation: str,
    version: str,
    source_id: int,
) -> tuple[str, int]:
    """Crée ou met à jour un concept Area Type ; retourne (outcome, concept_id).

    Variante locale du `_upsert_concept` du CF importer, qui renseigne
    explicitement `import_source_id` à l'INSERT et à l'UPDATE pour que
    la vue `gov.v_imports_status` compte correctement les concepts par
    source.

    `outcome` ∈ {"created", "updated", "skipped", "override"}.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT concept_id, import_version, has_local_override "
            "FROM vocab.concept WHERE uri = %s",
            (uri,),
        )
        existing = cur.fetchone()
        if existing is None:
            cur.execute(
                "INSERT INTO vocab.concept "
                "(uri, notation, status, import_source_id, import_version, last_synced_at) "
                "VALUES (%s, %s, 'approved', %s, %s, now()) RETURNING concept_id",
                (uri, notation, source_id, version),
            )
            row = cur.fetchone()
            assert row is not None
            return ("created", int(row[0]))

        concept_id, current_version, has_override = existing
        if has_override:
            return ("override", int(concept_id))
        if str(current_version) == version:
            cur.execute(
                "UPDATE vocab.concept SET last_synced_at = now() WHERE concept_id = %s",
                (concept_id,),
            )
            return ("skipped", int(concept_id))
        cur.execute(
            "UPDATE vocab.concept SET import_source_id = %s, import_version = %s, "
            "last_synced_at = now() WHERE concept_id = %s",
            (source_id, version, concept_id),
        )
        return ("updated", int(concept_id))


def _ensure_area_scheme(conn: psycopg.Connection, scheme_uri: str) -> int:
    """Crée le scheme `area-types-cf` s'il n'existe pas, retourne son id."""
    with conn.cursor() as cur:
        cur.execute("SELECT scheme_id FROM vocab.scheme WHERE uri = %s", (scheme_uri,))
        row = cur.fetchone()
        if row is not None:
            return int(row[0])
        cur.execute(
            """
            INSERT INTO vocab.scheme (uri, code, title, description, status)
            VALUES (%s, %s, %s, %s, 'published')
            RETURNING scheme_id
            """,
            (
                scheme_uri,
                CF_AREA_SCHEME_CODE,
                CF_AREA_SCHEME_TITLE,
                "Scheme local hébergeant les types de surfaces CF importés.",
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])
