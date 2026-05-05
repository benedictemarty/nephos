"""Normalisation des symboles d'unité CF → QUDT.

CF Conventions et QUDT n'écrivent pas les unités composées avec la même
notation :

============== =====================================
CF             QUDT (qudt:symbol)
============== =====================================
``m s-1``      ``m/s``
``m s-2``      ``m/s²``
``kg m-2``     ``kg/m²``
``kg m-2 s-1`` ``kg/(m²·s)``
``W m-2``      ``W/m²``
``mol m-3``    ``mol/m³``
``K``          ``K`` (identique)
``1``          ``1`` (identique)
============== =====================================

Ce module fournit `normalize_cf_to_qudt` qui convertit la notation CF
(tokens séparés par espaces, exposants signés sans `^`) vers la
convention QUDT (numérateur ``a·b`` / dénominateur, exposants Unicode).

Couvre l'item E4-04b du backlog.
"""

from __future__ import annotations

import re

# Token CF : un identifiant de base (lettres / chiffres / `%` / `°` / `_`)
# éventuellement suivi d'un exposant entier signé.
_CF_TOKEN = re.compile(r"^([A-Za-z%°_]+|[0-9])(-?\d+)?$")

_SUPERSCRIPTS = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "-": "⁻",
}


def normalize_cf_to_qudt(cf_symbol: str) -> str:
    """Convertit un symbole CF en sa notation QUDT équivalente.

    Si la chaîne ne peut pas être parsée selon les règles CF, elle est
    rendue inchangée — la résolution dans `_resolve_unit` traitera ce
    cas comme une non-correspondance.

    Notations supportées :
    - tokens séparés par espaces : ``"m s-1"`` → ``"m/s"``.
    - exposants positifs : ``"m2 s-2"`` → ``"m²/s²"``.
    - dénominateur multiple : ``"kg m-2 s-1"`` → ``"kg/(m²·s)"``.
    - cas trivial ``"1"`` (sans dimension) inchangé.
    - tokens uniques sans exposant : ``"K"`` inchangé.
    """
    if not cf_symbol or cf_symbol == "1":
        return cf_symbol

    tokens = cf_symbol.strip().split()
    numerator: list[str] = []
    denominator: list[str] = []

    for tok in tokens:
        match = _CF_TOKEN.match(tok)
        if not match:
            return cf_symbol  # impossible à parser → rendu tel quel
        base, exp = match.group(1), match.group(2)
        if exp is None or exp == "1":
            numerator.append(base)
        elif exp == "-1":
            denominator.append(base)
        elif exp.startswith("-"):
            denominator.append(f"{base}{_to_superscript(exp[1:])}")
        else:
            numerator.append(f"{base}{_to_superscript(exp)}")

    num_str = "·".join(numerator) if numerator else "1"
    if not denominator:
        return num_str
    den_str = "·".join(denominator)
    if len(denominator) > 1 or "·" in den_str:
        return f"{num_str}/({den_str})"
    return f"{num_str}/{den_str}"


def _to_superscript(digits: str) -> str:
    return "".join(_SUPERSCRIPTS.get(c, c) for c in digits)
