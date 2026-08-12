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

MAX_TURNS = 8

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


def _cite(doc_id: str, node_ids: list[str]) -> str:
    """Citation comes from the node that was actually fetched, never the model."""
    if not doc_id or not node_ids:
        return ""
    try:
        rows = tools.get_content(doc_id, node_ids[:1])
    except (KeyError, IndexError):
        return ""
    return rows[0].get("cite", "") if rows else ""


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


def investigate(claims: list[Claim]) -> dict[int, Evidence]:
    """One agent run for a group of claims. Returns evidence per claim index."""
    listing = "\n".join(f"[{i}] {c.text}" for i, c in enumerate(claims))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Verify these claims:\n{listing}"}]

    for _ in range(MAX_TURNS):
        msg = chat(messages, tools=TOOLS)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return _parse(msg.get("content") or "", claims)
        for call in calls:
            fn = call["function"]
            out = _run_tool(fn["name"], json.loads(fn["arguments"] or "{}"))
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})

    raise RuntimeError(f"agent exceeded {MAX_TURNS} turns")  # fail the group, not the run


def _parse(content: str, claims: list[Claim]) -> dict[int, Evidence]:
    data = _loads(content)

    found: dict[int, Evidence] = {}
    for f in data.get("findings", []):
        quantities = []
        for fig in f.get("figures", []):
            # The row label carries basis and period hints; the table's unit
            # statement carries scale. Conflating them silently reads a figure
            # printed in thousands as units and reports a false CONTRADICTED.
            q = parse_quantity(fig.get("raw", ""),
                               table_unit=fig.get("unit", ""),
                               context=fig.get("label", ""))
            if q is None:
                continue
            p = parse_period(fig.get("period", "")) or q.period
            quantities.append(Quantity(value=q.value, unit=q.unit, scale=q.scale,
                                       period=p, basis=q.basis, raw=q.raw))
        doc_id, node_ids = f.get("doc_id", ""), f.get("node_ids", [])
        found[f.get("claim_index", -1)] = Evidence(
            quantities=quantities,
            covered_periods=[q.period for q in quantities if q.period],
            doc_id=doc_id, node_ids=node_ids,
            # Never trust a model-authored URL — it will invent a plausible one
            # for the wrong company. Resolve it from the node we actually read.
            citation_url=_cite(doc_id, node_ids), quote=f.get("quote", ""))

    # Every claim gets a record, even an empty one. A missing claim is a silent drop.
    return {i: found.get(i, Evidence()) for i in range(len(claims))}
