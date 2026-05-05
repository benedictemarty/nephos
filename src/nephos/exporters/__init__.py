"""Exporters Nephos — produisent le référentiel sous forme RDF/SKOS.

Couvert au niveau de cet item (E6-01) : export en Turtle d'un scheme
complet ou de l'ensemble du référentiel, avec attribution licences
(CC-BY 4.0 sur les données originales, ADR 0005) et préservation
de l'attribution amont (`dcterms:source`).
"""

from nephos.exporters.skos import SKOSExporter

__all__ = ["SKOSExporter"]
