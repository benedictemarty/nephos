"""Mappings ECMWF Parameter Database (E4-06).

**Alignement par mapping seul, pas de clone** : Nephos n'importe pas
les paramètres ECMWF en tant que concepts. On pose simplement des
``concept_mapping closeMatch`` depuis les concepts ``grandeurs-cf``
existants vers une URL filtrée du ECMWF Parameter Database
(https://codes.ecmwf.int/grib/param-db/) qui présente les paramètres
ECMWF correspondant au triplet GRIB2.

Source d'alignement : ``cfName.def`` du dépôt
`ecmwf/eccodes <https://github.com/ecmwf/eccodes>`_ (Apache 2.0). Ce
fichier mappe chaque CF Standard Name vers ses clés GRIB2
canoniques :

```
#Temperature
'air_temperature' = {
   discipline = 0 ;
   parameterCategory = 0 ;
   parameterNumber = 0 ;
}
```

Pour chaque CF name présent dans ``cfName.def`` ET présent en base
sous le scheme ``grandeurs-cf``, on pose un mapping :

- ``mapping_relation = 'closeMatch'`` (le triplet GRIB2 peut désigner
  plusieurs ids ECMWF en présence de qualificatifs additionnels :
  ``typeOfStatisticalProcessing``, ``typeOfFirstFixedSurface`` —
  cette V1 ne discrimine pas).
- ``target_uri =
  https://codes.ecmwf.int/grib/param-db/?discipline=D&parameterCategory=C&parameterNumber=N``.
- ``target_source_id = ECMWF_PARAMS``.

Le compteur ``ImportResult.nb_creations`` reflète le nombre de
mappings effectivement insérés (idempotent : les rejouer ne crée
pas de doublons grâce à la contrainte
``(concept_id, target_uri, mapping_relation)``).
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import psycopg
import requests

from nephos.etl.base import Importer, ImportResult, SourceCode
from nephos.etl.exceptions import ImportSourceError
from nephos.logging import get_logger

logger = get_logger(__name__)

ECCODES_CFNAME_URL = (
    "https://raw.githubusercontent.com/ecmwf/eccodes/develop/definitions/grib2/cfName.def"
)
ECMWF_PARAM_DB_BASE = "https://codes.ecmwf.int/grib/param-db/"


_ENTRY_HEAD = re.compile(r"^'(?P<name>[a-zA-Z0-9_]+)'\s*=\s*\{")
_KEY_LINE = re.compile(r"^\s*(?P<key>[a-zA-Z]+)\s*=\s*(?P<val>-?\d+)\s*;")


@dataclasses.dataclass(slots=True, frozen=True)
class CFGribKeys:
    """Mapping CF name → triplet GRIB2 + qualificatifs optionnels."""

    cf_name: str
    discipline: int
    parameter_category: int
    parameter_number: int
    extra: tuple[tuple[str, int], ...] = ()


class ECMWFMappingsImporter(Importer):
    """Pose des `closeMatch` CF → ECMWF Parameter Database via cfName.def."""

    source_code: SourceCode = SourceCode("ECMWF_PARAMS")
    source_format: str = "ecCodes cfName.def"

    def __init__(self, source: str | Path | None = None) -> None:
        self._source: str | Path = source if source is not None else ECCODES_CFNAME_URL
        self._cached_payload: bytes | None = None

    def discover_version(self) -> str:
        """Hash MD5 du contenu de `cfName.def` — sert de version stable."""
        payload = self._fetch()
        digest = hashlib.md5(payload, usedforsecurity=False).hexdigest()
        return digest[:12]

    def extract(self) -> object:
        payload = self._fetch()
        return list(_iter_entries(payload.decode("utf-8")))

    def transform(self, raw: object) -> list[dict[str, object]]:
        entries = cast("list[CFGribKeys]", raw)
        return [
            {
                "cf_name": e.cf_name,
                "target_uri": _build_ecmwf_url(
                    e.discipline, e.parameter_category, e.parameter_number
                ),
                "discipline": e.discipline,
                "parameter_category": e.parameter_category,
                "parameter_number": e.parameter_number,
                "qualifiers": dict(e.extra) if e.extra else None,
            }
            for e in entries
        ]

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        source_id = _resolve_source_id(conn, self.source_code)
        nb_creations = 0
        nb_skipped = 0
        nb_unmatched = 0

        for entry in entries:
            cf_name = cast("str", entry["cf_name"])
            target_uri = cast("str", entry["target_uri"])
            concept_id = _find_cf_concept(conn, cf_name)
            if concept_id is None:
                nb_unmatched += 1
                continue
            outcome = _upsert_mapping(conn, concept_id, source_id, target_uri)
            if outcome == "created":
                nb_creations += 1
            else:
                nb_skipped += 1

        notes = (
            f"{nb_unmatched} CF name(s) de cfName.def absent(s) du scheme grandeurs-cf"
            if nb_unmatched
            else None
        )
        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=len(entries),
            nb_creations=nb_creations,
            nb_modifications=0,
            nb_skipped=nb_skipped,
            nb_overrides_protected=0,
            notes=notes,
        )

    def _fetch(self) -> bytes:
        """Charge `cfName.def` depuis la source (URL ou fichier local), memoïsé."""
        if self._cached_payload is not None:
            return self._cached_payload
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
        if not payload.strip():
            raise ImportSourceError(f"cfName.def vide depuis {self._source}.")
        self._cached_payload = payload
        return payload


def _iter_entries(text: str) -> Iterator[CFGribKeys]:
    """Parse `cfName.def` ; yield un ``CFGribKeys`` par bloc."""
    current_name: str | None = None
    current_keys: dict[str, int] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        head_match = _ENTRY_HEAD.match(line)
        if head_match:
            current_name = head_match.group("name")
            current_keys = {}
            continue
        if current_name is None:
            continue
        if line.strip() == "}":
            entry = _build_entry(current_name, current_keys)
            if entry is not None:
                yield entry
            current_name = None
            current_keys = {}
            continue
        key_match = _KEY_LINE.match(line)
        if key_match:
            current_keys[key_match.group("key")] = int(key_match.group("val"))


def _build_entry(name: str, keys: dict[str, int]) -> CFGribKeys | None:
    if not all(k in keys for k in ("discipline", "parameterCategory", "parameterNumber")):
        return None
    extra = tuple(
        (k, v)
        for k, v in keys.items()
        if k not in {"discipline", "parameterCategory", "parameterNumber"}
    )
    return CFGribKeys(
        cf_name=name,
        discipline=keys["discipline"],
        parameter_category=keys["parameterCategory"],
        parameter_number=keys["parameterNumber"],
        extra=extra,
    )


def _build_ecmwf_url(discipline: int, parameter_category: int, parameter_number: int) -> str:
    return (
        f"{ECMWF_PARAM_DB_BASE}"
        f"?discipline={discipline}"
        f"&parameterCategory={parameter_category}"
        f"&parameterNumber={parameter_number}"
    )


def _resolve_source_id(conn: psycopg.Connection, source_code: SourceCode) -> int:
    """Retourne l'``import_source_id`` numérique pour ce code de source."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT import_source_id FROM gov.import_sources WHERE code = %s",
            (source_code,),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"Source d'import '{source_code}' non déclarée.")
    return int(row[0])


def _find_cf_concept(conn: psycopg.Connection, cf_name: str) -> int | None:
    """Localise le concept CF correspondant à ``cf_name`` (notation lower-case)."""
    notation = cf_name.lower()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT c.concept_id FROM vocab.concept c "
            "JOIN vocab.concept_in_scheme cis ON cis.concept_id = c.concept_id "
            "JOIN vocab.scheme s ON s.scheme_id = cis.scheme_id "
            "WHERE c.notation = %s AND s.code = 'grandeurs-cf' "
            "LIMIT 1",
            (notation,),
        )
        row = cur.fetchone()
    return int(row[0]) if row else None


def _upsert_mapping(
    conn: psycopg.Connection, concept_id: int, source_id: int, target_uri: str
) -> str:
    """Insère un closeMatch ; retourne ``"created"`` ou ``"skipped"``."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept_mapping
              (concept_id, target_source_id, target_uri, mapping_relation)
            VALUES (%s, %s, %s, 'closeMatch')
            ON CONFLICT (concept_id, target_uri, mapping_relation) DO NOTHING
            RETURNING mapping_id
            """,
            (concept_id, source_id, target_uri),
        )
        row = cur.fetchone()
    return "created" if row is not None else "skipped"
