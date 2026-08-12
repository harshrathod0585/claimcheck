#!/usr/bin/env python3
"""Download the ClaimCheck demo corpus from SEC EDGAR.

Snowflake (CIK 0001640147): the FY2024 10-K, the most recent 10-Q, and the most
recent 8-K EX-99.1 exhibit. Idempotent: files already on disk are skipped.

SEC requires a descriptive User-Agent and <=10 requests/second. Both enforced below.
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

CIK = "0001640147"
TICKER = "SNOW"
TENK_FISCAL_YEAR = 2024  # pinned: the committed demo corpus is built on FY2024
USER_AGENT = "ClaimCheck harsh.rathod0585@gmail.com"
MIN_INTERVAL = 0.15  # ~6.7 req/s, under SEC's 10/s ceiling
ARCHIVES = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}"

OUT = Path(__file__).parent
_last = 0.0


def get(url: str) -> bytes:
    """Rate-limited GET with the SEC-required User-Agent."""
    global _last
    wait = MIN_INTERVAL - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as r:
        return r.read()


def save(name: str, url: str) -> None:
    path = OUT / name
    if path.exists():
        print(f"skip   {name}  ({path.stat().st_size:,} bytes already on disk)")
        return
    body = get(url)
    path.write_bytes(body)
    print(f"fetch  {name}  ({len(body):,} bytes)\n       {url}")


def filings():
    data = json.loads(get(f"https://data.sec.gov/submissions/CIK{CIK}.json"))
    r = data["filings"]["recent"]
    keys = ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument")
    return [dict(zip(keys, row)) for row in zip(*(r[k] for k in keys))]


def documents(accession: str):
    """[(filename, exhibit_type)] for a filing, from its EDGAR index page."""
    acc = accession.replace("-", "")
    html = get(f"{ARCHIVES}/{acc}/{accession}-index.html").decode("utf-8", "replace")
    rows = re.findall(r"<tr\b.*?</tr>", html, re.S)
    docs = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        href = re.search(r'href="([^"]+)"', row)
        if href and len(cells) >= 4:
            docs.append((href.group(1).rsplit("/", 1)[-1], cells[3].strip()))
    return docs


def find_deck(all_filings):
    """Most recent 8-K EX-99.1. Prefers a real PDF slide deck over an HTML release."""
    fallback = None
    for f in (f for f in all_filings if f["form"] == "8-K"):
        for name, kind in documents(f["accessionNumber"]):
            if kind != "EX-99.1":
                continue
            url = f"{ARCHIVES}/{f['accessionNumber'].replace('-', '')}/{name}"
            if name.lower().endswith(".pdf"):
                return f, name, url, True
            fallback = fallback or (f, name, url, False)
        if fallback:  # newest EX-99.1 wins; older PDFs aren't worth the extra requests
            break
    return fallback


def main() -> int:
    OUT.mkdir(exist_ok=True)
    all_filings = filings()

    tenk = next(f for f in all_filings
                if f["form"] == "10-K" and f["reportDate"].startswith(str(TENK_FISCAL_YEAR)))
    acc = tenk["accessionNumber"].replace("-", "")
    save(f"{TICKER}_10K_FY{TENK_FISCAL_YEAR}.htm", f"{ARCHIVES}/{acc}/{tenk['primaryDocument']}")

    tenq = next(f for f in all_filings if f["form"] == "10-Q")
    acc = tenq["accessionNumber"].replace("-", "")
    save(f"{TICKER}_10Q_{tenq['reportDate']}.htm", f"{ARCHIVES}/{acc}/{tenq['primaryDocument']}")

    deck = find_deck(all_filings)
    if not deck:
        print("WARN   no 8-K EX-99.1 found", file=sys.stderr)
        return 1
    f, name, url, is_pdf = deck
    ext = "pdf" if is_pdf else "htm"
    save(f"{TICKER}_8K_EX99-1_{f['filingDate']}.{ext}", url)
    if not is_pdf:
        print(f"NOTE   EX-99.1 is HTML ({name}), not a PDF slide deck. Snowflake files no "
              f"PDF exhibits; the deck path is exercised with an HTML earnings release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
