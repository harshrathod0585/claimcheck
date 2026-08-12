"""text -> Quantity. Pure functions: no I/O, no network, no model."""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .models import Basis, Period, PeriodKind, Quantity, Unit

SCALE_WORDS = {
    "k": 1e3, "thousand": 1e3, "thousands": 1e3,
    "m": 1e6, "mm": 1e6, "million": 1e6, "millions": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9, "billions": 1e9,
    "t": 1e12, "trillion": 1e12, "trillions": 1e12,
}

_NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_SCALE_SUFFIX = re.compile(
    r"\s*(k|mm|m|bn|b|t|thousands?|millions?|billions?|trillions?)\b", re.I
)
_TABLE_UNIT = re.compile(
    r"in\s+(thousands?|millions?|billions?)", re.I
)

# Basis markers, checked in order — the most specific label wins.
_BASIS_MARKERS = [
    (Basis.ARR, r"\bARR\b|annual(?:ized)?\s+recurring\s+revenue"),
    (Basis.PRODUCT_REVENUE, r"\bproduct\s+revenue\b"),
    (Basis.ADJUSTED, r"\badjusted\b|\bEBITDA\b|\bpro\s*forma\b"),
    (Basis.NON_GAAP, r"non[-\s]?GAAP"),
    (Basis.GAAP, r"\bGAAP\b|\btotal\s+revenue\b|\brevenue\b"),
]

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}

_WORD_MONTH_COUNT = {"one": 1, "two": 2, "three": 3, "six": 6, "nine": 9, "twelve": 12}


def detect_basis(text: str) -> Basis:
    for basis, pattern in _BASIS_MARKERS:
        if re.search(pattern, text, re.I):
            return basis
    return Basis.UNKNOWN


def parse_table_scale(text: str) -> float:
    """'(in thousands)' -> 1e3. Returns 1.0 when no unit statement is present."""
    m = _TABLE_UNIT.search(text or "")
    return SCALE_WORDS[m.group(1).lower()] if m else 1.0


def parse_period(text: str) -> Optional[Period]:
    t = text or ""

    m = re.search(
        r"(one|two|three|six|nine|twelve|\d+)\s+months?\s+ended\s+"
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", t, re.I)
    if m:
        n = m.group(1).lower()
        months = _WORD_MONTH_COUNT.get(n) or int(n)
        month = _MONTHS.get(m.group(2).lower())
        if month:
            end = date(int(m.group(4)), month, int(m.group(3)))
            return Period(PeriodKind.MONTHS_ENDED, year=end.year, months=months,
                          end_date=end, label=m.group(0))

    m = re.search(r"\bQ([1-4])\s*(?:of\s*)?(?:FY|fiscal\s*(?:year\s*)?)?\s*(\d{4}|\d{2})\b", t, re.I)
    if m:
        return Period(PeriodKind.QUARTER, year=_year(m.group(2)),
                      quarter=int(m.group(1)), label=m.group(0))

    m = re.search(r"\b(?:FY|fiscal\s*(?:year\s*)?)\s*(\d{4}|\d{2})\b", t, re.I)
    if m:
        return Period(PeriodKind.FISCAL_YEAR, year=_year(m.group(1)), label=m.group(0))

    m = re.search(r"\b(?:full\s+year|year\s+ended[^,]*,?)\s*(\d{4})\b", t, re.I)
    if m:
        return Period(PeriodKind.FISCAL_YEAR, year=int(m.group(1)), label=m.group(0))

    return None


def _year(s: str) -> int:
    n = int(s)
    return 2000 + n if n < 100 else n


def parse_quantity(text: str, table_unit: str = "",
                   period: Optional[Period] = None,
                   context: str = "") -> Optional[Quantity]:
    """Parse a figure as it appears in a filing or deck.

    `table_unit` is the surrounding table's unit statement ('(in thousands)'),
    applied only to bare numbers — an explicit suffix in the text always wins.
    `context` supplies extra text for period/basis detection (row label,
    section header) without contributing digits.
    """
    if not text:
        return None
    t = text.strip()

    # Accounting negatives: (1,978) and $(1,978). '(in thousands)' has no
    # digits after the paren, so it does not trip this.
    negative = bool(re.search(r"\(\s*\$?\s*\d[\d,.]*[^)]*\)", t))
    m = _NUMBER.search(t)
    if not m:
        return None
    value = float(m.group(0).replace(",", ""))
    raw_number = m.group(0)
    tail = t[m.end():]

    unit = Unit.COUNT
    scale = 1.0
    if re.match(r"\s*(bps|basis\s+points?)\b", tail, re.I):
        # 140 bps -> 1.40 percentage points
        unit, value, raw_number = Unit.PERCENT, value / 100.0, f"{value / 100.0:g}"
    elif re.match(r"\s*%|\s*percent", tail, re.I):
        unit = Unit.PERCENT
    else:
        sm = _SCALE_SUFFIX.match(tail)
        if sm:
            unit = Unit.USD if "$" in t else Unit.COUNT
            scale = SCALE_WORDS[sm.group(1).lower()]
        else:
            unit = Unit.USD if "$" in t else Unit.COUNT
            scale = parse_table_scale(table_unit)

    if negative:
        value = -value

    both = f"{t} {context}"
    return Quantity(
        value=value,
        unit=unit,
        scale=scale,
        period=period or parse_period(both),
        basis=detect_basis(both),
        raw=raw_number,
    )


def significant_figures(raw: str) -> int:
    """Sig figs in a figure *as written*. '4.2' -> 2, '140' -> 2, '4.20' -> 3.

    Trailing zeros in an integer are treated as non-significant (the usual
    convention), so '140%' gets a band of +/-5 rather than +/-0.5.
    """
    s = re.sub(r"[^\d.]", "", raw or "")
    if not s:
        return 0
    if "." in s:
        digits = s.replace(".", "").lstrip("0")
        return max(len(digits), 1)
    digits = s.strip("0")
    return max(len(digits), 1)
