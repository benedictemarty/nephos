"""Importer WMO Codes Registry (E4-05).

Source : https://codes.wmo.int — registres de code lists publiés en
SKOS/Turtle par le WMO. Chaque code list est un ``reg:Register`` qui
agrège des ``skos:Concept`` (un concept = une valeur de code).

Approche : un importer générique paramétré par un *register* WMO
(URL Turtle) et un ``scheme_code`` cible Nephos. Chaque concept WMO
devient un ``vocab.concept`` Nephos avec :

- URI Nephos = ``{uri_base}/{scheme_code}/{notation}`` (ADR 0003) ;
- ``skos:notation`` = la valeur du code WMO ;
- ``rdfs:label@en`` du WMO → ``concept_label@en`` (kind=pref) ;
- ``concept_mapping`` ``exactMatch`` vers l'URI WMO d'origine.

Le scheme cible est créé localement (`status='approved'`) à la
première exécution, pas seedé.

Presets disponibles (CLI ``--code-list``) :

============================  ===============================================
Clé preset                    Code list WMO
============================  ===============================================
``bufr-0-02-001``             Type of station
``bufr-0-02-002``             Type of instrumentation for wind measurement
``bufr-0-02-003``             Type of measuring equipment used
``bufr-0-08-021``             Time significance
============================  ===============================================

Cf. backlog E4-05.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

import psycopg
import rdflib
from rdflib import URIRef
from rdflib.namespace import RDFS, SKOS

from nephos.config import get_settings
from nephos.etl.base import Importer, ImportResult, SourceCode
from nephos.etl.exceptions import ImportSourceError
from nephos.importers.cf import (
    _ensure_concept_in_scheme,
    _resolve_source_id,
    _upsert_pref_label_en,
)
from nephos.logging import get_logger

logger = get_logger(__name__)

DCT = rdflib.Namespace("http://purl.org/dc/terms/")
REG = rdflib.Namespace("http://purl.org/linked-data/registry#")


@dataclasses.dataclass(slots=True, frozen=True)
class WMOCodeListPreset:
    """Définition figée d'une code list WMO importée par Nephos."""

    key: str
    register_url: str
    scheme_code: str
    scheme_title: str


WMO_PRESETS: dict[str, WMOCodeListPreset] = {
    "bufr-0-02-001": WMOCodeListPreset(
        key="bufr-0-02-001",
        register_url="https://codes.wmo.int/bufr4/codeflag/0-02-001",
        scheme_code="wmo-bufr-0-02-001",
        scheme_title="WMO BUFR 0-02-001 — Type of station",
    ),
    "bufr-0-02-002": WMOCodeListPreset(
        key="bufr-0-02-002",
        register_url="https://codes.wmo.int/bufr4/codeflag/0-02-002",
        scheme_code="wmo-bufr-0-02-002",
        scheme_title="WMO BUFR 0-02-002 — Type of instrumentation for wind measurement",
    ),
    "bufr-0-02-003": WMOCodeListPreset(
        key="bufr-0-02-003",
        register_url="https://codes.wmo.int/bufr4/codeflag/0-02-003",
        scheme_code="wmo-bufr-0-02-003",
        scheme_title="WMO BUFR 0-02-003 — Type of measuring equipment used",
    ),
    "bufr-0-08-021": WMOCodeListPreset(
        key="bufr-0-08-021",
        register_url="https://codes.wmo.int/bufr4/codeflag/0-08-021",
        scheme_code="wmo-bufr-0-08-021",
        scheme_title="WMO BUFR 0-08-021 — Time significance",
    ),
}


@dataclasses.dataclass(slots=True, frozen=True)
class WMOCodeEntry:
    """Représentation d'un concept WMO extrait d'un register."""

    wmo_uri: str
    notation: str
    pref_label_en: str | None


