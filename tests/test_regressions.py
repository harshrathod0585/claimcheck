"""Regressions for three bugs a live run produced, with the real data.

Each of these shipped, ran against a real filing, and produced a wrong verdict.
Wrong in the dangerous direction: the output looked exactly like a correct one.

No model calls. No API key. No network.
"""
from __future__ import annotations

from src.compare import compare, within_tolerance
from src.models import (Basis, Claim, Evidence, Operation, Period, PeriodKind,
                        Quantity, Status, Unit)
from src.verify import _grounded, _table_unit

FY2024 = Period(kind=PeriodKind.FISCAL_YEAR, year=2024, label="FY2024")

# The text the agent actually fetched from Datadog's FY2024 10-K, node n147.
FETCHED = [{
    "content": "(in thousands)\n"
               "| Operating income (loss) | 54,284 | (33,464) | (58,695) |\n"
               "| Revenue | 2,684,275 | 2,128,359 | 1,675,100 |",
    "cite": "https://www.sec.gov/Archives/edgar/data/1561550/...#ibf53bde573",
}]


# ── bug 1: the agent invented a figure and it was reported as SUPPORTED ──

def test_invented_figure_is_not_grounded():
    """674,000 was reported for non-GAAP operating income. It is not in the
    filing. The agent had this text in its context window and produced a
    plausible number anyway."""
    assert _grounded("674,000", FETCHED) is False


def test_real_figures_are_grounded():
    """The check must not be so strict that it rejects correct evidence, which
    would fail quietly in the opposite direction."""
    for raw in ("54,284", "2,684,275", "(33,464)"):
        assert _grounded(raw, FETCHED) is True, raw


def test_grounding_ignores_separator_style():
    """The model reformats freely: 54284, 54,284, $54,284 are the same figure."""
    for raw in ("54284", "$54,284", "54,284.00"):
        assert _grounded(raw, FETCHED) is True, raw


def test_grounding_fails_closed():
    """No fetched text means nothing can be confirmed, so nothing is."""
    assert _grounded("54,284", []) is False
    assert _grounded("", FETCHED) is False


# ── bug 2: a correct figure rejected as a unit conflict ─────────────────

def test_dollar_claim_against_bare_table_figure():
    """'$54 million' vs a retrieved '54,284' was CONTRADICTED with
    'unit mismatch: USD vs count'. The currency is printed once in the column
    header, so a figure lifted from the table is bare. That is the absence of
    a unit, not a claim that it isn't money."""
    claimed = Quantity(value=54, unit=Unit.USD, scale=1e6, period=FY2024, raw="$54 million")
    actual = Quantity(value=54_284, unit=Unit.COUNT, scale=1e3, period=FY2024, raw="54,284")
    ok, why = within_tolerance(claimed, actual)
    assert ok, why


def test_percent_against_currency_still_rejects():
    """The loosening must not swallow a real unit conflict."""
    claimed = Quantity(value=74, unit=Unit.PERCENT, scale=1.0, period=FY2024, raw="74%")
    actual = Quantity(value=74, unit=Unit.USD, scale=1e6, period=FY2024, raw="$74M")
    ok, why = within_tolerance(claimed, actual)
    assert not ok and "unit mismatch" in why


# ── bug 3: table scale trusted to the model ─────────────────────────────

def test_table_unit_read_from_fetched_text():
    """'(in thousands)' is printed once in a header. Read it, don't ask for it:
    a figure read as units instead of thousands is wrong by 1000x."""
    assert "thousand" in _table_unit(FETCHED).lower()


def test_table_unit_absent_is_empty_not_guessed():
    assert _table_unit([{"content": "| Revenue | 2,684,275 |"}]) == ""


# ── the three together, on the verdict that was wrong ───────────────────

def test_gaap_operating_income_verdict_is_supported():
    """End to end over the exact figures from the failing run: $54 million
    claimed, 54,284 thousands retrieved. Same number. Must be SUPPORTED."""
    claim = Claim(text="GAAP operating income was $54 million in FY2024",
                  value=Quantity(value=54, unit=Unit.USD, scale=1e6,
                                 period=FY2024, raw="$54 million"),
                  operation=Operation.ABSOLUTE, period=FY2024)
    evidence = Evidence(
        quantities=[Quantity(value=54_284, unit=Unit.COUNT, scale=1e3,
                             period=FY2024, basis=Basis.GAAP, raw="54,284")],
        covered_periods=[FY2024], doc_id="DDOG_10K_FY2024", node_ids=["n147"])
    assert compare(claim, evidence).status is Status.SUPPORTED


def test_inflated_claim_still_contradicted():
    """The fixes must not turn the system into a rubber stamp. 10x the real
    figure has to fail."""
    claim = Claim(text="GAAP operating income was $540 million in FY2024",
                  value=Quantity(value=540, unit=Unit.USD, scale=1e6,
                                 period=FY2024, raw="$540 million"),
                  operation=Operation.ABSOLUTE, period=FY2024)
    evidence = Evidence(
        quantities=[Quantity(value=54_284, unit=Unit.COUNT, scale=1e3,
                             period=FY2024, basis=Basis.GAAP, raw="54,284")],
        covered_periods=[FY2024], doc_id="DDOG_10K_FY2024", node_ids=["n147"])
    assert compare(claim, evidence).status is Status.CONTRADICTED
