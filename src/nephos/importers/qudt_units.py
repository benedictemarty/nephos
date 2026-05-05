"""Importer QUDT Units.

Source : https://qudt.org/2.1/vocab/unit (Turtle, ~2.4 MB).

Chaque ressource ``?u a qudt:Unit`` du graphe QUDT alimente la table
``vocab.unite`` :

- ``qudt_uri`` ← URI QUDT (par ex. ``http://qudt.org/vocab/unit/K``).
- ``symbole`` ← ``qudt:symbol`` (par ex. ``"K"``).
- ``nom``     ← ``rdfs:label`` (premier label en EN si disponible, sinon brut).
- ``grandeur``← liste des ``qudt:hasQuantityKind`` jointe par virgules
  (par ex. ``"Temperature, ThermodynamicTemperature"``).
- ``facteur_conversion``  ← ``qudt:conversionMultiplier``.
- ``offset_conversion``   ← ``qudt:conversionOffset`` (si présent).
- ``est_si_canonique``    ← ``True`` si ``qudt:applicableSystem sou:SI``
                            ET ``qudt:conversionMultiplier == 1``
                            ET pas d'offset.

Idempotence : par ``qudt_uri``. Une unité existante avec le même
``qudt_uri`` est mise à jour ; sinon, un rapprochement par ``symbole``
identique tente d'enrichir une unité préexistante (par ex. unités
seed importées par d'autres voies). Sinon nouvel INSERT.

Les collisions de ``symbole`` (deux unités QUDT avec le même symbole)
sont traitées comme une erreur de qualité QUDT et loggées.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

import psycopg
import rdflib
from rdflib import URIRef
from rdflib.namespace import RDFS

from nephos.etl.base import Importer, ImportResult, SourceCode
from nephos.etl.exceptions import ImportSourceError
from nephos.logging import get_logger

logger = get_logger(__name__)

QUDT_DEFAULT_URL = "https://qudt.org/2.1/vocab/unit"

# Namespaces QUDT (déclarés à plat — rdflib n'a pas de NS standard pour QUDT)
QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")
QUDT_UNIT = rdflib.Namespace("http://qudt.org/vocab/unit/")
SOU = rdflib.Namespace("http://qudt.org/vocab/sou/")
DCTERMS = rdflib.Namespace("http://purl.org/dc/terms/")


@dataclasses.dataclass(slots=True, frozen=True)
class QUDTUnit:
    """Représentation normalisée d'une unité QUDT extraite du graphe."""

    qudt_uri: str
    symbol: str
    label: str | None
    description: str | None
    conversion_multiplier: float | None
    conversion_offset: float | None
    applicable_systems: tuple[str, ...]
    quantity_kinds: tuple[str, ...]


