"""FastAPI + SSE. Thin — orchestration only, no verification logic.

Two modes:
  GET /run            replays the committed recorded run. No model calls, no key,
                      no spend. This is what a public deployment should serve.
  POST /verify        a real run. Gated behind VERIFY_ENABLED because a public
                      endpoint backed by a metered API key is an open wallet.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

UI = pathlib.Path(__file__).parent.parent / "ui"
VERIFY_ENABLED = os.environ.get("VERIFY_ENABLED", "0") == "1"
MAX_CLAIMS = int(os.environ.get("MAX_CLAIMS_PER_REQUEST", "6"))

app = FastAPI(title="ClaimCheck")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ALLOW_ORIGINS", "*").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


CORPUS = pathlib.Path(__file__).parent.parent / "corpus"
ALLOWED = {".htm", ".html", ".md", ".pdf"}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "live_verify": VERIFY_ENABLED}


@app.get("/documents")
def documents() -> list[dict]:
    from .tools import list_documents
    return list_documents()


@app.post("/upload")
async def upload(role: str = Form("room"), files: list[UploadFile] = File(...)) -> dict:
    """Accept documents, index them, report what each became.

    A rejected file is named and explained rather than silently ignored.
    """
    from .loader import load
    from .tree import NoStructure, build_tree, walk

    out = []
    for f in files:
        suffix = pathlib.Path(f.filename or "").suffix.lower()
        if suffix not in ALLOWED:
            out.append({"name": f.filename, "ok": False,
                        "detail": f"unsupported format {suffix or '(none)'}"})
            continue

        dest = CORPUS / pathlib.Path(f.filename).name
        dest.write_bytes(await f.read())
        try:
            doc = load(dest)
            tree = build_tree(doc)
            nodes = sum(1 for _ in walk(tree))
            out.append({"name": dest.name, "ok": True, "role": role,
                        "doc_id": dest.stem, "nodes": nodes,
                        "bytes": dest.stat().st_size,
                        "detail": f"{nodes} sections indexed"})
        except NoStructure as exc:
            dest.unlink(missing_ok=True)
            out.append({"name": f.filename, "ok": False,
                        "detail": f"no recoverable structure: {exc}"})
        except Exception as exc:
            dest.unlink(missing_ok=True)
            out.append({"name": f.filename, "ok": False,
                        "detail": f"{type(exc).__name__}: {exc}"[:160]})

    # tools caches the corpus listing; drop it so new files are visible
    from . import tools as _t
    _t._paths.cache_clear()
    _t._manifest.cache_clear()
    return {"documents": out}


@app.post("/fetch")
async def fetch_url(body: dict) -> dict:
    """Pull a filing straight from a URL, then index it like an upload.

    Fetching a user-supplied URL server-side is an SSRF surface, so private and
    loopback addresses are refused even though this normally runs locally.
    """
    import ipaddress
    import socket
    import urllib.parse
    import urllib.request

    from .loader import load
    from .tree import NoStructure, build_tree, walk

    url = (body.get("url") or "").strip()
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(400, "url must be http or https")

    try:
        resolved = socket.gethostbyname(parts.hostname)
    except socket.gaierror:
        raise HTTPException(400, f"cannot resolve {parts.hostname}") from None
    addr = ipaddress.ip_address(resolved)
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise HTTPException(400, "refusing to fetch a private address")

    name = pathlib.Path(parts.path).name or "document.htm"
    if pathlib.Path(name).suffix.lower() not in ALLOWED:
        name += ".htm"

    # EDGAR requires a descriptive User-Agent and rejects the default one.
    req = urllib.request.Request(url, headers={
        "User-Agent": os.environ.get("FETCH_UA", "ClaimCheck research contact@example.com")})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read(int(os.environ.get("MAX_FETCH_BYTES", 40_000_000)))
    except Exception as exc:
        raise HTTPException(400, f"fetch failed: {type(exc).__name__}: {exc}"[:200]) from None

    dest = CORPUS / name
    dest.write_bytes(data)
    try:
        tree = build_tree(load(dest))
        nodes = sum(1 for _ in walk(tree))
    except NoStructure as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"no recoverable structure: {exc}") from None
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"{type(exc).__name__}: {exc}"[:200]) from None

    from . import tools as _t
    _t._paths.cache_clear()
    _t._manifest.cache_clear()
    return {"doc_id": dest.stem, "name": dest.name, "nodes": nodes,
            "bytes": len(data), "source": url}


@app.post("/extract")
async def extract_claims(body: dict) -> dict:
    """Run the real extractor over one document. Returns typed claims."""
    from .extract import extract
    from .loader import load
    from .tools import _paths

    doc_id = body.get("doc_id") or ""
    paths = _paths()
    if doc_id not in paths:
        raise HTTPException(404, f"unknown doc_id {doc_id!r}; have {sorted(paths)}")

    claims = await asyncio.to_thread(
        extract, load(paths[doc_id]).markdown, int(body.get("max_chars", 26_000)))
    return {"claims": [{
        "text": c.text, "operation": c.operation.value, "figure": c.value.raw,
        "period": c.period.label if c.period else "",
    } for c in claims]}


@app.get("/run")
async def replay(delay: float = 0.5) -> StreamingResponse:
    """Stream the recorded run. Free, deterministic, safe to expose."""
    path = UI / "real_run.json"
    if not path.exists():
        raise HTTPException(404, "no recorded run committed")
    claims = json.loads(path.read_text())["claims"]

    async def gen():
        for c in claims:
            for t in c.get("trace", []):
                yield _sse("trace", t)
                await asyncio.sleep(delay / 4)
            yield _sse("verdict", {k: v for k, v in c.items() if k != "trace"})
            await asyncio.sleep(delay)
        yield _sse("done", {"count": len(claims)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.post("/verify")
async def verify_live(body: dict) -> StreamingResponse:
    """A real run. Off by default — turning this on spends money per request."""
    if not VERIFY_ENABLED:
        raise HTTPException(403, "live verification disabled; set VERIFY_ENABLED=1")

    from .compare import compare
    from .models import Claim, Operation
    from .normalize import parse_period, parse_quantity
    from .verify import investigate

    specs = (body.get("claims") or [])[:MAX_CLAIMS]
    if not specs:
        raise HTTPException(400, "no claims supplied")

    async def gen():
        for spec in specs:
            q = parse_quantity(spec.get("figure", ""))
            if q is None:
                yield _sse("verdict", {"text": spec.get("text", ""), "status": "RUN_FAILED",
                                       "reason": "unparseable figure"})
                continue
            claim = Claim(text=spec.get("text", ""), value=q,
                          operation=Operation(spec.get("operation", "absolute")),
                          period=parse_period(spec.get("period", "")))
            try:
                ev = (await asyncio.to_thread(investigate, [claim]))[0]
                v = compare(claim, ev)
                yield _sse("verdict", {"text": claim.text, "status": v.status.value,
                                       "reason": v.reason, "claimed": v.claimed,
                                       "actual": v.actual, "cite": ev.citation_url,
                                       "figures": [x.raw for x in ev.quantities]})
            except Exception as exc:  # one claim failing must not kill the stream
                yield _sse("verdict", {"text": claim.text, "status": "RUN_FAILED",
                                       "reason": f"{type(exc).__name__}: {exc}"[:200]})
        yield _sse("done", {"count": len(specs)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
