from datetime import date

import pytest

from src.models import Basis, PeriodKind, Unit
from src.normalize import (detect_basis, parse_period, parse_quantity,
                           parse_table_scale, significant_figures)


@pytest.mark.parametrize("text,table_unit,value,unit,scale,base", [
    ("$4.2M",              "",                 4.2,       Unit.USD,     1e6, 4_200_000),
    ("$4.2 million",       "",                 4.2,       Unit.USD,     1e6, 4_200_000),
    ("$4.2B",              "",                 4.2,       Unit.USD,     1e9, 4_200_000_000),
    ("4,183,204",          "",                 4183204.0, Unit.COUNT,   1.0, 4_183_204),
    ("$4,183,204",         "",                 4183204.0, Unit.USD,     1.0, 4_183_204),
    ("(1,978)",            "",                 -1978.0,   Unit.COUNT,   1.0, -1978),
    ("$(1,978)",           "(in thousands)",   -1978.0,   Unit.USD,     1e3, -1_978_000),
    ("2,806",              "(in thousands)",   2806.0,    Unit.COUNT,   1e3, 2_806_000),
    ("2,806",              "(in millions)",    2806.0,    Unit.COUNT,   1e6, 2_806_000_000),
    ("$4.2M",              "(in thousands)",   4.2,       Unit.USD,     1e6, 4_200_000),
    ("72%",                "",                 72.0,      Unit.PERCENT, 1.0, 72),
    ("72 percent",         "",                 72.0,      Unit.PERCENT, 1.0, 72),
    ("140 bps",            "",                 1.4,       Unit.PERCENT, 1.0, 1.4),
    ("140 basis points",   "",                 1.4,       Unit.PERCENT, 1.0, 1.4),
    ("-3.5%",              "",                 -3.5,      Unit.PERCENT, 1.0, -3.5),
])
def test_parse_quantity(text, table_unit, value, unit, scale, base):
    q = parse_quantity(text, table_unit=table_unit)
    assert q is not None
    assert q.value == pytest.approx(value)
    assert q.unit is unit
    assert q.scale == pytest.approx(scale)
    assert q.base_value == pytest.approx(base)


def test_parse_quantity_empty():
    assert parse_quantity("") is None
    assert parse_quantity("market-leading platform") is None


@pytest.mark.parametrize("text,scale", [
    ("(in thousands)", 1e3),
    ("(in millions, except per share data)", 1e6),
    ("(in billions)", 1e9),
    ("", 1.0),
    ("Consolidated Statements of Operations", 1.0),
])
def test_parse_table_scale(text, scale):
    assert parse_table_scale(text) == scale


@pytest.mark.parametrize("text,kind,year,quarter,months,end", [
    ("FY2024",                                 PeriodKind.FISCAL_YEAR, 2024, None, None, None),
    ("fiscal 2024",                            PeriodKind.FISCAL_YEAR, 2024, None, None, None),
    ("fiscal year 2023",                       PeriodKind.FISCAL_YEAR, 2023, None, None, None),
    ("FY24",                                   PeriodKind.FISCAL_YEAR, 2024, None, None, None),
    ("Q4 2023",                                PeriodKind.QUARTER,     2023, 4,    None, None),
    ("Q4 FY2024",                              PeriodKind.QUARTER,     2024, 4,    None, None),
    ("three months ended October 31, 2023",    PeriodKind.MONTHS_ENDED, 2023, None, 3, date(2023, 10, 31)),
    ("nine months ended January 31, 2024",     PeriodKind.MONTHS_ENDED, 2024, None, 9, date(2024, 1, 31)),
])
def test_parse_period(text, kind, year, quarter, months, end):
    p = parse_period(text)
    assert p is not None
    assert (p.kind, p.year, p.quarter, p.months, p.end_date) == (kind, year, quarter, months, end)


def test_parse_period_absent():
    assert parse_period("Revenue grew strongly") is None


def test_period_matching():
    assert parse_period("FY2024").matches(parse_period("fiscal 2024"))
    assert not parse_period("FY2024").matches(parse_period("FY2023"))
    assert not parse_period("Q4 2023").matches(parse_period("FY2023"))
    assert parse_period("FY2024").matches(None)


@pytest.mark.parametrize("text,basis", [
    ("ARR of $3.0B",                          Basis.ARR),
    ("annual recurring revenue",              Basis.ARR),
    ("product revenue of $2.6B",              Basis.PRODUCT_REVENUE),
    ("adjusted EBITDA margin",                Basis.ADJUSTED),
    ("non-GAAP operating income",             Basis.NON_GAAP),
    ("total revenue",                         Basis.GAAP),
    ("headcount grew to 7,000",               Basis.UNKNOWN),
])
def test_detect_basis(text, basis):
    assert detect_basis(text) is basis


def test_quantity_inherits_period_and_basis_from_context():
    q = parse_quantity("$4.2M", context="Total revenue for FY2024")
    assert q.period == parse_period("FY2024")
    assert q.basis is Basis.GAAP


@pytest.mark.parametrize("raw,sig", [
    ("4.2", 2), ("4.20", 3), ("140", 2), ("72", 2), ("4,183,204", 7),
    ("0.045", 2), ("100", 1), ("$4.2M", 2),
])
def test_significant_figures(raw, sig):
    assert significant_figures(raw) == sig
