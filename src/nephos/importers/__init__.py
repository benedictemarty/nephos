"""Importers concrets pour les sources standards Nephos.

Chaque sous-module spécialise la classe `Importer` du framework ETL
(`nephos.etl.base`) pour une source amont :

- `cf` : CF Standard Names (XML)
- `cf_area_type` : CF Area Type Table (XML)
- `qudt_units` : QUDT Units (Turtle)
- `wmo_codes` : WMO Code Registry (Turtle, paramétrable par code list)
- (à venir) `cf_cell`, `ecmwf`, `nerc`
"""

from nephos.importers.cf import CFStandardNamesImporter
from nephos.importers.cf_area_type import CFAreaTypeImporter
from nephos.importers.qudt_units import QUDTUnitsImporter
from nephos.importers.wmo_codes import WMO_PRESETS, WMOCodesImporter

__all__ = [
    "WMO_PRESETS",
    "CFAreaTypeImporter",
    "CFStandardNamesImporter",
    "QUDTUnitsImporter",
    "WMOCodesImporter",
]
