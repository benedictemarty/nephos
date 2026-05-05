"""Importers concrets pour les sources standards Nephos.

Chaque sous-module spécialise la classe `Importer` du framework ETL
(`nephos.etl.base`) pour une source amont :

- `cf` : CF Standard Names (XML)
- (à venir) `cf_cell`, `qudt`, `wmo`, `ecmwf`, `nerc`
"""

from nephos.importers.cf import CFStandardNamesImporter

__all__ = ["CFStandardNamesImporter"]
