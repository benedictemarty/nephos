"""Importer CF Standard Names.

Source : https://cfconventions.org/Data/cf-standard-names/current/src/cf-standard-name-table.xml

Chaque `<entry id="..."/>` du XML CF devient un concept Nephos avec :

- URI : ``https://w3id.org/nephos/vocab/grandeurs-cf/{notation}``
- ``notation`` : l'identifiant CF tel quel (par ex. ``air_temperature``).
- ``concept_label`` (``pref``, ``en``) : ``id.replace('_', ' ')`` (par ex. ``air temperature``).
- ``concept_note`` (``definition``, ``en``) : contenu de ``<description>``.
- ``concept_in_scheme`` : appartenance au scheme ``grandeurs-cf`` (créé si absent).
- ``concept_mapping`` (``exactMatch``) : pointe vers la fiche CF officielle
  (``https://cfconventions.org/Data/cf-standard-names/{version}/build/cf-standard-name-table.html#{id}``).
- ``concept_physical`` : ``value_type = scalar``, ``cf_standard_name = id``,
  ``unit_canonical_id`` résolu depuis ``vocab.unite.symbole`` quand possible.

Statut initial : ``approved`` (les concepts ont au moins un ``prefLabel@en``).
Le passage à ``published`` requiert l'ajout d'un ``prefLabel@fr`` (cf. ADR 0004).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Iterator
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
from nephos.importers._unit_symbols import normalize_cf_to_qudt
from nephos.logging import get_logger

logger = get_logger(__name__)

CF_DEFAULT_URL = (
    "https://cfconventions.org/Data/cf-standard-names/current/src/cf-standard-name-table.xml"
)
CF_SCHEME_CODE = "grandeurs-cf"
CF_SCHEME_TITLE = "CF Standard Names — grandeurs physiques"


@dataclasses.dataclass(slots=True, frozen=True)
class CFEntry:
    """Représentation normalisée d'une `<entry>` CF.

    `notation` est l'identifiant CF brut. `pref_label_en` est sa forme
    « humaine » (underscores → espaces). `canonical_units_raw` reste tel
    qu'écrit en CF (ex. ``"m s-1"``) — la résolution vers `vocab.unite`
    est laissée à `load`.
    """

    notation: str
    pref_label_en: str
    description: str | None
    canonical_units_raw: str | None


class CFStandardNamesImporter(Importer):
    """Importer pour les CF Standard Names depuis l'XML officiel.

    L'instance peut être configurée pour télécharger depuis l'URL CF
    officielle (par défaut) ou lire un fichier XML local — utile pour les
    tests d'intégration et le développement déconnecté.

    Le contenu XML est téléchargé une fois lors du premier accès et mis
    en cache sur l'instance, pour servir à la fois `discover_version` et
    `extract`.
    """

    source_code: SourceCode = SourceCode("CF")
    source_format: str = "XML"

    def __init__(self, source: str | Path | None = None) -> None:
        self._source: str | Path = source if source is not None else CF_DEFAULT_URL
        self._cached_root: etree._Element | None = None

    # ------------------------------------------------------------------
    # Étapes du framework ETL
    # ------------------------------------------------------------------

    def discover_version(self) -> str:
        root = self._fetch()
        version = root.findtext("version_number")
        if not version:
            raise ImportSourceError("Élément <version_number> absent du fichier CF Standard Names.")
        return str(version).strip()

    def extract(self) -> object:
        root = self._fetch()
        return list(_iter_entries(root))

    def transform(self, raw: object) -> list[dict[str, object]]:
        # Normalisation des notations en minuscules pour respecter ADR 0003
        # (URI Nephos minuscules). L'identifiant CF original (qui peut contenir
        # des majuscules pour les isotopes — ex. `13C`, `18O`) est conservé
        # dans `cf_standard_name` côté `concept_physical`, et dans l'URI cible
        # du mapping. Les pref-labels humanisés conservent la casse originale.
        entries = cast("list[CFEntry]", raw)
        return [
            {
                "notation": e.notation.lower(),
                "uri": self._build_uri(e.notation.lower()),
                "pref_label_en": e.pref_label_en,
                "description": e.description,
                "canonical_units_raw": e.canonical_units_raw,
                "cf_target_uri": self._build_cf_target_uri(e.notation),
                "cf_standard_name": e.notation,
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
        scheme_id = _ensure_cf_scheme(conn, self._build_scheme_uri())

        nb_creations = 0
        nb_modifications = 0
        nb_skipped = 0
        nb_overrides = 0
        units_unresolved: list[str] = []

        for entry in entries:
            notation = cast("str", entry["notation"])
            uri = cast("str", entry["uri"])
            pref_label = cast("str", entry["pref_label_en"])
            description = cast("str | None", entry["description"])
            cf_target_uri = cast("str", entry["cf_target_uri"])
            units_raw = cast("str | None", entry["canonical_units_raw"])
            cf_standard_name = cast("str", entry["cf_standard_name"])

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
            unit_id = _resolve_unit(conn, units_raw) if units_raw else None
            if units_raw and unit_id is None:
                units_unresolved.append(units_raw)
            _upsert_concept_physical(conn, concept_id, unit_id, cf_standard_name)

        if units_unresolved:
            logger.warning(
                "Unités CF non résolues vers vocab.unite",
                extra={
                    "count": len(units_unresolved),
                    "samples": list(set(units_unresolved))[:10],
                },
            )

        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=len(entries),
            nb_creations=nb_creations,
            nb_modifications=nb_modifications,
            nb_skipped=nb_skipped,
            nb_overrides_protected=nb_overrides,
            notes=(
                f"{len(units_unresolved)} unité(s) CF non résolue(s) vers vocab.unite"
                if units_unresolved
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Helpers privés
    # ------------------------------------------------------------------

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

        # Parsing sécurisé via defusedxml : protection contre XXE,
        # billion laughs, expansion d'entités externes, etc. On valide
        # d'abord avec defusedxml ; si OK, on reparse avec lxml pour
        # bénéficier de son API riche (find/findtext/iter sur Element).
        try:
            DET.fromstring(payload)  # nosec B320 — defusedxml protège des attaques XML
            root = etree.fromstring(payload)  # nosec B320 — déjà validé par defusedxml
        except (etree.XMLSyntaxError, DET.ParseError) as exc:
            raise ImportSourceError(f"XML CF invalide depuis {self._source} : {exc}") from exc
        self._cached_root = root
        return root

    def _build_uri(self, notation: str) -> str:
        base = get_settings().uri_base.rstrip("/")
        return f"{base}/{CF_SCHEME_CODE}/{notation}"

    def _build_scheme_uri(self) -> str:
        base = get_settings().uri_base.rstrip("/")
        return f"{base}/{CF_SCHEME_CODE}"

    @staticmethod
    def _build_cf_target_uri(notation: str) -> str:
        return (
            "https://cfconventions.org/Data/cf-standard-names/current/build/"
            f"cf-standard-name-table.html#{notation}"
        )


# ----------------------------------------------------------------------
# Parsing XML
# ----------------------------------------------------------------------


def _iter_entries(root: etree._Element) -> Iterator[CFEntry]:
    for entry_elt in root.iter("entry"):
        notation = entry_elt.get("id")
        if not notation:
            continue
        canonical_units = entry_elt.findtext("canonical_units")
        description = entry_elt.findtext("description")
        yield CFEntry(
            notation=notation,
            pref_label_en=notation.replace("_", " "),
            description=(description or "").strip() or None,
            canonical_units_raw=(canonical_units or "").strip() or None,
        )


# ----------------------------------------------------------------------
# Helpers SQL — petits, lisibles, idempotents.
# ----------------------------------------------------------------------


def _resolve_source_id(conn: psycopg.Connection, source_code: SourceCode) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT import_source_id FROM gov.import_sources WHERE code = %s",
            (source_code,),
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"Source d'import '{source_code}' non déclarée dans gov.import_sources.")
    return int(row[0])


def _ensure_cf_scheme(conn: psycopg.Connection, scheme_uri: str) -> int:
    """Crée le scheme `grandeurs-cf` s'il n'existe pas, retourne son id."""
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
                CF_SCHEME_CODE,
                CF_SCHEME_TITLE,
                "Scheme local hébergeant les concepts importés depuis CF Standard Names.",
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _upsert_concept(
    conn: psycopg.Connection,
    uri: str,
    notation: str,
    version: str,
    source_id: int,
) -> tuple[str, int]:
    """Crée ou met à jour un concept ; retourne (outcome, concept_id).

    `outcome` ∈ {"created", "updated", "skipped", "override"} :
      - "created"   : nouvelle ligne insérée (avec ``import_source_id``).
      - "updated"   : ligne existante, ``import_version`` et ``import_source_id``
                      mis à jour.
      - "skipped"   : ligne existante, déjà à la bonne version.
      - "override"  : `has_local_override = TRUE`, on ne touche à rien.
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
                """
                INSERT INTO vocab.concept
                  (uri, notation, status, import_source_id, import_version, last_synced_at)
                VALUES (%s, %s, 'approved', %s, %s, now())
                RETURNING concept_id
                """,
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


