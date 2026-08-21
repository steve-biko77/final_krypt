"""Filtres de template dédiés aux emails (identité visuelle) — formatage des
montants « à la française » (séparateur de milliers par espace), cohérent
avec ``frontend/lib/amountConverter.ts`` (``formatXaf``) et
``frontend/app/.../transfer/[id]/page.tsx`` (``formatEUR``/``formatXAF``),
qui utilisent toutes deux ``toLocaleString('fr-FR')``.

Aucun utilitaire Python équivalent n'existait déjà dans le backend (vérifié :
``receipt_generator.py``/``tracfin_report_generator.py`` interpolent le
montant brut sans formatage). Celui-ci reste volontairement simple — pas de
dépendance au module ``locale`` (état process-global, à éviter dans un
serveur applicatif) — pour un besoin aussi ponctuel.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def _group_thousands_fr(digits: str) -> str:
    """Insère un espace tous les 3 chiffres depuis la droite."""
    reversed_digits = digits[::-1]
    groups = [reversed_digits[i:i + 3] for i in range(0, len(reversed_digits), 3)]
    return " ".join(groups)[::-1]


@register.filter
def format_xaf(value) -> str:
    """FCFA : entier arrondi, séparateur de milliers, jamais de décimale —
    même convention que ``formatXaf``/``formatXAF`` côté frontend."""
    try:
        n = int(Decimal(str(value)).to_integral_value(rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    sign = "-" if n < 0 else ""
    return f"{sign}{_group_thousands_fr(str(abs(n)))}"


@register.filter
def format_eur(value) -> str:
    """EUR : toujours 2 décimales, séparateur de milliers, virgule décimale —
    même convention que ``formatEUR`` côté frontend."""
    try:
        n = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    sign = "-" if n < 0 else ""
    integer_part, _, decimal_part = f"{abs(n):.2f}".partition(".")
    return f"{sign}{_group_thousands_fr(integer_part)},{decimal_part}"
