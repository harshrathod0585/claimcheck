"""Load PDF / HTML / Markdown into one normalized Markdown Document.

Everything format-specific stops here. Downstream sees markdown text plus a
line -> anchor map and nothing else.
"""

from __future__ import annotations

import hashlib
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", module="bs4")

BLOCK = {"div", "p", "li", "tr", "td", "th", "table", "body", "html", "h1", "h2", "h3", "h4", "h5", "h6"}
SYMBOLS = {"$", "%", "(", ")", "—", "-"}
NOISE = {"table of contents", ""}


@dataclass
class Document:
    doc_id: str
    doc_type: str  # html | pdf | md
    markdown: str
    anchors: dict[int, str] = field(default_factory=dict)  # 1-based line -> html id
    pages: dict[int, int] = field(default_factory=dict)  # 1-based line -> pdf page
    sha256: str = ""

    @property
    def lines(self) -> list[str]:
        return self.markdown.split("\n")


def load(path: str | Path) -> Document:
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    ext = path.suffix.lower()
    if ext in (".htm", ".html"):
        doc = _load_html(raw.decode("utf-8", "replace"), path.stem)
    elif ext == ".pdf":
        doc = _load_pdf(path)
    elif ext in (".md", ".markdown", ".txt"):
        doc = Document(path.stem, "md", raw.decode("utf-8", "replace"))
    else:
        raise ValueError(f"unsupported format {ext!r} for {path}")
    doc.sha256 = sha
    return doc


# --------------------------------------------------------------------------- html


def _style_bold(el) -> bool:
    if el.name in ("b", "strong"):
        return True
    st = el.get("style") or ""
    return "font-weight:7" in st or "font-weight:bold" in st


def _is_heading(el, text: str) -> bool:
    """EDGAR has no <h1>, so headings there are short fully-bold blocks.

    Ordinary HTML does have heading tags, and a document that uses them was
    building no tree at all — every non-EDGAR page would have been rejected as
    structureless.
    """
    if not text or len(text) > 200 or text.lower() in NOISE:
        return False
    if getattr(el, "name", "") in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return True
    if re.match(r"^(PART|ITEM)\s+[IVX0-9]", text, re.I):
        return True
    spans = el.find_all(["span", "font", "b", "strong"])
    if spans:
        return all(_style_bold(s) or not s.get_text(strip=True) for s in spans)
    return _style_bold(el)  # press releases bold the block itself, not a span


def _level(text: str, el=None) -> int:
    name = getattr(el, "name", "") if el is not None else ""
    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        return int(name[1])
    if re.match(r"^PART\s+[IVX]+", text, re.I):
        return 1
    if re.match(r"^ITEM\s+\d", text, re.I):
        return 2
    return 3


def _tidy(cell: str) -> str:
    """`( 1,234 )` -> `(1,234)`, `$ 12` -> `$12`."""
    cell = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", cell))
    return re.sub(r"([$(])\s+", r"\1", cell).strip()


def _cell_text(td) -> str:
    return re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()


def _grid(table) -> list[list[str]]:
    """Expand colspans, duplicating text across every column a cell covers."""
    rows = []
    for tr in table.find_all("tr"):
        row = []
        for td in tr.find_all(["td", "th"], recursive=False) or tr.find_all(["td", "th"]):
            txt = _cell_text(td)
            row.extend([txt] * max(1, int(td.get("colspan") or 1)))
        rows.append(row)
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def _mergeable(a: str, b: str) -> bool:
    return not a or not b or a == b or a in SYMBOLS or b in SYMBOLS


def _join(a: str, b: str) -> str:
    if a == b or not b:
        return a
    if not a:
        return b
    return a + b if (a in SYMBOLS or b in SYMBOLS) else f"{a} {b}"


