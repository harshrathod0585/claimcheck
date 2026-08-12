"""Run the real extractor over the real deck and write ui/extracted.json.

Separate from run_demo.py so the two never contend for the same
tokens-per-minute budget.
"""
from __future__ import annotations

import json
import pathlib

from src.extract import extract
from src.loader import load

DECK = pathlib.Path(__file__).parent / "corpus" / "SNOW_8K_EX99-1_FY2024Q4.htm"
OUT = pathlib.Path(__file__).parent / "ui" / "extracted.json"

# Claims carried through to verification in run_demo.py, matched on figure text.
CARRIED = {"38%", "$2,666.8 million", "2,666.8", "$778.9 million", "778.9",
           "$848.1 million", "848.1", "74%"}


def main() -> None:
    claims = extract(load(DECK).markdown, max_chars=26_000)
    rows = [{
        "text": c.text,
        "operation": c.operation.value,
        "figure": c.value.raw,
        "period": c.period.label if c.period else "",
        "carried": c.value.raw in CARRIED,
    } for c in claims]
    OUT.write_text(json.dumps({"claims": rows}, indent=2))
    print(f"wrote {OUT} · {len(rows)} claims")
    for r in rows:
        print(" ", "▸" if r["carried"] else " ", r["operation"].ljust(9),
              r["figure"].ljust(14), r["text"][:56])


if __name__ == "__main__":
    main()
