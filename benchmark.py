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
import sys
import time

from src.compare import compare
from src.models import Claim, Operation
from src.normalize import parse_period, parse_quantity
from src.judge import judge
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
    # --judge: the agent states the verdict. Default: the agent returns evidence
    # and compare.py decides. Same cases either way, so the two are comparable.
    use_judge = "--judge" in sys.argv
    mode = "agent decides" if use_judge else "code decides"
    print(f"model: {model}\nmode : {mode}\ncases: {len(CASES)}\n", flush=True)
    rows, hits, started = [], 0, time.time()

    # All claims go to ONE agent run. That is the design: claims are the query,
    # and claims sharing evidence share the fetch. One run per claim re-reads
    # the same income statement twelve times and costs twelve times as much.
    claims = [Claim(text=text, value=parse_quantity(fig), operation=op,
                    period=parse_period(per))
              for text, fig, op, per, _, _ in CASES]

    t0 = time.time()
    try:
        if use_judge:
            results = judge(claims)
            got = {i: (r["status"], r.get("reason", ""),
                       [r["found"]] if r.get("found") else [], r.get("cite", ""))
                   for i, r in results.items()}
        else:
            evidence = investigate(claims)
            got = {}
            for i, c in enumerate(claims):
                v = compare(c, evidence[i])
                got[i] = (v.status.value, v.reason or "",
                          [q.raw for q in evidence[i].quantities],
                          evidence[i].citation_url)
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"[:120]
        got = {i: ("RUN_FAILED", detail, [], "") for i in range(len(CASES))}
    elapsed = time.time() - t0

    for i, (text, _fig, _op, _per, expected, why) in enumerate(CASES):
        status, reason, figures, cite = got.get(i, ("RUN_FAILED", "no result", [], ""))
        ok = status in expected.split("|")
        hits += ok
        print(f"{'ok ' if ok else 'MISS'} [{i+1:2}/{len(CASES)}] {status:<15} "
              f"expected {expected:<26} {text[:46]}", flush=True)
        if not ok:
            print(f"     reason : {reason[:96]}")
            print(f"     figures: {figures}   ({why})", flush=True)

        rows.append({"text": text, "expected": expected, "status": status,
                     "reason": reason, "figures": figures, "cite": cite,
                     "note": why, "seeded": "seeded" in why, "ok": ok})

    print(f"\none agent run for {len(CASES)} claims: {elapsed:.0f}s "
          f"({elapsed/len(CASES):.0f}s per claim)", flush=True)

    total = time.time() - started
    print(f"{hits} of {len(CASES)} as expected · {total:.0f}s total · model {model}")
    misses = [r for r in rows if not r["ok"]]
    if misses:
        print("\nmisses:")
        for m in misses:
            print(f"  {m['status']:<15} {m['text'][:52]}")
            print(f"      {m['reason'][:96]}")

    out = OUT.with_name("real_run_judge.json") if use_judge else OUT
    out.write_text(json.dumps({"model": model, "mode": mode, "claims": rows}, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