class WMOCodesImporter(Importer):
    """Importer paramétrable pour une code list WMO (un register)."""

    source_code: SourceCode = SourceCode("WMO_CODES")
    source_format: str = "RDF/SKOS (Turtle)"

    def __init__(
        self,
        *,
        register_url: str | Path,
        scheme_code: str,
        scheme_title: str,
    ) -> None:
        self._register_url: str | Path = register_url
        self._scheme_code = scheme_code
        self._scheme_title = scheme_title
        self._cached_graph: rdflib.Graph | None = None
        self._register_uri: URIRef | None = None

    @classmethod
    def from_preset(cls, key: str) -> WMOCodesImporter:
        """Construit un importer à partir d'un preset WMO connu (cf. ``WMO_PRESETS``)."""
        if key not in WMO_PRESETS:
            raise ValueError(f"Preset WMO inconnu : {key!r}. Choix : {sorted(WMO_PRESETS)}")
        preset = WMO_PRESETS[key]
        return cls(
            register_url=preset.register_url,
            scheme_code=preset.scheme_code,
            scheme_title=preset.scheme_title,
        )

    def discover_version(self) -> str:
        """Retourne ``dct:modified`` du register WMO (ou ``"unknown"`` si absent)."""
        graph = self._fetch()
        register = self._find_register(graph)
        modified = graph.value(register, DCT.modified)
        if modified:
            return str(modified)
        return "unknown"

    def extract(self) -> object:
        """Extrait la liste des ``skos:Concept`` membres directs du register."""
        graph = self._fetch()
        register = self._find_register(graph)
        return list(_iter_concepts(graph, register))

    def transform(self, raw: object) -> list[dict[str, object]]:
        """Normalise les entrées WMO en payload prêt pour ``load`` (URI Nephos, label EN)."""
        entries = cast("list[WMOCodeEntry]", raw)
        return [
            {
                "wmo_uri": e.wmo_uri,
                "notation": e.notation,
                "uri": self._build_uri(e.notation),
                "pref_label_en": e.pref_label_en or e.notation,
            }
            for e in entries
        ]

    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        """Upsert idempotent des concepts, labels, scheme et `exactMatch` WMO."""
        source_id = _resolve_source_id(conn, self.source_code)
        scheme_id = _ensure_wmo_scheme(
            conn, self._build_scheme_uri(), self._scheme_code, self._scheme_title
        )

        nb_creations = 0
        nb_modifications = 0
        nb_skipped = 0
        nb_overrides = 0

        for entry in entries:
            uri = cast("str", entry["uri"])
            notation = cast("str", entry["notation"])
            pref_label = cast("str", entry["pref_label_en"])
            wmo_uri = cast("str", entry["wmo_uri"])

            outcome, concept_id = _upsert_concept(conn, uri, notation, version, source_id)
            if outcome == "created":
                nb_creations += 1
            elif outcome == "skipped":
                nb_skipped += 1
            elif outcome == "override":
                nb_overrides += 1
                continue
            else:
                nb_modifications += 1

            _upsert_pref_label_en(conn, concept_id, pref_label)
            _ensure_concept_in_scheme(conn, concept_id, scheme_id)
            _upsert_wmo_mapping(conn, concept_id, source_id, wmo_uri)

        return ImportResult(
            source_code=self.source_code,
            version=version,
            nb_entites=len(entries),
            nb_creations=nb_creations,
            nb_modifications=nb_modifications,
            nb_skipped=nb_skipped,
            nb_overrides_protected=nb_overrides,
            notes=f"register={self._register_url} scheme={self._scheme_code}",
        )

    def _fetch(self) -> rdflib.Graph:
        """Parse le register Turtle (URL ou fichier) en mémoire (memoïsé)."""
        if self._cached_graph is not None:
            return self._cached_graph
        graph = rdflib.Graph()
        try:
            graph.parse(source=str(self._register_url), format="turtle")
        except Exception as exc:
            raise ImportSourceError(
                f"Impossible de parser le register WMO {self._register_url} : {exc}"
            ) from exc
        self._cached_graph = graph
        return graph

    def _find_register(self, graph: rdflib.Graph) -> URIRef:
        """Localise l'URI du ``reg:Register`` racine dans le graphe."""
        if self._register_uri is not None:
            return self._register_uri
        for subj in graph.subjects(rdflib.RDF.type, REG.Register):
            if isinstance(subj, URIRef):
                self._register_uri = subj
                return subj
        raise ImportSourceError(f"Aucun reg:Register trouvé dans le graphe {self._register_url}.")

    def _build_uri(self, notation: str) -> str:
        """Construit l'URI Nephos d'un concept (cf. ADR 0003)."""
        base = get_settings().uri_base.rstrip("/")
        return f"{base}/{self._scheme_code}/{notation}"

    def _build_scheme_uri(self) -> str:
        """Construit l'URI Nephos du scheme cible."""
        base = get_settings().uri_base.rstrip("/")
        return f"{base}/{self._scheme_code}"


