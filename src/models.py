"""Core value types for the decision engine. Pure data, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Unit(str, Enum):
    USD = "USD"
    PERCENT = "percent"
    COUNT = "count"          # headcount, customers, bare numbers
    RATIO = "ratio"


class Basis(str, Enum):
    """Accounting basis a figure is measured on."""
    GAAP = "GAAP"
    NON_GAAP = "non-GAAP"
    ADJUSTED = "adjusted"
    ARR = "ARR"
    PRODUCT_REVENUE = "product revenue"
    UNKNOWN = "unknown"


class PeriodKind(str, Enum):
    FISCAL_YEAR = "FY"
    QUARTER = "Q"
    MONTHS_ENDED = "months_ended"


class Operation(str, Enum):
    ABSOLUTE = "absolute"
    GROWTH = "growth"        # (a - b) / b
    MARGIN = "margin"        # a / b


class Status(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    BASIS_MISMATCH = "BASIS_MISMATCH"
    NO_EVIDENCE = "NO_EVIDENCE"
    NO_SOURCE = "NO_SOURCE"


@dataclass(frozen=True)
class Period:
    kind: PeriodKind
    year: Optional[int] = None
    quarter: Optional[int] = None
    months: Optional[int] = None
    end_date: Optional[date] = None
    label: str = ""

    def key(self):
        """Identity used for period comparison. end_date wins when present."""
        if self.end_date is not None:
            return ("ended", self.months, self.end_date)
        return (self.kind.value, self.year, self.quarter)

    def matches(self, other: Optional["Period"]) -> bool:
        # An unknown period on either side does not block a comparison; the
        # claim's period is what the caller asserted, and evidence that
        # carries no period label is judged by its covering document.
        if other is None or self is None:
            return True
        if self.end_date is not None and other.end_date is not None:
            return self.end_date == other.end_date and self.months == other.months
        if self.kind != other.kind:
            return False
        return self.year == other.year and self.quarter == other.quarter


@dataclass(frozen=True)
class Quantity:
    value: float                       # mantissa as written ("$4.2M" -> 4.2)
    unit: Unit = Unit.COUNT
    scale: float = 1.0                 # multiplier ("$4.2M" -> 1e6)
    period: Optional[Period] = None
    basis: Basis = Basis.UNKNOWN
    raw: str = ""                      # text as it appeared, drives sig figs

    @property
    def base_value(self) -> float:
        """Value in base units — dollars, percentage points, items."""
        return self.value * self.scale


@dataclass
class Claim:
    text: str
    value: Quantity                    # the figure as the deck states it
    operation: Operation = Operation.ABSOLUTE
    period: Optional[Period] = None
    basis: Basis = Basis.UNKNOWN

    def __post_init__(self):
        if self.period is None:
            self.period = self.value.period
        if self.basis is Basis.UNKNOWN:
            self.basis = self.value.basis


@dataclass
class Evidence:
    """What the verification agent returned. Never a verdict."""
    quantities: list[Quantity] = field(default_factory=list)
    covered_periods: list[Period] = field(default_factory=list)
    doc_id: str = ""
    node_ids: list[str] = field(default_factory=list)
    citation_url: str = ""
    quote: str = ""

    def covers(self, period: Optional[Period]) -> bool:
        if period is None:
            return bool(self.covered_periods) or bool(self.quantities)
        return any(period.matches(p) for p in self.covered_periods)


@dataclass
class Verdict:
    status: Status
    claim: Optional[Claim] = None
    claimed: Optional[float] = None    # base units
    actual: Optional[float] = None     # base units
    claimed_basis: Optional[Basis] = None
    actual_basis: Optional[Basis] = None
    reason: str = ""
    evidence: Optional[Evidence] = None
