"""Build a node tree from a normalized Markdown Document.

Nodes are pointers, never text. The whole tree has to fit in one prompt, so
serialized size is a hard constraint and small nodes are folded into parents.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .loader import Document

MAX_CHARS = 80_000  # ~20k tokens ~ 10 pages
MIN_LINES = 6  # a shorter section is not a useful retrieval target
_IS_ITEM = re.compile(r"^(PART|ITEM)\s", re.I)
Node = dict[str, Any]


class NoStructure(Exception):
    """Raised when a document has no recoverable heading structure."""


def build_tree(doc: Document) -> Node:
    lines = doc.lines
    heads = [
        (n, len(m.group(1)), m.group(2).strip())
        for n, line in enumerate(lines, 1)
        if (m := re.match(r"^(#{1,6})\s+(.*)$", line))
    ]
    root: Node = _node("root", doc.doc_id, 1, len(lines), doc)
    if len(heads) < 1:
        root["nodes"].append(_node("n1", doc.doc_id, 1, len(lines), doc))
        return root
    stack: list[tuple[int, Node]] = [(0, root)]
    counter = 0
    for idx, (line_no, level, title) in enumerate(heads):
        end = (heads[idx + 1][0] - 1) if idx + 1 < len(heads) else len(lines)
        counter += 1
        node = _node(f"n{counter}", title, line_no, end, doc)
        while stack and stack[-1][0] >= level:
            stack.pop()
        (stack[-1][1] if stack else root)["nodes"].append(node)
        stack.append((level, node))

    _extend_ends(root)
    _prune(root, lines)
    _split(root, lines, doc)
    return root


def _node(node_id: str, title: str, start: int, end: int, doc: Document) -> Node:
    if doc.doc_type == "pdf":
        pages = [p for ln, p in doc.pages.items() if start <= ln <= end]
        addr = {"page_start": min(pages, default=0), "page_end": max(pages, default=0)}
    else:
        addr = {"line_start": start, "line_end": end, "anchor": doc.anchors.get(start)}
    return {"node_id": node_id, "title": title, "summary": None, "addr": addr, "nodes": []}


def _key(node: Node) -> str:
    return "line_end" if "line_end" in node["addr"] else "page_end"


def _extend_ends(node: Node) -> None:
    """A parent spans through its last child."""
    for child in node["nodes"]:
        _extend_ends(child)
    if node["nodes"]:
        k = _key(node)
        node["addr"][k] = max(node["addr"][k], node["nodes"][-1]["addr"][k])


def _span(node: Node, lines: list[str]) -> int:
    a = node["addr"]
    return a.get("line_end", 0) - a.get("line_start", 0)


def _prune(node: Node, lines: list[str]) -> None:
    """Fold away leaves too small to navigate to. Their lines stay inside the
    parent's span, so nothing becomes unreachable."""
    for child in node["nodes"]:
        _prune(child, lines)
    node["nodes"] = [
        c
        for c in node["nodes"]
        if c["nodes"]
        or _span(c, lines) >= MIN_LINES
        or "line_start" not in c["addr"]
        or _IS_ITEM.match(c["title"])  # an Item section is always a target, however short
    ]


def _split(node: Node, lines: list[str], doc: Document) -> None:
    """Bound leaf size. Oversized leaves get part-children on line boundaries."""
    for child in node["nodes"]:
        _split(child, lines, doc)
    if node["nodes"] or "line_start" not in node["addr"]:
        return
    start, end = node["addr"]["line_start"], node["addr"]["line_end"]
    text = "\n".join(lines[start - 1 : end])
    if len(text) <= MAX_CHARS:
        return
    parts = -(-len(text) // MAX_CHARS)
    step = -(-(end - start + 1) // parts)
    for i in range(parts):
        s = start + i * step
        e = min(end, s + step - 1)
        node["nodes"].append(
            _node(f"{node['node_id']}p{i + 1}", f"{node['title']} (part {i + 1})", s, e, doc)
        )


# --------------------------------------------------------------------------- summaries


def summarize(
    tree: Node, llm: Callable[[str], str] | None = None, cache: dict | None = None
) -> Node:
    """Fill node summaries. No llm -> no-op, so ingest runs without an API key.

    `cache` is any dict-like keyed by node_id (a Redis-backed mapping drops in
    unchanged), so summaries survive a rebuild.
    """
    if llm is None and cache is None:
        return tree
    for node in walk(tree):
        if node["summary"] is not None:
            continue
        if cache is not None and node["node_id"] in cache:
            node["summary"] = cache[node["node_id"]]
        elif llm is not None:
            node["summary"] = llm(node["title"])
            if cache is not None:
                cache[node["node_id"]] = node["summary"]
    return tree


def walk(node: Node):
    yield node
    for child in node["nodes"]:
        yield from walk(child)


def find(tree: Node, node_id: str) -> Node | None:
    return next((n for n in walk(tree) if n["node_id"] == node_id), None)


def path_to(tree: Node, node_id: str) -> list[str]:
    """Titles from root to node, e.g. ['PART II', 'ITEM 8.', 'CONSOLIDATED ...']."""

    def rec(node, trail):
        trail = trail + [node["title"]]
        if node["node_id"] == node_id:
            return trail
        for child in node["nodes"]:
            if (hit := rec(child, trail)) is not None:
                return hit
        return None

    return (rec(tree, []) or [])[1:]  # drop the synthetic root
