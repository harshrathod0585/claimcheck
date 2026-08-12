import pytest

from src.compare import compare, compute, numeric_band, within_tolerance
from src.models import (Basis, Claim, Evidence, Operation, Period, PeriodKind,
                        Quantity, Status, Unit)

FY2024 = Period(PeriodKind.FISCAL_YEAR, 2024, label="FY2024")
FY2023 = Period(PeriodKind.FISCAL_YEAR, 2023, label="FY2023")
FY2022 = Period(PeriodKind.FISCAL_YEAR, 2022, label="FY2022")


def usd(value, scale=1.0, period=FY2024, basis=Basis.GAAP, raw=None):
    return Quantity(value, Unit.USD, scale, period, basis, raw or f"{value:g}")


def pct(value, period=FY2024, basis=Basis.GAAP, raw=None):
    return Quantity(value, Unit.PERCENT, 1.0, period, basis, raw or f"{value:g}")


def claim_of(q, operation=Operation.ABSOLUTE, period=None, text=""):
    return Claim(text=text or "claim", value=q, operation=operation,
                 period=period or q.period, basis=q.basis)


def evidence_of(quantities, periods=(FY2024, FY2023)):
    return Evidence(quantities=list(quantities), covered_periods=list(periods),
                    doc_id="SNOW_10K_FY2024", node_ids=["n1"],
                    citation_url="https://sec.gov/...#n1")


# --- the headline table ------------------------------------------------------

CASES = [
    # id,                claim,                          evidence quantities,      expected
    ("rounds down",      usd(4.2, 1e6, raw="4.2"),        [usd(4_183_204)],         Status.SUPPORTED),
    ("rounds up",        usd(4.2, 1e6, raw="4.2"),        [usd(4_249_000)],         Status.SUPPORTED),
    ("outside band",     usd(4.2, 1e6, raw="4.2"),        [usd(4_900_000)],         Status.CONTRADICTED),
    ("scale error",      usd(4.2, 1e9, raw="4.2"),        [usd(4_183_204)],         Status.CONTRADICTED),
    ("exact",            usd(4_183_204, raw="4,183,204"), [usd(4_183_204)],         Status.SUPPORTED),
    ("margin figure",    pct(72, raw="72"),               [pct(71.8, raw="71.8")],  Status.SUPPORTED),
    ("wrong margin",     pct(72, raw="72"),               [pct(64.1, raw="64.1")],  Status.CONTRADICTED),
]


@pytest.mark.parametrize("label,claimed,quantities,expected",
                         CASES, ids=[c[0] for c in CASES])
def test_absolute_claims(label, claimed, quantities, expected):
    v = compare(claim_of(claimed), evidence_of(quantities))
    assert v.status is expected, f"{label}: {v.reason}"


def test_scale_error_is_reported_as_a_scale_error():
    v = compare(claim_of(usd(4.2, 1e9, raw="4.2")), evidence_of([usd(4_183_204)]))
    assert v.status is Status.CONTRADICTED
    assert "scale mismatch" in v.reason
    assert v.claimed == pytest.approx(4.2e9)
    assert v.actual == pytest.approx(4_183_204)


def test_period_swap_is_caught():
    """An FY2023 figure presented as FY2024. The 10-K covers both periods, so
    this is a period mismatch rather than NO_SOURCE."""
    claim = claim_of(usd(4.2, 1e6, raw="4.2", period=FY2024), period=FY2024)
    v = compare(claim, evidence_of([usd(4_183_204, period=FY2023)]))
    assert v.status is Status.CONTRADICTED
    assert "period mismatch" in v.reason


def test_unit_mismatch_is_caught_before_the_numeric_band():
    ok, reason = within_tolerance(pct(72, raw="72"), usd(72))
    assert not ok and "unit mismatch" in reason


# --- derived figures ---------------------------------------------------------

def test_growth_is_recomputed_in_python():
    actual = compute(Operation.GROWTH,
                     [usd(2_806_411, period=FY2024), usd(1_978_224, period=FY2023)])
    assert actual.value == pytest.approx(41.87, abs=0.01)
    assert actual.unit is Unit.PERCENT