class QUDTUnitsImporter(Importer):
    """Importer pour les unités QUDT depuis le vocabulaire Turtle officiel."""

    source_code: SourceCode = SourceCode("QUDT_UNIT")
    source_format: str = "OWL/RDF (Turtle)"

    def __init__(self, source: str | Path | None = None) -> None:
        self._source: str | Path = source if source is not None else QUDT_DEFAULT_URL
        self._cached_graph: rdflib.Graph | None = None

    # ------------------------------------------------------------------
    # Étapes du framework ETL
    # ------------------------------------------------------------------

    def discover_version(self) -> str:
        graph = self._fetch()
        # Le label de l'ontologie a la forme « QUDT VOCAB Units of Measure Release 2.1.47 ».
        ontology_uri = URIRef("http://qudt.org/2.1/vocab/unit")
        label = graph.value(ontology_uri, RDFS.label)
        if label:
            return _extract_version_from_label(str(label))
        return "unknown"

    def extract(self) -> object:
        graph = self._fetch()
        return list(_iter_units(graph))

    def transform(self, raw: object) -> list[dict[str, object]]:
        units = cast("list[QUDTUnit]", raw)
        return [
            {
                "qudt_uri": u.qudt_uri,
                "symbol": u.symbol,
                "label": u.label or u.symbol,
                "description": u.description,
                "conversion_multiplier": u.conversion_multiplier,
                "conversion_offset": u.conversion_offset,
                "is_si_canonical": _is_si_canonical(u),
                "quantity_kinds": ", ".join(u.quantity_kinds) or None,
            }
            for u in units
        ]

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        source_id = _resolve_source_id(conn, self.source_code)
        nb_creations = 0
        nb_modifications = 0
        nb_skipped = 0
        nb_overrides = 0
        symbol_collisions: list[str] = []

        for entry in entries:
            qudt_uri = cast("str", entry["qudt_uri"])
            symbol = cast("str", entry["symbol"])
            outcome = _upsert_unit(conn, entry, version, source_id)
            if outcome == "created":
                nb_creations += 1
            elif outcome == "updated":
                nb_modifications += 1
            elif outcome == "skipped":
                nb_skipped += 1
            elif outcome == "override":
                nb_overrides += 1
            elif outcome == "symbol_collision":
                symbol_collisions.append(f"{symbol} ({qudt_uri})")

        if symbol_collisions:
            logger.warning(
                "Collisions de symbole QUDT — unités ignorées",
                extra={"count": len(symbol_collisions), "samples": symbol_collisions[:10]},
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
                f"{len(symbol_collisions)} collision(s) de symbole — ignorées"
                if symbol_collisions
                else None
            ),
        )

    # ------------------------------------------------------------------
    # Helpers privés
    # ------------------------------------------------------------------

    def _fetch(self) -> rdflib.Graph:
        if self._cached_graph is not None:
            return self._cached_graph
        graph = rdflib.Graph()
        try:
            if isinstance(self._source, Path):
                graph.parse(source=str(self._source), format="turtle")
            else:
                # rdflib gère HTTP + content negotiation pour les URL.
                graph.parse(source=str(self._source), format="turtle")
        except Exception as exc:
            raise ImportSourceError(
                f"Impossible de parser le graphe QUDT depuis {self._source} : {exc}"
            ) from exc
        self._cached_graph = graph
        return graph


# ----------------------------------------------------------------------
# Parsing RDF
# ----------------------------------------------------------------------


def _iter_units(graph: rdflib.Graph) -> list[QUDTUnit]:
    """Extrait toutes les ressources `qudt:Unit` du graphe."""
    units: list[QUDTUnit] = []
    qudt_unit_class = QUDT["Unit"]
    for unit_uri in graph.subjects(rdflib.RDF.type, qudt_unit_class):
        if not isinstance(unit_uri, URIRef):
            continue
        symbol_lit = graph.value(unit_uri, QUDT["symbol"])
        if not symbol_lit:
            continue
        label_lit = _pick_label(graph, unit_uri)
        description_lit = graph.value(unit_uri, DCTERMS.description)
        mult_lit = graph.value(unit_uri, QUDT["conversionMultiplier"])
        offset_lit = graph.value(unit_uri, QUDT["conversionOffset"])

        applicable_systems = tuple(
            str(s) for s in graph.objects(unit_uri, QUDT["applicableSystem"])
        )
        quantity_kinds = tuple(
            _local_name(str(qk)) for qk in graph.objects(unit_uri, QUDT["hasQuantityKind"])
        )

        units.append(
            QUDTUnit(
                qudt_uri=str(unit_uri),
                symbol=str(symbol_lit),
                label=str(label_lit) if label_lit else None,
                description=(str(description_lit).strip() or None) if description_lit else None,
                conversion_multiplier=float(mult_lit) if mult_lit is not None else None,
                conversion_offset=float(offset_lit) if offset_lit is not None else None,
                applicable_systems=applicable_systems,
                quantity_kinds=quantity_kinds,
            )
        )
    return units


def _pick_label(graph: rdflib.Graph, subject: URIRef) -> rdflib.term.Node | None:
    """Préfère un `rdfs:label` en `en`, sinon le premier disponible."""
    labels = list(graph.objects(subject, RDFS.label))
    for label in labels:
        if isinstance(label, rdflib.Literal) and label.language == "en":
            return label
    return labels[0] if labels else None


