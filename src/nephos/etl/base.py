"""Interface `Importer` et types partagés du framework ETL.

Convention de nommage : `SourceCode` désigne le code court d'une source
externe tel qu'inscrit dans `gov.import_sources` (par exemple `"CF"`,
`"QUDT_UNIT"`, `"WMO_CODES"`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import NewType

import psycopg

SourceCode = NewType("SourceCode", str)


@dataclass(slots=True)
class ImportResult:
    """Compteurs renvoyés par un import et persistés dans `gov.imports`."""

    source_code: SourceCode
    version: str
    nb_entites: int = 0
    nb_creations: int = 0
    nb_modifications: int = 0
    nb_skipped: int = 0
    nb_overrides_protected: int = 0
    nb_deprecated_disappeared: int = 0
    """Concepts marqués `deprecated` parce qu'absents de la nouvelle
    version source (E4-08). Toujours `0` quand l'importer ne supporte
    pas la détection (cf. `Importer.target_scheme_codes`)."""

    notes: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


class Importer(ABC):
    """Interface qu'une source externe doit implémenter pour s'intégrer
    au pipeline ETL Nephos.

    Le cycle de vie d'un import est :

      1. ``self.extract(conn)``   — récupération brute (HTTP, SPARQL, fichier).
      2. ``self.transform(...)``  — normalisation vers le modèle SKOS.
      3. ``self.load(conn, ...)`` — écriture en base avec idempotence
         et respect de ``has_local_override``.

    L'orchestration (journal `gov.imports`, gestion d'erreurs, log)
    est portée par `ImportRunner`.

    Les implémentations sont attendues idempotentes : rejouer un import
    ne doit pas créer de doublons. La clé d'identité côté source est
    son URI ; côté base, elle est portée par ``concept.uri``.
    """

    #: Code de la source amont, doit correspondre à une ligne de
    #: ``gov.import_sources``.
    source_code: SourceCode

    #: Format / mime-type humain documentant la source. Indicatif.
    source_format: str

    @abstractmethod
    def discover_version(self) -> str:
        """Retourne la version (étiquette ou hash) de la source amont
        actuellement disponible.

        Doit pouvoir être appelée sans déclencher un import complet —
        sert au pré-check de re-sync (a-t-on déjà cette version ?).
        """

    @abstractmethod
    def extract(self) -> object:
        """Récupère les données brutes depuis la source amont.

        Le type de retour est laissé à l'implémentation (XML parsé,
        graphe RDF, JSON, etc.) et passé tel quel à ``transform``.
        """

    @abstractmethod
    def transform(self, raw: object) -> list[dict[str, object]]:
        """Normalise les données extraites en entrées prêtes pour le
        chargement.

        Chaque entrée est un dictionnaire dont la structure est
        spécifique à la source (voir les sous-classes), mais doit au
        minimum porter une clé ``uri`` qui identifie le concept côté
        Nephos.
        """

    def target_scheme_codes(self) -> tuple[str, ...] | None:
        """Liste des codes de schemes que cet importer alimente.

        Sert à la détection automatique des concepts disparus côté
        source (E4-08) : après le ``load``, le runner passe en
        ``status='deprecated'`` les concepts encore en base sous ces
        schemes mais qui n'ont **pas** été touchés à la version
        importée (i.e. ``import_version`` resté à une ancienne valeur,
        et ``has_local_override = FALSE``).

        Retourne ``None`` (défaut) pour désactiver la détection — le
        cas par défaut sécuritaire pour les sources qui n'alimentent
        pas ``vocab.concept`` (par ex. ``QUDTUnitsImporter`` qui touche
        ``vocab.unite``) ou pour les imports partiels où on ne peut
        pas raisonner sur l'exhaustivité.
        """
        return None

    @abstractmethod
    def load(
        self,
        conn: psycopg.Connection,
        entries: list[dict[str, object]],
        version: str,
    ) -> ImportResult:
        """Écrit les entrées en base de manière idempotente.

        Doit incrémenter les compteurs `nb_creations`, `nb_modifications`,
        `nb_skipped`, `nb_overrides_protected` selon le cas, et retourner
        un `ImportResult`.

        Conventions :
        - ``nb_creations``           : entrée absente en base, insérée.
        - ``nb_modifications``       : entrée présente, mise à jour
                                       (et `has_local_override = false`).
        - ``nb_skipped``             : entrée déjà à jour, aucune écriture.
        - ``nb_overrides_protected`` : entrée existante avec
                                       ``has_local_override = true`` —
                                       l'amont est ignoré pour préserver
                                       la modification locale.
        """
