from decimal import Decimal

import pytest

from docworker import normalize as nz


@pytest.mark.parametrize("token,style", [
    ("1234", None), ("1,234.56", "dot"), ("1.234,56", "comma"), ("1,234", "ambiguous"),
    ("1.234", "ambiguous"), ("12.5", "dot"), ("12,5", "comma"), ("1,234,567", "dot"),
    ("1.234.567", "comma"), ("0.30", "dot"),
])
def test_separator_evidence(token, style):
    assert nz.classify_separators(token) == style


@pytest.mark.parametrize("raw,style,value,status", [
    ("1,234.56", "dot", "1234.56", nz.KNOWN),
    ("1.234,56", "comma", "1234.56", nz.KNOWN),
    ("1.234,56", "dot", None, nz.AMBIGUOUS),
    ("1,234.56", "unknown", None, nz.AMBIGUOUS),
    ("-7", "unknown", "-7", nz.KNOWN),
    ("(12.50)", "dot", "-12.50", nz.KNOWN),
    ("$-3.10", "dot", "-3.10", nz.KNOWN),
    ("€1.000,00", "comma", "1000.00", nz.KNOWN),
    ("12,34,567.00", "dot", None, nz.INVALID),
    ("1.2.3", "dot", None, nz.INVALID),
    ("12 CR", "dot", None, nz.INVALID),
    ("", "dot", None, nz.MISSING),
    ("abc", "dot", None, nz.INVALID),
])
def test_parse_text_amount(raw, style, value, status):
    got, got_status = nz.parse_text_amount(raw, style)
    assert got_status == status
    assert (None if got is None else str(got)) == value


def test_minor_units_never_round():
    assert nz.to_minor_units(Decimal("12.345"), "USD") == (None, 2, nz.PRECISION)
    assert nz.to_minor_units(Decimal("12.340"), "USD") == ("1234", 2, nz.KNOWN)
    assert nz.to_minor_units(Decimal("1.234"), "KWD") == ("1234", 3, nz.KNOWN)
    assert nz.to_minor_units(Decimal("5"), "JPY") == ("5", 0, nz.KNOWN)
    assert nz.to_minor_units(Decimal("5.5"), "JPY")[2] == nz.PRECISION
    assert nz.to_minor_units(Decimal("1"), "XYZ")[2] == nz.UNKNOWN_CURRENCY
    assert nz.to_minor_units(Decimal("1"), None)[2] == nz.UNKNOWN_CURRENCY


def test_float_cells_are_exact_not_rounded():
    assert str(nz.decimal_from_cell_number(0.1 + 0.2)) == "0.30000000000000004"
    assert nz.to_minor_units(nz.decimal_from_cell_number(0.1 + 0.2), "USD")[2] == nz.PRECISION
    assert nz.to_minor_units(nz.decimal_from_cell_number(120.25), "USD")[0] == "12025"
    with pytest.raises(TypeError):
        nz.decimal_from_cell_number(True)


@pytest.mark.parametrize("raw,order,value,status", [
    ("2026-01-31", "iso_only", "2026-01-31", nz.KNOWN),
    ("2026-02-30", "iso_only", None, nz.INVALID),
    ("03/04/2026", "iso_only", None, nz.AMBIGUOUS),
    ("03/04/2026", "dmy", "2026-04-03", nz.KNOWN),
    ("03/04/2026", "mdy", "2026-03-04", nz.KNOWN),
    ("13/13/2026", "dmy", None, nz.INVALID),
    ("31 Jan 2026", "dmy", None, nz.INVALID),
    ("", "dmy", None, nz.MISSING),
])
def test_dates(raw, order, value, status):
    assert nz.parse_text_date(raw, order) == (value, status)


def test_currency_codes():
    assert nz.normalize_currency("usd") == ("USD", nz.KNOWN)
    assert nz.normalize_currency("XYZ") == ("XYZ", nz.UNKNOWN_CURRENCY)
    assert nz.normalize_currency("US$")[1] == nz.INVALID
    assert nz.normalize_currency(" ") == (None, nz.MISSING)
