"""Verify a set of claims against the corpus and report what happened.

Not a research benchmark. Fifteen or so claims with known answers, run through
the real agent, counted by hand. Enough to tell whether the system works and
where it fails; not enough to support a percentage, so none is reported.

    python3 benchmark.py
"""
from __future__ import annotations

import json
import os
import pathlib
import time

from src.compare import compare
from src.models import Claim, Operation
from src.normalize import parse_period, parse_quantity
from src.verify import investigate

OUT = pathlib.Path(__file__).parent / "ui" / "real_run.json"

# (text, figure, operation, period, expected, why)
# Expectations come from figures verified by hand against DDOG_10K_FY2024.htm.
CASES = [
    ("Revenue was $2.68 billion in FY2024", "$2.68 billion", Operation.ABSOLUTE, "FY2024",
     "SUPPORTED", "10-K reports 2,684,275 thousands"),
    ("GAAP operating income was $54 million in FY2024", "$54 million", Operation.ABSOLUTE, "FY2024",
     "SUPPORTED", "10-K reports 54,284 thousands"),
    ("Net cash from operating activities was $871 million in FY2024", "$871 million",
     Operation.ABSOLUTE, "FY2024", "SUPPORTED", "10-K reports 870,603 thousands"),
    ("Free cash flow was $775 million in FY2024", "$775 million", Operation.ABSOLUTE, "FY2024",
     "SUPPORTED", "10-K reports 775,103 thousands"),
    ("Cost of revenue was $516 million in FY2024", "$516 million", Operation.ABSOLUTE, "FY2024",
     "SUPPORTED", "10-K reports 515,531 thousands"),
    ("Gross profit was $2.17 billion in FY2024", "$2.17 billion", Operation.ABSOLUTE, "FY2024",
     "SUPPORTED", "10-K reports 2,168,744 thousands"),

    # Seeded defects. The figure is wrong on purpose.
    ("Revenue grew 140% year over year in FY2024", "140%", Operation.GROWTH, "FY2024",
     "CONTRADICTED", "seeded: actual growth is 26.1%"),
    ("Revenue was $8.4 billion in FY2024", "$8.4 billion", Operation.ABSOLUTE, "FY2024",
     "CONTRADICTED", "seeded: inflated ~3x"),
    ("GAAP operating income was $540 million in FY2024", "$540 million", Operation.ABSOLUTE, "FY2024",
     "CONTRADICTED", "seeded: 10x the real 54,284"),
    ("Free cash flow was $775 billion in FY2024", "$775 billion", Operation.ABSOLUTE, "FY2024",
     "CONTRADICTED", "seeded: unit error, millions stated as billions"),

    # Basis difference, not a lie. The deck reports both; the 10-K reports GAAP.
    ("Non-GAAP operating income was $674 million in FY2024", "$674 million", Operation.ABSOLUTE,
     "FY2024", "BASIS_MISMATCH|NO_EVIDENCE", "non-GAAP; GAAP figure is 54,284"),

    # No document covers the period.
    ("Revenue was $3.5 billion in FY2026", "$3.5 billion", Operation.ABSOLUTE, "FY2026",
     "NO_SOURCE", "corpus has no FY2026 filing"),
]


def main() -> None:
    model = os.environ.get("LLM_MODEL", "?")
    print(f"model: {model}\ncases: {len(CASES)}\n")
    rows, hits, started = [], 0, time.time()

    for i, (text, fig, op, per, expected, why) in enumerate(CASES, 1):
        claim = Claim(text=text, value=parse_quantity(fig), operation=op,
                      period=parse_period(per))
        t0 = time.time()
        try:
            ev = investigate([claim])[0]
            v = compare(claim, ev)
            got, reason = v.status.value, (v.reason or "")
            figures = [q.raw for q in ev.quantities]
            cite = ev.citation_url
        except Exception as exc:
            got, reason, figures, cite = "RUN_FAILED", f"{type(exc).__name__}: {exc}"[:120], [], ""

        ok = got in expected.split("|")
        hits += ok
        secs = time.time() - t0
        print(f"{'ok ' if ok else 'MISS'} [{i:2}/{len(CASES)}] {got:<15} "
              f"expected {expected:<26} {secs:5.1f}s  {text[:44]}")
        if not ok:
            print(f"     reason: {reason[:96]}")
            print(f"     figures: {figures}  ({why})")

        rows.append({"text": text, "expected": expected, "status": got, "reason": reason,
                     "figures": figures, "cite": cite, "seconds": round(secs, 1),
                     "note": why, "seeded": "seeded" in why, "ok": ok})

    total = time.time() - started
    print(f"\n{hits} of {len(CASES)} as expected · {total:.0f}s total "
          f"· {total/len(CASES):.0f}s per claim · model {model}")
    misses = [r for r in rows if not r["ok"]]
    if misses:
        print("\nmisses:")
        for m in misses:
            print(f"  {m['status']:<15} {m['text'][:52]}")
            print(f"      {m['reason'][:96]}")

    OUT.write_text(json.dumps({"model": model, "claims": rows}, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
