"""Verification agent. Claims are the query, documents are the environment.

The agent finds evidence and reads numbers. It never returns a verdict —
that is decided in compare.py, in Python. That boundary is the whole point:
it is why an open-weight model suffices and why the verdict logic is
testable with no API key.
"""
from __future__ import annotations

import json
import re

from . import tools
from .llm import chat
from .models import Claim, Evidence, Quantity
from .normalize import parse_period, parse_quantity

# Turns needed grows with how many distinct sections the batch requires, not
# with the claim count itself: claims sharing an income statement share a
# fetch. Three orienting turns plus roughly one fetch per two claims, floored
# so a single claim still gets room to recover from a wrong first guess.
BASE_TURNS = 6
TURNS_PER_CLAIM = 0.5
MAX_TURNS_CEILING = 30


def turn_budget(n_claims: int) -> int:
    return min(MAX_TURNS_CEILING, BASE_TURNS + int(n_claims * TURNS_PER_CLAIM))


MAX_TURNS = BASE_TURNS  # back-compat for callers that import it directly

TOOLS = [
    {"type": "function", "function": {
        "name": "list_documents", "description": "List available documents and the periods they cover.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_structure", "description": "Full section tree of a document. Titles and summaries only, no text.",
        "parameters": {"type": "object", "required": ["doc_id"],
                       "properties": {"doc_id": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "get_content", "description": "Fetch the text of specific nodes. Tables come back intact.",
        "parameters": {"type": "object", "required": ["doc_id", "node_ids"],
                       "properties": {"doc_id": {"type": "string"},
                                      "node_ids": {"type": "array", "items": {"type": "string"}}}}}},
]

SYSTEM = """You verify claims against financial filings.

The deck is the claim, not the proof. Never cite a document whose role is
"assertion" as evidence for its own claims: quoting the deck back at itself
proves nothing. Evidence must come from a document whose role is "evidence".
If no evidence document covers the claim's period, the verdict is NO_SOURCE.

Method:
1. list_documents() to see what exists and which periods they cover.
2. get_structure(doc_id) to see all sections. Reason over the whole tree at once.
3. get_content(doc_id, [node_ids]) with the nodes you selected. Batch them in one call.

Claims that share evidence share a fetch — one income statement answers revenue,
growth and margin claims together.

If a figure disagrees with the claim, also fetch the non-GAAP reconciliation
section before concluding: the deck may be quoting ARR or adjusted figures
rather than lying.

Return ONLY the numbers you found and where you found them. Do NOT judge whether
any claim is true or false — that is decided downstream.

CRITICAL: emit one finding for EVERY claim index, in order, even when the number
in the document differs from the claim. A differing number is exactly what must
be reported — report what the document actually says and let the caller compare.
Use an empty figures list only when the document genuinely says nothing.

Never invent a URL. Omit "cite"; the caller resolves it from node_ids.

Copy each figure exactly as printed, and copy the table's unit statement with it.
Financial tables state their units once in a header such as "(in thousands)" or
"(in millions)". Without it a figure is unreadable: 2,666,849 in thousands and
2,666,849 in units differ by a factor of a thousand. If the table states no unit,
use an empty string.

Finish with a JSON object:
{"findings":[{"claim_index":0,"figures":[{"raw":"2,806,489","label":"Total revenue",
                                          "unit":"(in thousands)","period":"FY2024"}],
              "doc_id":"...","node_ids":["..."],"quote":"..."}]}"""


def _loads(content: str) -> dict:
    """Open models emit near-JSON: unescaped quotes inside quoted text, trailing
    commas, prose around the object. Salvage what parses; a malformed tail must
    not cost the whole group its evidence."""
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    start, end = content.find("{"), content.rfind("}")
    if start < 0:
        return {"findings": []}
    dec = json.JSONDecoder()
    try:
        return dec.raw_decode(content[start:])[0]
    except json.JSONDecodeError:
        pass
    # Open models leave stray characters *inside* the outer object, e.g.
    # {"findings":[ ... ]"}  — so parse the findings array on its own.
    key = content.find('"findings"')
    bracket = content.find("[", key) if key >= 0 else -1
    if bracket >= 0:
        try:
            return {"findings": dec.raw_decode(content[bracket:])[0]}
        except json.JSONDecodeError:
            pass
    return {"findings": []}


def _fetched(doc_id: str, node_ids: list[str]) -> list[dict]:
    if not doc_id or not node_ids:
        return []
    try:
        return tools.get_content(doc_id, node_ids)
    except (KeyError, IndexError):
        return []


def _cite(rows: list[dict]) -> str:
    """Citation comes from the node that was actually fetched, never the model."""
    return rows[0].get("cite", "") if rows else ""


def _table_unit(rows: list[dict]) -> str:
    """The scale statement printed in the fetched table, e.g. '(in thousands)'."""
    for r in rows:
        m = re.search(r"\(in (thousands|millions|billions)[^)]*\)",
                      r.get("content", ""), re.I)
        if m:
            return m.group(0)
    return ""


def _grounded(raw: str, rows: list[dict]) -> bool:
    """Does this figure actually appear in the text the agent read?

    A model will report a figure that is not in the document — not as a
    retrieval miss but as a fluent invention, complete with a plausible label
    and a real node id. Reporting that as SUPPORTED, with a working citation
    pointing at a page that does not contain it, is the worst output this
    system can produce.

    So the figure is checked against the fetched content. Digits only, since
    the model reformats separators freely (674,000 / 674000 / $674.0).
    """
    if not raw or not rows:
        return False
    haystack = _digits(" ".join(r.get("content", "") for r in rows))
    return any(d and d in haystack for d in _forms(raw))


def _digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text)


def _norm(text: str) -> str:
    """Case-folded, whitespace-collapsed, punctuation-stripped."""
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())


