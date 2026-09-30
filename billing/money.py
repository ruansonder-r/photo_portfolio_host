"""Money arithmetic and formatting.

Two rules hold everywhere in this app:

* Every amount is a ``Decimal``. A float never reaches the database.
* Rounding is ``ROUND_HALF_UP``. Python's default is ``ROUND_HALF_EVEN``,
  which rounds 2.345 to 2.34 -- it disagrees with every bank statement this
  gets reconciled against, and the disagreement is invisible until it isn't.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")

# A plain space, not a narrow or non-breaking one: it renders identically in
# every PDF viewer and every browser, with no encoding question.
THOUSANDS_SEP = " "

CURRENCY_SYMBOLS = {"ZAR": "R"}


def to_decimal(value) -> Decimal:
    """Coerce to Decimal, via str for floats so 0.1 stays 0.1."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return ZERO
    return Decimal(str(value))


def quantize(value) -> Decimal:
    """Round to cents, half away from zero."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def format_money(value, *, currency: str = "") -> str:
    """``9850`` -> ``9 850.00``; with ``currency="ZAR"`` -> ``R 9 850.00``.

    Always two decimals, always grouped. Right-aligned in a column of
    Helvetica -- whose digits are all 556/1000 em -- this puts every decimal
    point on the same axis with no font feature and no manual padding.
    """
    amount = quantize(value)
    sign = "-" if amount < 0 else ""
    whole, _, fraction = f"{abs(amount):.2f}".partition(".")

    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    grouped = THOUSANDS_SEP.join(groups)

    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    prefix = f"{symbol} " if symbol else ""
    return f"{prefix}{sign}{grouped}.{fraction}"


def format_quantity(value) -> str:
    """``1.00`` -> ``1``; ``1.50`` -> ``1.5``.

    A count of one should not print as ``1.00`` next to a price that does.
    """
    amount = quantize(value)
    text = f"{amount:f}".rstrip("0").rstrip(".")
    return text or "0"
