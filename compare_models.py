"""Run the same claims through several models at once and print one table.

Models run concurrently: nothing about one model's run depends on another's,
and each is mostly waiting on the network. Sequentially this takes the sum of
five runs; in parallel it takes the slowest one.

Concurrency is only possible because the model is a per-call parameter rather
than process-global state. When it was a module global, two models in flight
would race on the same variable and results would be attributed to the wrong
model, which is worse than slow.

    python3 compare_models.py             # agent decides
    python3 compare_models.py --evidence  # agent returns evidence, compare.py decides
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from benchmark import CASES
from src.compare import compare
from src.judge import judge
from src.models import Claim
from src.normalize import parse_period, parse_quantity
from src.verify import investigate

OUT = pathlib.Path(__file__).parent / "ui" / "model_comparison.json"

MODELS = [
    "qwen/qwen3-235b-a22b-2507",
    "qwen/qwen3-235b-a22b-2507",
    "qwen/qwen3-235b-a22b-2507",
]


def build_claims() -> list[Claim]:
    return [Claim(text=t, value=parse_quantity(f), operation=o,
                  period=parse_period(p))
            for t, f, o, p, _, _ in CASES]


def run_one(model: str, use_judge: bool) -> dict:
    claims = build_claims()
    t0 = time.time()
    rows, rejected, failed = [], 0, False

    try:
        if use_judge:
            results = judge(claims, model=model)
            for i, (_t, _f, _o, _p, expected, why) in enumerate(CASES):
                r = results.get(i, {})
                status = r.get("status", "MISSING")
                if r.get("rejected"):
                    rejected += 1
                rows.append({"i": i, "status": status, "expected": expected,
                             "ok": status in expected.split("|"),
                             "rejected": r.get("rejected", ""), "why": why})
        else:
            evidence = investigate(claims, model=model)
            for i, (_t, _f, _o, _p, expected, why) in enumerate(CASES):
                v = compare(claims[i], evidence[i])
                rows.append({"i": i, "status": v.status.value, "expected": expected,
                             "ok": v.status.value in expected.split("|"),
                             "rejected": "", "why": why})
    except Exception as exc:
        failed = True
        detail = f"{type(exc).__name__}: {exc}"[:120]
        rows = [{"i": i, "status": "RUN_FAILED", "expected": e, "ok": False,
                 "rejected": detail, "why": w}
                for i, (_t, _f, _o, _p, e, w) in enumerate(CASES)]

    secs = round(time.time() - t0, 1)
    hits = sum(r["ok"] for r in rows)
    print(f"   done {model:<38} {hits:>2}/{len(rows)} · {secs:>5.0f}s · "
          f"{rejected} rejected{' · FAILED' if failed else ''}", flush=True)
    return {"model": model, "hits": hits, "total": len(rows), "seconds": secs,
            "rejected_evidence": rejected, "run_failed": failed, "rows": rows}


def main() -> None:
    use_judge = "--evidence" not in sys.argv
    mode = "agent decides" if use_judge else "code decides"
    print(f"mode: {mode}\nmodels: {len(MODELS)} (in parallel)\n", flush=True)

    started = time.time()
    with ThreadPoolExecutor(max_workers=len(MODELS)) as pool:
        results = list(pool.map(lambda m: run_one(m, use_judge), MODELS))
    wall = time.time() - started

    print(f"\n{'model':<40}{'correct':>9}{'time':>8}{'rejected':>10}")
    print("-" * 67)
    for r in sorted(results, key=lambda x: (-x["hits"], x["seconds"])):
        mark = "  FAILED" if r["run_failed"] else ""
        print(f"{r['model']:<40}{r['hits']:>4}/{r['total']:<4}"
              f"{r['seconds']:>7.0f}s{r['rejected_evidence']:>10}{mark}")
    print(f"\nwall clock {wall:.0f}s "
          f"(sequential would be {sum(r['seconds'] for r in results):.0f}s)")

    # Which cases every model got wrong is more useful than any single score.
    common = [i for i in range(len(CASES))
              if all(not r["rows"][i]["ok"] for r in results if r["rows"])]
    if common:
        print("\nmissed by every model:")
        for i in common:
            print(f"  {CASES[i][0][:56]}  ({CASES[i][5]})")

    OUT.write_text(json.dumps({"mode": mode, "wall_seconds": round(wall, 1),
                               "results": results}, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
