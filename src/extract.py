"""Deck -> claims. One query over the whole deck, all claims at once.

The deck is short enough to read whole, so there is no retrieval here and no
per-page loop. Unfalsifiable content is discarded at this step and never
enters the pipeline.
"""
from __future__ import annotations

from .llm import json_call
from .models import Claim, Operation
from .normalize import parse_period, parse_quantity

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
                "required": ["text", "figure", "operation", "period", "section"],
                "properties": {
                    "text": {"type": "string"},
                    "figure": {"type": "string",
                               "description": "the number exactly as written, e.g. '$4.2M', '140%'"},
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


def extract(markdown: str, max_chars: int = 60_000) -> list[Claim]:
    """One call. Returns typed claims with period inherited from section context."""
    raw = json_call(
        [{"role": "user", "content": PROMPT.format(body=markdown[:max_chars])}],
        SCHEMA,
    )
    claims = []
    for c in raw.get("claims", []):
        if c["operation"] == "entity":
            continue  # ponytail: entity claims need BM25; skipped until that lands
        q = parse_quantity(c["figure"])
        if q is None:
            continue
        # A count ("40 employees") is verified the same way as any absolute figure.
        op = Operation(c["operation"]) if c["operation"] in Operation._value2member_map_ \
            else Operation.ABSOLUTE
        period = parse_period(c["period"]) or parse_period(c["section"])
        claims.append(Claim(text=c["text"], value=q, operation=op,
                            period=period or q.period))
    return claims


def groups(claims: list[Claim], size: int = 10) -> list[list[Claim]]:
    """Chunked so a long agent trajectory can't silently drop claims."""
    return [claims[i:i + size] for i in range(0, len(claims), size)]