def _collapse(rows: list[list[str]]) -> list[list[str]]:
    """EDGAR tables are layout grids: spacer columns, a lone '$' column, a lone
    ')' column. Drop empty columns, then greedily merge adjacent columns that
    never conflict, which reattaches currency signs and header spans to their
    numbers.

    ponytail: purely structural heuristic, no style inspection. If a real table
    ever over-merges, gate the merge on the column being <=2 chars wide.
    """
    if not rows:
        return rows
    cols = [list(c) for c in zip(*rows)]
    cols = [c for c in cols if any(x for x in c)]
    out: list[list[str]] = []
    for col in cols:
        if out and all(_mergeable(a, b) for a, b in zip(out[-1], col)):
            out[-1] = [_join(a, b) for a, b in zip(out[-1], col)]
        else:
            out.append(col)
    return [list(r) for r in zip(*out)] if out else []


def _merge_header(rows: list[list[str]]) -> list[list[str]]:
    """EDGAR splits a column header over two rows ("Fiscal Year Ended January
    31," / "2024"). Fold the first into the second so the year stays attached
    to the column it labels."""
    if len(rows) < 2:
        return rows
    top = [c for c in rows[0] if c]
    if len(top) > 1 and len(set(top)) == 1 and any(rows[1]):
        merged = [_join(a, b) for a, b in zip(rows[0], rows[1])]
        return [merged] + rows[2:]
    return rows


def _table_md(table) -> str:
    rows = [r for r in _collapse(_grid(table)) if any(x for x in r)]
    rows = _merge_header(rows)
    if not rows:
        return ""
    esc = lambda r: "| " + " | ".join(_tidy(c).replace("|", "\\|") for c in r) + " |"
    head, body = rows[0], rows[1:]
    return "\n".join([esc(head), "| " + " | ".join("---" for _ in head) + " |", *map(esc, body)])


def _leaf_blocks(node):
    """Yield (kind, element) in document order. Tables are atomic; text blocks
    are the innermost div/p that contain no further block elements."""
    for child in node.children:
        if getattr(child, "name", None) is None:
            continue
        if child.get("id") and ":" not in child.name:  # skip ix:* XBRL tag ids
            yield "anchor", child
        if child.name == "table":
            yield "table", child
        elif child.find(BLOCK - {"td", "th", "tr"}) is not None:
            yield from _leaf_blocks(child)
        elif child.name in BLOCK:
            yield "text", child
        else:
            yield from _leaf_blocks(child)


def _load_html(html: str, doc_id: str) -> Document:
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup
    out: list[str] = []
    anchors: dict[int, str] = {}
    # EDGAR puts one id'd <div> at the top of each rendered page; that is the
    # deep-link target, so a heading cites the page anchor it sits under.
    cur_anchor: str | None = None

    def emit(text: str, anchor: str | None = None):
        # one list entry per physical line, or line numbers desync on tables
        for line in text.split("\n"):
            out.append(line)
        if anchor:
            anchors[len(out)] = anchor

    for kind, el in _leaf_blocks(body):
        if kind == "anchor":
            cur_anchor = el["id"]
            continue
        if kind == "table":
            md = _table_md(el)
            if md:
                emit("")
                emit(md)
            continue
        text = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if not text or text.lower() in NOISE or re.fullmatch(r"\d{1,3}", text):
            continue
        if _is_heading(el, text):
            emit("")
            emit("#" * _level(text, el) + " " + text, cur_anchor)
        else:
            emit("")
            emit(text)
    return Document(doc_id, "html", "\n".join(out), anchors=anchors)


# --------------------------------------------------------------------------- pdf


def _load_pdf(path: Path) -> Document:
    from pypdf import PdfReader

    out: list[str] = []
    pages: dict[int, int] = {}
    for n, page in enumerate(PdfReader(str(path)).pages, 1):
        out.append(f"# Page {n}")
        pages[len(out)] = n
        for line in (page.extract_text() or "").split("\n"):
            out.append(line.strip())
            pages[len(out)] = n
        out.append("")
    return Document(path.stem, "pdf", "\n".join(out), pages=pages)


if __name__ == "__main__":
    import sys

    d = load(sys.argv[1])
    print(d.doc_type, len(d.markdown), "chars,", len(d.anchors), "anchors")
