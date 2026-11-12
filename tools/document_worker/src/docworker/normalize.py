"""Exact typed normalization of amounts, dates and currencies.

Rules: Decimal only (never float arithmetic), signed integer minor units serialized as strings,
explicit status for every value, and no guessing. A value whose meaning depends on an
undeclared or contradictory convention is reported as ``ambiguous`` with a null value.
"""

from __future__ import annotations

import datetime as _dt
import re
from decimal import Decimal, InvalidOperation

# ISO 4217 minor-unit exponents for the currencies Part A recognises. Unlisted codes are
# kept as codes but their amounts cannot be converted to minor units (status unknown_currency).
CURRENCY_EXPONENTS = {
    "AUD": 2, "BHD": 3, "CAD": 2, "CHF": 2, "CNY": 2, "EUR": 2, "GBP": 2, "INR": 2,
    "JPY": 0, "KRW": 0, "KWD": 3, "MXN": 2, "NZD": 2, "SEK": 2, "SGD": 2, "USD": 2,
}

KNOWN = "known"
MISSING = "missing"
AMBIGUOUS = "ambiguous"
INVALID = "invalid"
UNKNOWN_CURRENCY = "unknown_currency"
PRECISION = "precision_exceeds_currency"
FORMULA_NO_VALUE = "formula_without_cached_value"

_SYMBOLS = "$€£¥₹"
_NUMBER = re.compile(r"^[0-9][0-9.,]*$")


def classify_separators(token: str) -> str | None:
    """Decimal-style evidence carried by one numeric token: 'dot', 'comma', 'ambiguous' or None.

    None means the token has no separators. 'ambiguous' means a single separator followed by
    exactly three digits (1,234 or 1.234), whose meaning depends on the convention.
    """
    dots, commas = token.count("."), token.count(",")
    if dots == 0 and commas == 0:
        return None
    if dots and commas:
        return "dot" if token.rfind(".") > token.rfind(",") else "comma"
    sep = "." if dots else ","
    if token.count(sep) > 1:  # repeated separator can only be grouping
        return "comma" if sep == "." else "dot"
    tail = token.rsplit(sep, 1)[1]
    if len(tail) == 3:
        return "ambiguous"
    return "dot" if sep == "." else "comma"


def _strip_amount(raw: str) -> tuple[str, int, str | None] | None:
    """Return (numeric token, sign, symbol) or None when the text is not a plain amount."""
    text = raw.strip().replace(" ", "").replace(" ", "")
    sign = 1
    symbol = None
    if text.startswith("(") and text.endswith(")"):
        sign, text = -1, text[1:-1]
    if text.startswith(("-", "+")):
        sign, text = (-sign if text[0] == "-" else sign), text[1:]
    if text and text[0] in _SYMBOLS:
        symbol, text = text[0], text[1:]
    elif text and text[-1] in _SYMBOLS:
        symbol, text = text[-1], text[:-1]
    if text.startswith(("-", "+")) and sign == 1:  # $-12.00
        sign, text = (-1 if text[0] == "-" else 1), text[1:]
    if not _NUMBER.match(text):
        return None
    return text, sign, symbol


def _valid_grouping(integer_part: str, group_sep: str) -> bool:
    if group_sep not in integer_part:
        return True
    groups = integer_part.split(group_sep)
    return 1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])


def text_amount_style(raw: str) -> str | None:
    stripped = _strip_amount(raw)
    return classify_separators(stripped[0]) if stripped else None


def parse_text_amount(raw: str, style: str) -> tuple[Decimal | None, str]:
    """Parse a text amount using an effective style ('dot' | 'comma' | 'unknown')."""
    if raw is None or raw.strip() == "":
        return None, MISSING
    stripped = _strip_amount(raw)
    if stripped is None:
        return None, INVALID
    token, sign, _symbol = stripped
    readings = {s: _read_token(token, s) for s in ("dot", "comma")}
    if readings["dot"] is None and readings["comma"] is None:
        return None, INVALID  # malformed under every convention
    evidence = classify_separators(token)
    if evidence is not None and style == "unknown":
        return None, AMBIGUOUS
    if evidence in ("dot", "comma") and evidence != style:
        return None, AMBIGUOUS  # contradicts the declared/document convention
    # Under an unknown convention only separator-free tokens reach here; both readings agree.
    value = readings["dot"] if style == "unknown" else readings.get(style)
    if value is None:
        return None, INVALID
    return value * sign, KNOWN


def _read_token(token: str, style: str) -> Decimal | None:
    """The token's value under one convention, or None when it is malformed under it."""
    decimal_sep, group_sep = (".", ",") if style == "dot" else (",", ".")
    if token.count(decimal_sep) > 1:
        return None
    if decimal_sep in token:
        integer_part, fraction = token.split(decimal_sep)
    else:
        integer_part, fraction = token, ""
    if not integer_part or not _valid_grouping(integer_part, group_sep):
        return None
    digits = integer_part.replace(group_sep, "")
    if not digits.isdigit() or (fraction and not fraction.isdigit()):
        return None
    try:
        return Decimal(f"{digits}.{fraction}" if fraction else digits)
    except InvalidOperation:
        return None


def decimal_from_cell_number(value) -> Decimal:
    """Exact decimal of a spreadsheet number: ints exactly, floats by shortest round-trip repr.

    A binary float such as 0.30000000000000004 stays exactly that, so currency precision
    checks reject it rather than silently rounding.
    """
    if isinstance(value, bool):
        raise TypeError("boolean is not an amount")
    if isinstance(value, int):
        return Decimal(value)
    return Decimal(repr(float(value)))


def to_minor_units(value: Decimal | None, currency: str | None) -> tuple[str | None, int | None,
                                                                          str]:
    """(minor-unit integer string, exponent, status) for a known decimal value."""
    if value is None:
        return None, None, MISSING
    if currency is None:
        return None, None, UNKNOWN_CURRENCY
    exponent = CURRENCY_EXPONENTS.get(currency)
    if exponent is None:
        return None, None, UNKNOWN_CURRENCY
    scaled = value.scaleb(exponent)
    if scaled != scaled.to_integral_value():
        return None, exponent, PRECISION
    return str(int(scaled)), exponent, KNOWN


_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_SLASH_DATE = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$")


def parse_text_date(raw: str | None, date_order: str) -> tuple[str | None, str]:
    if raw is None or raw.strip() == "":
        return None, MISSING
    text = raw.strip()
    match = _ISO_DATE.match(text)
    try:
        if match:
            y, m, d = (int(g) for g in match.groups())
            return _dt.date(y, m, d).isoformat(), KNOWN
        match = _SLASH_DATE.match(text)
        if match:
            if date_order == "iso_only":
                return None, AMBIGUOUS
            a, b, y = (int(g) for g in match.groups())
            d, m = (a, b) if date_order == "dmy" else (b, a)
            return _dt.date(y, m, d).isoformat(), KNOWN
    except ValueError:
        return None, INVALID
    return None, INVALID


def normalize_currency(raw: str | None) -> tuple[str | None, str]:
    if raw is None or str(raw).strip() == "":
        return None, MISSING
    code = str(raw).strip().upper()
    if len(code) != 3 or not code.isalpha():
        return None, INVALID
    return code, KNOWN if code in CURRENCY_EXPONENTS else UNKNOWN_CURRENCY
