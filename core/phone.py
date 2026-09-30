"""Phone-number normalisation, shared by the site chrome and the PDF renderer.

The old invoice printed `828139850` because the number was stored as bare
digits and rendered as-is. One helper, used everywhere a number is displayed.
"""

from __future__ import annotations

import re

# South Africa. The only country this site invoices from.
COUNTRY_CODE = "27"
NATIONAL_LENGTH = 9  # digits after the leading 0 / country code


def digits_only(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def to_international_digits(raw: str) -> str:
    """Normalise to country-code-prefixed digits, e.g. ``27828139850``.

    Accepts ``+27 82 813 9850``, ``082 813 9850`` and the bare ``828139850``
    that the Google Docs invoice was storing.
    """
    digits = digits_only(raw)
    if not digits:
        return ""
    if digits.startswith(COUNTRY_CODE) and len(digits) == len(COUNTRY_CODE) + NATIONAL_LENGTH:
        return digits
    if digits.startswith("0") and len(digits) == NATIONAL_LENGTH + 1:
        return COUNTRY_CODE + digits[1:]
    if len(digits) == NATIONAL_LENGTH:
        return COUNTRY_CODE + digits
    return digits


def format_za(raw: str) -> str:
    """``828139850`` -> ``+27 82 813 9850``.

    Anything that does not look like a South African number is returned
    unchanged rather than mangled into a plausible-looking wrong number.
    """
    digits = to_international_digits(raw)
    if len(digits) != len(COUNTRY_CODE) + NATIONAL_LENGTH:
        return (raw or "").strip()
    national = digits[len(COUNTRY_CODE):]
    return f"+{COUNTRY_CODE} {national[:2]} {national[2:5]} {national[5:]}"