def quote_grounded(quote: str, rows: list[dict], min_words: int = 3) -> bool:
    """Is this quoted text actually in what the agent read?

    Numeric grounding covers figures, but a claim can be about an entity, a
    date, a segment or a customer name — no digits to check. Those need the
    same guarantee: a fabricated customer must not become evidence merely
    because nothing numeric was there to contradict it.

    Matched on a normalised word sequence, since the model reflows whitespace
    and punctuation when it quotes. Short quotes are refused rather than
    accepted: two common words match almost any filing by accident.
    """
    words = _norm(quote).split()
    if len(words) < min_words:
        return False
    haystack = " ".join(_norm(r.get("content", "")).split())
    return " ".join(words) in haystack


def _forms(raw: str) -> list[str]:
    """Digit forms a figure might legitimately take.

    Rejecting a correct figure is the quieter half of this check going wrong:
    "54,284.00" and "54,284" are the same number, but naive digit-stripping
    makes them 5428400 and 54284, so the evidence would be discarded and the
    claim would come back NO_EVIDENCE with nothing to explain it.
    """
    forms = [_digits(raw)]
    trimmed = re.sub(r"\.0+\b", "", raw)          # 54,284.00 -> 54,284
    forms.append(_digits(trimmed))
    if "." in raw:
        forms.append(_digits(raw.split(".", 1)[0]))  # fall back to the integer part
    return forms


def _trim(node: dict, depth: int) -> dict:
    """ponytail: depth-limited tree. Free tiers cap tokens per minute, and the
    full 128-node tree plus accumulated content blows a 12k budget. Send the
    whole tree in one shot once the token ceiling allows it."""
    out = {"node_id": node["node_id"], "title": node["title"]}
    if node.get("summary"):
        out["summary"] = node["summary"]
    if depth > 0 and node.get("nodes"):
        out["nodes"] = [_trim(c, depth - 1) for c in node["nodes"]]
    return out


def _run_tool(name: str, args: dict) -> str:
    if name == "list_documents":
        return json.dumps(tools.list_documents())
    if name == "get_structure":
        tree = tools.get_structure(args["doc_id"])
        depth = int(args.get("depth", 99))
        return json.dumps(_trim(tree, depth))[:120_000]
    if name == "get_content":
        return json.dumps(tools.get_content(args["doc_id"], args["node_ids"]))[:60_000]
    return json.dumps({"error": f"unknown tool {name}"})


def investigate(claims: list[Claim], model: str | None = None) -> dict[int, Evidence]:
    """One agent run for a group of claims. Returns evidence per claim index."""
    listing = "\n".join(f"[{i}] {c.text}" for i, c in enumerate(claims))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Verify these claims:\n{listing}"}]

    budget = turn_budget(len(claims))
    for _ in range(budget):
        msg = chat(messages, tools=TOOLS, model=model)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return _parse(msg.get("content") or "", claims)
        for call in calls:
            fn = call["function"]
            out = _run_tool(fn["name"], json.loads(fn["arguments"] or "{}"))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})

    raise RuntimeError(f"agent exceeded {budget} turns for {len(claims)} claims")


def _parse(content: str, claims: list[Claim]) -> dict[int, Evidence]:
    data = _loads(content)

    found: dict[int, Evidence] = {}
    for f in data.get("findings", []):
        doc_id, node_ids = f.get("doc_id", ""), f.get("node_ids", [])
        rows = _fetched(doc_id, node_ids)
        quantities, ungrounded = [], []
        for fig in f.get("figures", []):
            # The row label carries basis and period hints; the table's unit
            # statement carries scale. Conflating them silently reads a figure
            # printed in thousands as units and reports a false CONTRADICTED.
            raw = fig.get("raw", "")
            if not _grounded(raw, rows):
                ungrounded.append(raw)
                continue
            # Read the table's unit statement out of the text we fetched rather
            # than trusting the model to report it. "(in thousands)" is printed
            # once in a header, and a figure read as units instead of thousands
            # is wrong by 1000x — too important to leave to a prompt.
            q = parse_quantity(raw,
                               table_unit=fig.get("unit", "") or _table_unit(rows),
                               context=fig.get("label", ""))
            if q is None:
                continue
            p = parse_period(fig.get("period", "")) or q.period
            quantities.append(Quantity(value=q.value, unit=q.unit, scale=q.scale,
                                       period=p, basis=q.basis, raw=q.raw))
        quote = f.get("quote", "")
        # A finding with no figures rests entirely on its quote — entity claims,
        # headcounts stated in prose, segment names. Check the quote the same
        # way a figure is checked, or a fabricated customer becomes evidence.
        if quote and not f.get("figures") and not quote_grounded(quote, rows):
            ungrounded.append(f"quote not in cited text: {quote[:60]}")
            quote = ""
        if ungrounded:
            quote = (f"[dropped, not present in the cited text: "
                     f"{', '.join(ungrounded)}] {quote}").strip()
        found[f.get("claim_index", -1)] = Evidence(
            quantities=quantities,
            covered_periods=[q.period for q in quantities if q.period],
            doc_id=doc_id, node_ids=node_ids,
            # Never trust a model-authored URL — it will invent a plausible one
            # for the wrong company. Resolve it from the node we actually read.
            citation_url=_cite(rows), quote=quote)

    # Every claim gets a record, even an empty one. A missing claim is a silent drop.
    return {i: found.get(i, Evidence()) for i in range(len(claims))}
