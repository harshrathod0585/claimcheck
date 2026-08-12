"""The corpus-facing tools the verification agent calls.

Three of the four PRD tools live here; `search` (BM25) is a later slice.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .loader import Document, load
from .tree import Node, build_tree, find, path_to

CORPUS = Path(__file__).resolve().parent.parent / "corpus"

# ponytail: metadata for the one committed document, overridden by
# corpus/manifest.json once the fetch script writes one.
DEFAULT_MANIFEST = {
    "SNOW_10K_FY2024": {
        "type": "10-K",
        "period": "FY2024 (fiscal year ended January 31, 2024)",
        "url": "https://www.sec.gov/Archives/edgar/data/1640147/000164014724000101/snow-20240131.htm",
    }
}


@lru_cache(maxsize=1)
def _manifest() -> dict:
    path = CORPUS / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else DEFAULT_MANIFEST


@lru_cache(maxsize=1)
def _paths() -> dict[str, Path]:
    return {
        p.stem: p
        for p in sorted(CORPUS.iterdir())
        if p.suffix.lower() in (".htm", ".html", ".pdf", ".md")
    }


@lru_cache(maxsize=8)
def _ingest(doc_id: str) -> tuple[Document, Node]:
    """ponytail: process-local memo. Swap for the Redis cache keyed on
    doc.sha256 when ingest moves behind an API."""
    if doc_id not in _paths():
        raise KeyError(f"unknown doc_id {doc_id!r}; have {sorted(_paths())}")
    doc = load(_paths()[doc_id])
    return doc, build_tree(doc)


def list_documents() -> list[dict]:
    """Documents, each labelled with its role.

    The deck is the thing being checked; the filings are what it is checked
    against. Without that distinction an agent will happily read the deck as
    its own evidence and report that it agrees with itself.
    """
    meta = _manifest()
    out = []
    for d in _paths():
        info = meta.get(d, {})
        kind = info.get("type", "document")
        is_deck = "deck" in kind.lower() or "ex-99" in kind.lower()
        out.append({
            "doc_id": d,
            "type": kind,
            "period": info.get("period"),
            "role": "assertion (the deck being checked)" if is_deck
                    else "evidence (a filing to check against)",
        })
    return out


def get_structure(doc_id: str) -> Node:
    """The full tree — titles, summaries, addresses. Never text."""
    return _ingest(doc_id)[1]


def get_content(doc_id: str, node_ids: list[str]) -> list[dict]:
    doc, tree = _ingest(doc_id)
    lines = doc.lines
    url = _manifest().get(doc_id, {}).get("url", "")
    out = []
    for node_id in node_ids:
        node = find(tree, node_id)
        if node is None:
            raise KeyError(f"unknown node_id {node_id!r} in {doc_id}")
        addr = node["addr"]
        if "line_start" in addr:
            content = "\n".join(lines[addr["line_start"] - 1 : addr["line_end"]])
            anchor = addr.get("anchor")
            cite = f"{url}#{anchor}" if (url and anchor) else url
        else:
            content = "\n".join(
                lines[ln - 1] for ln, p in doc.pages.items() if addr["page_start"] <= p <= addr["page_end"]
            )
            cite = f"{url}#page={addr['page_start']}" if url else ""
        out.append(
            {
                "doc_id": doc_id,
                "node_id": node_id,
                "title": node["title"],
                "path": " › ".join(path_to(tree, node_id)),
                "content": content,
                "cite": cite,
                "loc": addr,
            }
        )
    return out


if __name__ == "__main__":
    print(json.dumps(list_documents(), indent=2))
    tree = get_structure("SNOW_10K_FY2024")
    for part in tree["nodes"]:
        print(part["node_id"], part["title"][:70])