def _upsert_pref_label_en(conn: psycopg.Connection, concept_id: int, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept_label (concept_id, lang, kind, value)
            VALUES (%s, 'en', 'pref', %s)
            ON CONFLICT (concept_id, lang) WHERE kind = 'pref'
            DO UPDATE SET value = EXCLUDED.value
            """,
            (concept_id, value),
        )


def _upsert_definition_en(conn: psycopg.Connection, concept_id: int, value: str) -> None:
    """Insère la définition EN si absente, met à jour sinon."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT concept_note_id FROM vocab.concept_note
            WHERE concept_id = %s AND lang = 'en' AND kind = 'definition'
            """,
            (concept_id,),
        )
        existing = cur.fetchone()
        if existing is None:
            cur.execute(
                """
                INSERT INTO vocab.concept_note (concept_id, lang, kind, value)
                VALUES (%s, 'en', 'definition', %s)
                """,
                (concept_id, value),
            )
        else:
            cur.execute(
                "UPDATE vocab.concept_note SET value = %s WHERE concept_note_id = %s",
                (value, existing[0]),
            )


def _ensure_concept_in_scheme(conn: psycopg.Connection, concept_id: int, scheme_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept_in_scheme (concept_id, scheme_id, is_top_concept)
            VALUES (%s, %s, FALSE)
            ON CONFLICT (concept_id, scheme_id) DO NOTHING
            """,
            (concept_id, scheme_id),
        )