def _local_name(uri: str) -> str:
    return uri.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _extract_version_from_label(label: str) -> str:
    """Extrait la version d'un label QUDT du type
    « QUDT VOCAB Units of Measure Release 2.1.47 ».
    """
    parts = label.split()
    if parts and parts[-1].replace(".", "").isdigit():
        return parts[-1]
    return label.strip() or "unknown"


def _is_si_canonical(u: QUDTUnit) -> bool:
    """Heuristique : SI canonique ssi applicableSystem inclut SI,
    multiplicateur == 1 (ou None) et offset == 0 (ou None).
    """
    in_si = any(s.endswith("/SI") for s in u.applicable_systems)
    mult_ok = u.conversion_multiplier in (None, 1.0)
    offset_ok = u.conversion_offset in (None, 0.0)
    return in_si and mult_ok and offset_ok


# ----------------------------------------------------------------------
# Helpers SQL
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


def _upsert_unit(
    conn: psycopg.Connection,
    entry: dict[str, object],
    version: str,
    source_id: int,
) -> str:
    """Crée ou met à jour une unité ; retourne l'outcome.

    `outcome` ∈ {"created", "updated", "skipped", "override", "symbol_collision"}.
    """
    qudt_uri = cast("str", entry["qudt_uri"])
    symbol = cast("str", entry["symbol"])
    label = cast("str", entry["label"])
    grandeur = cast("str | None", entry["quantity_kinds"])
    multiplier = cast("float | None", entry["conversion_multiplier"])
    offset_v = cast("float | None", entry["conversion_offset"])
    is_si = cast("bool", entry["is_si_canonical"])

    with conn.cursor() as cur:
        # 1. Match strict par qudt_uri
        cur.execute(
            "SELECT unite_id, has_local_override FROM vocab.unite WHERE qudt_uri = %s",
            (qudt_uri,),
        )
        match_uri = cur.fetchone()
        if match_uri is not None:
            unit_id, has_override = match_uri
            if has_override:
                return "override"
            cur.execute(
                """
                UPDATE vocab.unite SET
                  symbole = %s, nom = %s, grandeur = %s,
                  facteur_conversion = %s, offset_conversion = %s,
                  est_si_canonique = %s,
                  import_source_id = %s, import_version = %s, last_synced_at = now()
                WHERE unite_id = %s
                """,
                (symbol, label, grandeur, multiplier, offset_v, is_si, source_id, version, unit_id),
            )
            return "updated"

        # 2. Pas de match URI : tente un rapprochement par symbole
        cur.execute(
            "SELECT unite_id, has_local_override, qudt_uri FROM vocab.unite WHERE symbole = %s",
            (symbol,),
        )
        match_sym = cur.fetchone()
        if match_sym is not None:
            unit_id, has_override, existing_qudt = match_sym
            if has_override:
                return "override"
            if existing_qudt and existing_qudt != qudt_uri:
                # Une autre QUDT URI a déjà ce symbole → collision.
                return "symbol_collision"
            cur.execute(
                """
                UPDATE vocab.unite SET
                  qudt_uri = %s, nom = %s, grandeur = %s,
                  facteur_conversion = %s, offset_conversion = %s,
                  est_si_canonique = %s,
                  import_source_id = %s, import_version = %s, last_synced_at = now()
                WHERE unite_id = %s
                """,
                (
                    qudt_uri,
                    label,
                    grandeur,
                    multiplier,
                    offset_v,
                    is_si,
                    source_id,
                    version,
                    unit_id,
                ),
            )
            return "updated"

        # 3. Nouvelle insertion
        try:
            cur.execute(
                """
                INSERT INTO vocab.unite
                  (symbole, nom, grandeur, qudt_uri,
                   facteur_conversion, offset_conversion, est_si_canonique,
                   status, import_source_id, import_version, last_synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved', %s, %s, now())
                """,
                (
                    symbol,
                    label,
                    grandeur,
                    qudt_uri,
                    multiplier,
                    offset_v,
                    is_si,
                    source_id,
                    version,
                ),
            )
            return "created"
        except psycopg.errors.UniqueViolation:
            # Symbole déjà pris par une unité sans qudt_uri (rare) — collision.
            conn.rollback()
            return "symbol_collision"