def _iter_concepts(graph: rdflib.Graph, register: URIRef) -> list[WMOCodeEntry]:
    """Extrait les ``skos:Concept`` membres directs du register."""
    entries: list[WMOCodeEntry] = []
    seen: set[str] = set()
    for concept_uri in graph.subjects(rdflib.RDF.type, SKOS.Concept):
        if not isinstance(concept_uri, URIRef):
            continue
        uri_str = str(concept_uri)
        if not uri_str.startswith(str(register)):
            continue
        if uri_str in seen:
            continue
        seen.add(uri_str)

        notation_lit = graph.value(concept_uri, SKOS.notation)
        if notation_lit is None:
            continue
        label = _pick_label_en(graph, concept_uri)
        entries.append(
            WMOCodeEntry(
                wmo_uri=uri_str,
                notation=str(notation_lit).strip(),
                pref_label_en=label,
            )
        )
    return entries


def _pick_label_en(graph: rdflib.Graph, subject: URIRef) -> str | None:
    """Retourne `rdfs:label@en` ou `skos:prefLabel@en`, sinon le premier label."""
    candidates: list[rdflib.Literal] = []
    for predicate in (RDFS.label, SKOS.prefLabel):
        for value in graph.objects(subject, predicate):
            if isinstance(value, rdflib.Literal):
                candidates.append(value)
    for lit in candidates:
        if lit.language == "en":
            return str(lit)
    if candidates:
        return str(candidates[0])
    return None


def _upsert_concept(
    conn: psycopg.Connection,
    uri: str,
    notation: str,
    version: str,
    source_id: int,
) -> tuple[str, int]:
    """Crée ou met à jour un concept WMO ; retourne (outcome, concept_id).

    Identique en logique au helper du CF Area Type : INSERT/UPDATE qui
    renseignent ``import_source_id`` pour que ``gov.v_imports_status``
    compte correctement les concepts par source.
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


def _ensure_wmo_scheme(
    conn: psycopg.Connection, scheme_uri: str, scheme_code: str, scheme_title: str
) -> int:
    """Crée le scheme local s'il n'existe pas, retourne son ``scheme_id``."""
    with conn.cursor() as cur:
        cur.execute("SELECT scheme_id FROM vocab.scheme WHERE uri = %s", (scheme_uri,))
        row = cur.fetchone()
        if row is not None:
            return int(row[0])
        cur.execute(
            """
            INSERT INTO vocab.scheme (uri, code, title, description, status)
            VALUES (%s, %s, %s, %s, 'approved')
            RETURNING scheme_id
            """,
            (
                scheme_uri,
                scheme_code,
                scheme_title,
                "Code list WMO importée depuis le WMO Codes Registry (E4-05).",
            ),
        )
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def _upsert_wmo_mapping(
    conn: psycopg.Connection, concept_id: int, source_id: int, target_uri: str
) -> None:
    """Pose un `exactMatch` du concept Nephos vers l'URI WMO d'origine."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vocab.concept_mapping
              (concept_id, target_source_id, target_uri, mapping_relation)
            VALUES (%s, %s, %s, 'exactMatch')
            ON CONFLICT (concept_id, target_uri, mapping_relation) DO NOTHING
            """,
            (concept_id, source_id, target_uri),
        )
