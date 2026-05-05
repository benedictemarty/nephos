"""Validateurs Nephos.

Couverts au niveau de cet item (E5-01) : validation SHACL des concepts
du référentiel contre les shapes Nephos Core.

À venir : validation de fichiers externes consommateurs (GRIB,
NetCDF-CF, BUFR — cf. EPIC E10 / ADR 0010).
"""

from nephos.validators.shacl_runner import (
    SHACLValidationReport,
    SHACLValidator,
    ValidationOutcome,
)

__all__ = ["SHACLValidationReport", "SHACLValidator", "ValidationOutcome"]
