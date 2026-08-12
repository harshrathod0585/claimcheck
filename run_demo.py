"""Produce a real run: real agent, real tools, real filings, recorded to JSON.

Paced for a free-tier token-per-minute cap, so it is slow by design. The UI loads
the output; nothing on the page is hand-authored.

    python3 run_demo.py            # writes ui/real_run.json
"""
from __future__ import annotations

import json
import pathlib
import time

from src import verify
from src.compare import compare
from src.llm import chat
from src.models import Claim, Operation
from src.normalize import parse_period, parse_quantity

OUT = pathlib.Path(__file__).parent / "ui" / "real_run.json"
PACE = 45  # seconds between claims — free tier meters per minute

# Real claims the extractor pulled from the FY2024 Q4 earnings release, plus two
# seeded defects. Seeded ones are labelled so the page never passes them off as real.
SPECS = [
    ("Revenue grew 140% year over year in FY2024", "140%", Operation.GROWTH, "FY2024", True),
    ("38% year-over-year growth in product revenue", "38%", Operation.GROWTH, "FY2024", False),
    ("Product revenue of $2,666.8 million in FY2024", "$2,666.8 million", Operation.ABSOLUTE, "FY2024", False),
    ("Free cash flow of $778.9 million in FY2024", "$778.9 million", Operation.ABSOLUTE, "FY2024", False),
    ("Net cash provided by operating activities of $848.1 million in FY2024",
     "$848.1 million", Operation.ABSOLUTE, "FY2024", False),
    ("Product gross margin of 74% in FY2024", "74%", Operation.MARGIN, "FY2024", False),
]


def investigate_traced(claim: Claim) -> tuple[dict, list[dict]]:
    """verify.investigate, but recording every tool call and every reasoning line."""
    messages = [{"role": "system", "content": verify.SYSTEM},
                {"role": "user", "content": f"Verify these claims:\n[0] {claim.text}"}]
    trace: list[dict] = []

    for _ in range(verify.MAX_TURNS):
        msg = chat(messages, tools=verify.TOOLS)
        messages.append(msg)
        if msg.get("content"):
            trace.append({"kind": "think", "text": msg["content"][:600]})
        calls = msg.get("tool_calls") or []
        if not calls:
            return verify._parse(msg.get("content") or "", [claim]), trace
        for call in calls:
            fn = call["function"]
            args = json.loads(fn["arguments"] or "{}")
            trace.append({"kind": "call", "name": fn["name"],
                          "args": ", ".join(f"{v}" for v in args.values())[:90]})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": verify._run_tool(fn["name"], args)})

    raise RuntimeError("exceeded max turns")


def main() -> None:
    results = []
    for i, (text, fig, op, per, seeded) in enumerate(SPECS):
        claim = Claim(text=text, value=parse_quantity(fig), operation=op,
                      period=parse_period(per))
        print(f"[{i+1}/{len(SPECS)}] {text[:56]}", flush=True)
        try:
            evidence, trace = investigate_traced(claim)
            ev = evidence[0]
            v = compare(claim, ev)
            results.append({
                "text": text, "seeded": seeded, "op": op.value,
                "status": v.status.value, "reason": v.reason,
                "claimed": v.claimed, "actual": v.actual,
                "figures": [q.raw for q in ev.quantities],
                "doc_id": ev.doc_id, "node_ids": ev.node_ids,
                "cite": ev.citation_url, "quote": ev.quote, "trace": trace,
            })
            print(f"      -> {v.status.value} {[q.raw for q in ev.quantities]}", flush=True)
        except Exception as exc:                       # a failed claim is reported, not hidden
            results.append({"text": text, "seeded": seeded, "op": op.value,
                            "status": "RUN_FAILED", "reason": f"{type(exc).__name__}: {exc}"[:200],
                            "figures": [], "trace": []})
            print(f"      -> FAILED {type(exc).__name__}", flush=True)

        if i < len(SPECS) - 1:
            time.sleep(PACE)

    OUT.write_text(json.dumps({"claims": results}, indent=2))
    print(f"\nwrote {OUT} · {len(results)} claims", flush=True)


if __name__ == "__main__":
    main()
