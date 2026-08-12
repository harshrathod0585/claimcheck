"""Deck -> claims. One query over the whole deck, all claims at once.

The deck is short enough to read whole, so there is no retrieval here and no
per-page loop. Unfalsifiable content is discarded at this step and never
enters the pipeline.
"""
from __future__ import annotations

from .llm import json_call
from .models import Claim, Operation, Quantity, Unit
from .normalize import detect_basis, parse_period, parse_quantity

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "figure", "value", "scale", "unit",
                             "operation", "period", "section"],
                "properties": {
                    "text": {"type": "string"},
                    "figure": {"type": "string",
                               "description": "the number exactly as written, e.g. '$4.2M', '140%'"},
                    "value": {"type": "number",
                              "description": "the bare mantissa, no separators or suffix. '$2.68B' -> 2.68"},
                    "scale": {"type": "string", "enum": ["", "K", "M", "B", "T"],
                              "description": "magnitude suffix. '$2.68B' -> B. '2,684,275' -> ''. "
                                             "Use the table's stated unit when the figure is bare: "
                                             "a number under '(in thousands)' is K."},
                    "unit": {"type": "string", "enum": ["USD", "percent", "count", "ratio"]},
                    "operation": {"type": "string", "enum": ["absolute", "growth", "margin", "entity", "count"]},
                    "period": {"type": "string", "description": "e.g. 'FY2024', 'Q4 2023', or '' if none stated"},
                    "section": {"type": "string", "description": "heading this claim sat under"},
                },
            },
        }
    },
}

PROMPT = """Extract every factual claim from this investor material that could be checked against a financial filing.

KEEP: absolute figures, growth rates, margins/ratios, named customers or entities, headcounts.
DISCARD SILENTLY: superlatives, market-size assertions, forward-looking projections, team-quality claims.

If a claim omits its period, inherit the period from its section heading.
Copy the figure exactly as written, including $ , % and M/B suffixes.

MATERIAL:
---
{body}
---"""


def extract(markdown: str, max_chars: int = 60_000, attempts: int = 3) -> list[Claim]:
    """One call. Returns typed claims with period inherited from section context.

    Occasionally the model returns a well-formed response with an empty claims
    array over material that plainly contains figures. That is a silent total
    failure — the caller cannot tell it from a document with nothing to check —
    so an empty result is retried rather than returned.
    """
    body = PROMPT.format(body=markdown[:max_chars])
    raw = {}
    for attempt in range(attempts):
        raw = json_call([{"role": "user", "content": body}], SCHEMA)
        if raw.get("claims"):
            break
        if attempt == attempts - 1:
            raise RuntimeError(
                f"extractor returned no claims after {attempts} attempts over "
                f"{len(markdown)} chars of material")

    # The extractor returns the same sentence more than once, tagged with
    # different operations, so a 22-claim deck can come back as 35. Verifying a
    # claim twice costs twice and shows the analyst the same row twice.
    claims, seen = [], set()
    for c in raw.get("claims", []):
        key = " ".join(str(c.get("text", "")).lower().split())
        if key in seen:
            continue
        seen.add(key)
        if c["operation"] == "entity":
            continue  # ponytail: entity claims need BM25; skipped until that lands
        q = parse_quantity(c["figure"])
        if q is None:
            continue
        # The model tags value, scale and unit; Python does the multiplying.
        # Reading how a filing phrases a magnitude is open-ended and suits the
        # model. Turning a tag into a number is arithmetic, and arithmetic is
        # the thing it gets confidently wrong.
        q = _tagged(c) or q

        # A count ("40 employees") is verified the same way as any absolute figure.
        op = Operation(c["operation"]) if c["operation"] in Operation._value2member_map_ \
            else Operation.ABSOLUTE
        period = parse_period(c["period"]) or parse_period(c["section"])
        claims.append(Claim(text=c["text"], value=q, operation=op,
                            period=period or q.period))
    return claims


SCALE = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _tagged(c: dict) -> Quantity | None:
    """Build a Quantity from the model's tags rather than by parsing prose.

    Returns None when the tags are missing or unusable, so the text parser
    stays as the floor. The multiplication happens here, in Python: the model
    says "B", it never says 2,680,000,000.
    """
    try:
        value = float(c["value"])
    except (KeyError, TypeError, ValueError):
        return None
    scale = SCALE.get((c.get("scale") or "").upper().strip())
    if scale is None:
        return None
    try:
        unit = Unit(c.get("unit") or "count")
    except ValueError:
        unit = Unit.COUNT
    return Quantity(value=value, unit=unit, scale=scale,
                    period=parse_period(c.get("period", "")),
                    basis=detect_basis(c.get("text", "")),
                    raw=c.get("figure", "") or str(value))


def groups(claims: list[Claim], size: int = 10) -> list[list[Claim]]:
    """Chunked so a long agent trajectory can't silently drop claims."""
    return [claims[i:i + size] for i in range(0, len(claims), size)]
