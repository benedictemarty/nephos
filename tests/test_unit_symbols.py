"""Tests unitaires de `nephos.importers._unit_symbols.normalize_cf_to_qudt`.

Pas de dépendance Postgres — pur calcul de chaînes.
"""

from __future__ import annotations

import pytest

from nephos.importers._unit_symbols import normalize_cf_to_qudt


@pytest.mark.parametrize(
    ("cf_input", "expected_qudt"),
    [
        # Cas triviaux
        ("K", "K"),
        ("Pa", "Pa"),
        ("m", "m"),
        ("1", "1"),
        ("", ""),
        # Inverses simples
        ("m s-1", "m/s"),
        ("kg m-2", "kg/m²"),
        ("W m-2", "W/m²"),
        ("mol m-3", "mol/m³"),
        # Inverses multiples (parenthèses)
        ("kg m-2 s-1", "kg/(m²·s)"),
        ("W m-2 K-1", "W/(m²·K)"),
        # Exposants positifs au numérateur
        ("m2 s-2", "m²/s²"),
        ("m2", "m²"),
        # Mixte numérateur multiple
        ("kg m s-2", "kg·m/s²"),
        # Pourcent et degré (caractères spéciaux acceptés)
        ("%", "%"),
        ("°C", "°C"),
        # Token non-parsable → rendu tel quel
        ("foo bar~~~", "foo bar~~~"),
    ],
)
def test_normalize_cf_to_qudt(cf_input: str, expected_qudt: str) -> None:
    assert normalize_cf_to_qudt(cf_input) == expected_qudt


def test_normalize_is_idempotent_on_qudt_already() -> None:
    """Une notation déjà QUDT-style (avec `/`, `²`) sort impactée par les
    règles : c'est attendu (la fonction n'est PAS un round-trip QUDT→QUDT).
    Le test documente le comportement, pas un invariant.
    """
    # Une chaîne déjà avec `/` ne match pas le token regex → rendue telle quelle.
    assert normalize_cf_to_qudt("m/s") == "m/s"