def test_claimed_growth_of_140_percent_is_contradicted():
    claim = claim_of(pct(140, raw="140"), operation=Operation.GROWTH,
                     text="revenue grew 140% YoY")
    v = compare(claim, evidence_of([usd(2_806_411, period=FY2024),
                                    usd(1_978_224, period=FY2023)]))
    assert v.status is Status.CONTRADICTED
    assert v.actual == pytest.approx(41.87, abs=0.01)


def test_correct_growth_is_supported():
    claim = claim_of(pct(42, raw="42"), operation=Operation.GROWTH)
    v = compare(claim, evidence_of([usd(2_806_411, period=FY2024),
                                    usd(1_978_224, period=FY2023)]))
    assert v.status is Status.SUPPORTED


def test_margin_is_recomputed_in_python():
    claim = claim_of(pct(72, raw="72"), operation=Operation.MARGIN)
    v = compare(claim, evidence_of([usd(2_016_000, period=FY2024),
                                    usd(2_806_411, period=FY2024)]))
    assert v.status is Status.SUPPORTED
    assert v.actual == pytest.approx(71.8, abs=0.1)


def test_growth_without_two_endpoints_is_no_evidence():
    claim = claim_of(pct(140, raw="140"), operation=Operation.GROWTH)
    v = compare(claim, evidence_of([usd(2_806_411)]))
    assert v.status is Status.NO_EVIDENCE


# --- basis -------------------------------------------------------------------

def test_arr_against_gaap_revenue_is_a_basis_mismatch():
    claim = claim_of(usd(3.0, 1e9, raw="3.0", basis=Basis.ARR), text="ARR of $3.0B")
    ev = evidence_of([usd(2.8e9, basis=Basis.GAAP, raw="2.8"),
                      usd(3.0e9, basis=Basis.ARR, raw="3.0")])
    v = compare(claim, ev)
    assert v.status is Status.BASIS_MISMATCH
    assert v.claimed_basis is Basis.ARR
    assert v.actual_basis is Basis.ARR
    assert v.actual == pytest.approx(2.8e9)


def test_arr_claim_with_no_alternate_basis_is_contradicted():
    claim = claim_of(usd(3.0, 1e9, raw="3.0", basis=Basis.ARR))
    v = compare(claim, evidence_of([usd(2.8e9, basis=Basis.GAAP, raw="2.8")]))
    assert v.status is Status.CONTRADICTED


def test_gaap_claim_matching_gaap_evidence_is_supported_not_basis_mismatch():
    claim = claim_of(usd(2.8, 1e9, raw="2.8", basis=Basis.GAAP))
    v = compare(claim, evidence_of([usd(2.8e9, basis=Basis.GAAP, raw="2.8"),
                                    usd(3.0e9, basis=Basis.ARR, raw="3.0")]))
    assert v.status is Status.SUPPORTED


# --- absence -----------------------------------------------------------------

def test_no_source_when_no_document_covers_the_period():
    claim = claim_of(usd(4.2, 1e6, raw="4.2", period=FY2024), period=FY2024)
    ev = evidence_of([usd(4_183_204, period=FY2022)], periods=[FY2022])
    v = compare(claim, ev)
    assert v.status is Status.NO_SOURCE


def test_no_evidence_when_nothing_was_found():
    claim = claim_of(usd(4.2, 1e6, raw="4.2"))
    v = compare(claim, evidence_of([]))
    assert v.status is Status.NO_EVIDENCE


def test_no_source_outranks_no_evidence():
    claim = claim_of(usd(4.2, 1e6, raw="4.2", period=FY2024), period=FY2024)
    v = compare(claim, Evidence(quantities=[], covered_periods=[FY2022]))
    assert v.status is Status.NO_SOURCE


# --- the tolerance band itself ----------------------------------------------

@pytest.mark.parametrize("value,raw,band", [
    (4.2, "4.2", 0.05),
    (4.20, "4.20", 0.005),
    (140, "140", 5.0),
    (72, "72", 0.5),
    (4183204, "4,183,204", 0.5),
])
def test_numeric_band_from_significant_figures(value, raw, band):
    assert numeric_band(value, raw) == pytest.approx(band)
