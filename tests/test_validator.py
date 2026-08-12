"""The validator checks that the agent supplied evidence for its verdict.

It never re-decides. A CONTRADICTED finding with sound evidence stays
CONTRADICTED even if the numbers look agreeable; the only thing that changes a
verdict here is the evidence behind it failing to hold up.

No model calls, no API key.
"""
from __future__ import annotations

import pytest

from src.models import Status
from src.validator import (Rejected, figure_retrievable, quote_retrievable,
                           relevant, validate, validate_all)


class FakeClaim:
    def __init__(self, text): self.text = text


# The text the agent actually fetched from Datadog's FY2024 10-K, node n147.
ROWS = [{
    "title": "Results of Operations",
    "content": "(in thousands)\n"
               "| Operating income (loss) | 54,284 | (33,464) |\n"
               "| Revenue | 2,684,275 | 2,128,359 |",
    "cite": "https://www.sec.gov/Archives/edgar/data/1561550/...#ibf53bde573",
}]

GOOD = {"claim_index": 0, "verdict": "SUPPORTED", "found": "54,284",
        "quote": "Operating income (loss) 54,284",
        "doc_id": "DDOG_10K_FY2024", "node_ids": ["n147"]}

CLAIM = "GAAP operating income was $54 million in FY2024"


# ── retrievability ──────────────────────────────────────────────────────

def test_invented_figure_is_not_retrievable():
    """674,000 was returned for non-GAAP operating income. It is not in the
    filing. The agent had this text in context and produced it anyway."""
    assert figure_retrievable("674,000", ROWS) is False


def test_real_figures_are_retrievable():
    for raw in ("54,284", "54284", "$54,284", "54,284.00", "2,684,275"):
        assert figure_retrievable(raw, ROWS) is True, raw


def test_quote_must_be_present():
    assert quote_retrievable("Operating income (loss) 54,284", ROWS) is True
    assert quote_retrievable("Acme Analytics is a customer", ROWS) is False


def test_short_quotes_are_refused():
    """Two common words match almost any filing by accident."""
    assert quote_retrievable("the revenue", ROWS) is False


# ── the contract ────────────────────────────────────────────────────────

def test_good_finding_passes_and_gets_a_citation():
    out = validate(GOOD, CLAIM)
    assert out["verdict"] == "SUPPORTED"
    assert out["cite"].startswith("https://www.sec.gov/")
    assert out["warnings"] == []


def test_citation_comes_from_the_node_not_the_model():
    """The model has produced a plausible URL for the wrong company (CIK
    1790673 instead of Datadog's 1561550). Whatever it writes is discarded and
    the citation is resolved from the node actually fetched."""
    fake = "https://www.sec.gov/Archives/edgar/data/9999999/fake.htm"
    cite = validate({**GOOD, "cite": fake}, CLAIM)["cite"]
    assert cite != fake
    assert "1561550" in cite  # Datadog's CIK, from the corpus manifest


def test_missing_field_is_rejected():
    with pytest.raises(Rejected, match="missing required fields"):
        validate({k: v for k, v in GOOD.items() if k != "quote"}, CLAIM)


def test_unknown_verdict_is_rejected():
    with pytest.raises(Rejected, match="not one of"):
        validate({**GOOD, "verdict": "PROBABLY_FINE"}, CLAIM)


def test_unresolvable_node_is_rejected():
    with pytest.raises(Rejected, match="not retrievable"):
        validate({**GOOD, "doc_id": "NO_SUCH_DOC", "node_ids": ["n1"]}, CLAIM)


def test_invented_figure_is_rejected_end_to_end():
    with pytest.raises(Rejected, match="not in the cited text"):
        validate({**GOOD, "found": "674,000",
                  "quote": "Non-GAAP operating income 674,000"}, CLAIM)


def test_absence_verdicts_need_no_evidence():
    """"We found nothing" cannot cite anything. Demanding a citation would
    force the agent to invent one."""
    for verdict in ("NO_EVIDENCE", "NO_SOURCE"):
        out = validate({"claim_index": 0, "verdict": verdict, "quote": "",
                        "doc_id": "", "node_ids": []}, CLAIM)
        assert out["verdict"] == verdict


# ── the validator does not re-decide ────────────────────────────────────

def test_contradicted_stays_contradicted():
    """Evidence is sound, so the agent's verdict stands untouched — even though
    54,284 thousands does equal the $54 million a SUPPORTED verdict would use."""
    out = validate({**GOOD, "verdict": "CONTRADICTED"}, CLAIM)
    assert out["verdict"] == "CONTRADICTED"


def test_basis_mismatch_stays():
    out = validate({**GOOD, "verdict": "BASIS_MISMATCH"}, CLAIM)
    assert out["verdict"] == "BASIS_MISMATCH"


# ── relevance is a warning, not a rejection ─────────────────────────────

def test_mismatched_evidence_warns():
    """claim_index alone proves nothing: an agent can file the right figure
    under the wrong claim and satisfy every other check."""
    out = validate(GOOD, "Free cash flow was $775 million in FY2024")
    assert "evidence may not relate to this claim" in out["warnings"]
    assert out["verdict"] == "SUPPORTED"  # warned, not overruled


# ── every claim gets a record ───────────────────────────────────────────

def test_skipped_claim_becomes_no_evidence():
    out = validate_all({}, [FakeClaim(CLAIM), FakeClaim("another claim")])
    assert len(out) == 2
    assert all(v["verdict"] == Status.NO_EVIDENCE.value for v in out.values())
    assert "no finding" in out[0]["rejected"]


def test_rejection_reason_is_kept():
    out = validate_all({0: {**GOOD, "found": "674,000"}}, [FakeClaim(CLAIM)])
    assert out[0]["verdict"] == Status.NO_EVIDENCE.value
    assert "not in the cited text" in out[0]["rejected"]
