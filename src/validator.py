"""Contract validation for agent findings.

The agent verifies the claim. This validates that the agent actually supplied
the evidence for its verdict. It does not re-decide anything: a finding is
never flipped from CONTRADICTED to SUPPORTED here, only rejected as unsupported
when the evidence behind it does not hold up.

Five checks:

    schema        required fields present, verdict from the fixed set
    claim link    claim_index refers to a real claim
    node resolves the cited node exists and can be fetched
    retrievable   the quoted text and figure are in what was fetched
    relevance     the finding mentions what the claim is about

Everything here is deterministic. No model calls, no network beyond reading
documents already on disk.
"""
from __future__ import annotations

import re

from . import tools
from .models import Status

VERDICTS = {s.value for s in Status}
REQUIRED = ("claim_index", "verdict", "quote", "doc_id", "node_ids")

# Words too common in filings to carry meaning in a relevance check.
_STOP = {"the", "was", "were", "is", "are", "in", "of", "for", "and", "a", "an",
         "to", "at", "on", "by", "with", "year", "over", "million", "billion",
         "thousand", "fiscal", "quarter", "grew", "growth", "had", "we", "our"}


class Rejected(Exception):
    """The finding failed its contract. The verdict does not stand."""


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())


def _digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _digit_forms(raw: str) -> list[str]:
    """Digit forms a figure might legitimately take, so a correct figure is not
    rejected merely because the model reformatted it."""
    forms = [_digits(raw), _digits(re.sub(r"\.0+\b", "", raw))]
    if "." in raw:
        forms.append(_digits(raw.split(".", 1)[0]))
    return [f for f in forms if f]


def fetch(doc_id: str, node_ids: list[str]) -> list[dict]:
    if not doc_id or not node_ids:
        return []
    try:
        return tools.get_content(doc_id, node_ids)
    except (KeyError, IndexError):
        return []


def figure_retrievable(raw: str, rows: list[dict]) -> bool:
    """Is this figure actually in the text the agent read?

    The agent has reported a figure that is not in the filing — not as a
    retrieval miss but as a fluent invention, with a plausible label and a real
    node id. A verdict resting on a figure that isn't there is the worst output
    this system can produce, because it is indistinguishable from a correct one.
    """
    if not raw or not rows:
        return False
    haystack = _digits(" ".join(r.get("content", "") for r in rows))
    return any(f in haystack for f in _digit_forms(raw))


def quote_retrievable(quote: str, rows: list[dict], min_words: int = 3) -> bool:
    """Same guarantee for claims with no digits: entities, segments, names."""
    words = _norm(quote).split()
    if len(words) < min_words or not rows:
        return False
    haystack = " ".join(_norm(" ".join(r.get("content", "") for r in rows)).split())
    return " ".join(words) in haystack


def relevant(claim_text: str, finding: dict, rows: list[dict]) -> bool:
    """Does the finding appear to be about the claim it is filed under?

    claim_index alone proves nothing: an agent can return the free cash flow
    figure under the revenue claim and satisfy every other check. This catches
    gross mismatches by requiring one distinctive word from the claim to appear
    in the evidence. It will not catch subtle ones.
    """
    terms = {w for w in _norm(claim_text).split() if w not in _STOP and len(w) > 3}
    if not terms:
        return True
    hay = _norm(" ".join([finding.get("quote", ""), finding.get("found", ""),
                          *(r.get("title", "") for r in rows)]))
    return any(t in hay for t in terms)


def validate(finding: dict, claim_text: str) -> dict:
    """Check one finding against the contract. Raises Rejected on failure.

    Returns the finding with a resolved citation and any non-fatal warnings.
    """
    missing = [k for k in REQUIRED if k not in finding]
    if missing:
        raise Rejected(f"missing required fields: {', '.join(missing)}")

    verdict = str(finding.get("verdict", "")).strip().upper()
    if verdict not in VERDICTS:
        raise Rejected(f"verdict {verdict!r} is not one of {sorted(VERDICTS)}")

    doc_id, node_ids = finding.get("doc_id", ""), finding.get("node_ids") or []

    # NO_SOURCE and NO_EVIDENCE assert an absence, so they carry no evidence
    # to check. Demanding a citation for "we found nothing" would force the
    # agent to invent one.
    if verdict in (Status.NO_SOURCE.value, Status.NO_EVIDENCE.value):
        return {**finding, "verdict": verdict, "cite": "", "warnings": []}

    rows = fetch(doc_id, node_ids)
    if not rows:
        raise Rejected(f"cited node not retrievable: {doc_id} {node_ids}")

    found = finding.get("found", "")
    quote = finding.get("quote", "")
    if _digits(found):
        if not figure_retrievable(found, rows):
            raise Rejected(f"figure {found!r} is not in the cited text")
    elif not quote_retrievable(quote, rows):
        raise Rejected(f"quote is not in the cited text: {quote[:60]!r}")

    warnings = []
    if not relevant(claim_text, finding, rows):
        warnings.append("evidence may not relate to this claim")

    return {**finding, "verdict": verdict,
            "cite": rows[0].get("cite", ""),   # from the node read, never the model
            "warnings": warnings}


def validate_all(findings: dict[int, dict], claims: list) -> dict[int, dict]:
    """Validate every claim's finding. A rejection becomes NO_EVIDENCE with the
    reason attached, so a failed contract is visible rather than silent."""
    out: dict[int, dict] = {}
    for i, claim in enumerate(claims):
        f = findings.get(i)
        if not f:
            out[i] = {"verdict": Status.NO_EVIDENCE.value, "cite": "", "warnings": [],
                      "rejected": "agent returned no finding for this claim"}
            continue
        try:
            out[i] = validate(f, getattr(claim, "text", str(claim)))
        except Rejected as exc:
            out[i] = {**f, "verdict": Status.NO_EVIDENCE.value, "cite": "",
                      "warnings": [], "rejected": str(exc)}
    return out
