"""Single-pass verification: the agent investigates and returns the verdict.

The agent resolves figures, does the comparison, and states a conclusion.
Python's job here is narrow: validate the shape, hold the verdict to a fixed
set of values, and resolve the citation from the node the agent actually read.

Contrast with verify.py + compare.py, where the agent returns only evidence and
Python decides. Both paths exist; this one is fewer moving parts, that one is
checkable without a model. `benchmark.py --judge` runs this one.
"""
from __future__ import annotations

import json

from . import tools
from .llm import chat
from .models import Claim, Status
from .validator import validate_all
from .verify import TOOLS, _loads, _run_tool, turn_budget

SYSTEM = """You verify claims against financial filings, and you state the verdict.

The deck is the claim, not the proof. Never cite a document whose role is
"assertion" as evidence for its own claims: quoting the deck back at itself
proves nothing. Evidence must come from a document whose role is "evidence".
If no evidence document covers the claim's period, the verdict is NO_SOURCE.

Method:
1. list_documents() to see what exists and which periods each covers.
2. get_structure(doc_id) to see all sections at once, then choose.
3. get_content(doc_id, [node_ids]) for the sections you selected. Batch them.

Read the figure as printed and apply the table's stated unit. A table headed
"(in thousands)" means 54,284 is $54,284,000. Compare on the same basis and the
same period. Treat a claim as agreeing when it rounds to the figure as stated:
"$54 million" agrees with 54,284 thousands.

Return one finding per claim index, in order, with exactly these verdicts:

  SUPPORTED       the filing agrees, within the rounding the claim implies
  CONTRADICTED    the filing states a different figure
  BASIS_MISMATCH  both figures correct, measured differently (GAAP vs non-GAAP,
                  ARR vs revenue). NOT a contradiction.
  NO_EVIDENCE     you looked and the filings do not say
  NO_SOURCE       no document in the corpus covers the claim's period

Quote the exact text you read. Never state a figure that is not in the text you
fetched: if you cannot find it, the verdict is NO_EVIDENCE. Do not write a URL;
the caller resolves it from node_ids.

Finish with one JSON object:
{"findings":[{"claim_index":0,
              "verdict":"SUPPORTED",
              "claimed":"$54 million",
              "found":"54,284",
              "resolved":"$54,284,000",
              "basis":"GAAP",
              "reasoning":"one sentence",
              "quote":"Operating income (loss) 54,284",
              "doc_id":"...","node_ids":["..."]}]}"""


def judge(claims: list[Claim], model: str | None = None,
          on_event=None) -> dict[int, dict]:
    """Run the agent, then validate that it supplied evidence for its verdict.

    The agent decides. The validator does not re-decide; it rejects a verdict
    whose evidence does not hold up, which becomes NO_EVIDENCE with the reason
    attached rather than a silent pass.
    """
    emit = on_event or (lambda *_a, **_k: None)
    listing = "\n".join(f"[{i}] {c.text}" for i, c in enumerate(claims))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Verify these claims:\n{listing}"}]

    budget = turn_budget(len(claims))
    emit("start", {"claims": len(claims), "turn_budget": budget, "model": model or ""})

    for turn in range(1, budget + 1):
        emit("thinking", {"turn": turn, "of": budget})
        msg = chat(messages, tools=TOOLS, model=model)
        messages.append(msg)

        if msg.get("content"):
            emit("reasoning", {"turn": turn, "text": msg["content"][:400]})

        calls = msg.get("tool_calls") or []
        if not calls:
            emit("validating", {"turn": turn})
            return _finalise(_loads(msg.get("content") or ""), claims)

        for call in calls:
            fn = call["function"]
            args = json.loads(fn["arguments"] or "{}")
            emit("tool", {"turn": turn, "name": fn["name"],
                          "args": ", ".join(str(v) for v in args.values())[:90]})
            out = _run_tool(fn["name"], args)
            emit("observation", {"turn": turn, "name": fn["name"], "chars": len(out)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})

    raise RuntimeError(f"agent exceeded {budget} turns for {len(claims)} claims")


def _finalise(data: dict, claims: list[Claim]) -> dict[int, dict]:
    """Index the agent's findings by claim, then run the contract validator."""
    by_index = {f.get("claim_index", -1): f for f in data.get("findings", [])}
    validated = validate_all(by_index, claims)

    out: dict[int, dict] = {}
    for i, v in validated.items():
        out[i] = {
            "status": v.get("verdict", Status.NO_EVIDENCE.value),
            "claimed": v.get("claimed", ""),
            "found": v.get("found", ""),
            "resolved": v.get("resolved", ""),
            "basis": v.get("basis", ""),
            "reason": v.get("rejected") or v.get("reasoning", ""),
            "quote": v.get("quote", ""),
            "doc_id": v.get("doc_id", ""),
            "node_ids": v.get("node_ids", []),
            "cite": v.get("cite", ""),
            "warnings": v.get("warnings", []),
            "rejected": v.get("rejected", ""),
        }
    return out