def _upsert_cf_mapping(
    conn: psycopg.Connection, concept_id: int, cf_source_id: int, target_uri: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept_mapping
              (concept_id, target_source_id, target_uri, mapping_relation)
            VALUES (%s, %s, %s, 'exactMatch')
            ON CONFLICT (concept_id, target_uri, mapping_relation) DO NOTHING
            """,
            (concept_id, cf_source_id, target_uri),
        )


def _resolve_unit(conn: psycopg.Connection, units_raw: str) -> int | None:
    """Retourne l'`unite_id` pour un symbole CF, ou None si non résolu.

    Tentative dans l'ordre :
      1. Symbole CF brut.
      2. Symbole CF → notation QUDT (cf. `_unit_symbols.normalize_cf_to_qudt`).
      3. Variante sans espaces.
      4. Variante avec `/` à la place des espaces.

    La normalisation CF → QUDT (étape 2) couvre les cas composés
    (``m s-1``, ``kg m-2 s-1``…) et est responsable de la majeure
    partie du gain de résolution observé après import QUDT.
    """
    candidates: Iterable[str] = (
        units_raw,
        normalize_cf_to_qudt(units_raw),
        units_raw.replace(" ", ""),
        units_raw.replace(" ", "/"),
    )
    seen: set[str] = set()
    with conn.cursor() as cur:
        for cand in candidates:
            if cand in seen:
                continue
            seen.add(cand)
            cur.execute("SELECT unite_id FROM vocab.unite WHERE symbole = %s", (cand,))
            row = cur.fetchone()
            if row is not None:
                return int(row[0])
    return None


def _upsert_concept_physical(
    conn: psycopg.Connection,
    concept_id: int,
    unit_id: int | None,
    cf_standard_name: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept_physical
              (concept_id, value_type, unit_canonical_id, cf_standard_name)
            VALUES (%s, 'scalar', %s, %s)
            ON CONFLICT (concept_id) DO UPDATE SET
              unit_canonical_id = COALESCE(EXCLUDED.unit_canonical_id, vocab.concept_physical.unit_canonical_id),
              cf_standard_name = EXCLUDED.cf_standard_name
            """,
            (concept_id, unit_id, cf_standard_name),
        )
