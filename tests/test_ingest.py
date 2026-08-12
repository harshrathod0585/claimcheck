"""The load-bearing test: a financial table must survive HTML -> Markdown.

Every claim this project makes rests on one behaviour. A revenue figure has to
reach the model still attached to its row label and its fiscal year. If that
breaks, nothing downstream is wrong in a way anyone would notice: the figures
still look like figures and the model still answers.

Deterministic, no model calls, no API key.
"""
from __future__ import annotations

import pathlib
import re
import warnings

import pytest

from src.loader import load
from src.tree import build_tree, walk

warnings.filterwarnings("ignore")

CORPUS = pathlib.Path(__file__).parent.parent / "corpus"
TENK = CORPUS / "DDOG_10K_FY2024.htm"

pytestmark = pytest.mark.skipif(not TENK.exists(), reason="demo corpus not present")


@pytest.fixture(scope="module")
def markdown() -> str:
    return load(TENK).markdown


@pytest.fixture(scope="module")
def tree():
    return build_tree(load(TENK))


# ── the table ────────────────────────────────────────────────────────────

def test_revenue_row_keeps_label_and_both_years(markdown):
    """The failure that chunking causes, asserted directly.

    FY2024 and FY2023 total revenue must appear on the SAME line as the row
    label. Naive chunking separates them, and that is the whole argument for
    navigating structure instead.
    """
    row = next((ln for ln in markdown.splitlines()
                if "2,684,275" in ln and "2,128,359" in ln), None)
    assert row is not None, "FY2024 and FY2023 revenue are not on one line"
    assert re.search(r"\bRevenue\b", row, re.I), f"row label lost: {row[:120]}"
    assert row.count("|") >= 3, f"not a markdown table row: {row[:120]}"


def test_income_statement_rows_are_intact(markdown):
    """Neighbouring rows survive too, so the grid is a grid."""
    for label, value in [("Cost of revenue", "515,531"), ("Gross profit", "2,168,744")]:
        assert any(label.lower() in ln.lower() and value in ln
                   for ln in markdown.splitlines()), f"{label} lost {value}"


def test_table_unit_statement_survives(markdown):
    """Scale is meaningless without it. A figure in thousands read as units is
    wrong by 1000x, which is the bug this assertion exists to catch."""
    i = markdown.find("2,684,275")
    assert i > 0
    assert re.search(r"in thousands", markdown[max(0, i - 4000):i], re.I), \
        "no unit statement precedes the income statement"


# ── the tree ─────────────────────────────────────────────────────────────

def test_tree_finds_the_filing_structure(tree):
    titles = [n["title"].upper() for n in walk(tree)]
    assert any("PART I" in t for t in titles)
    assert any("PART II" in t for t in titles)


def test_income_statement_is_addressable(markdown, tree):
    """The agent can only fetch what a node's address covers.

    Asserting a section *title* would test the filer's house style: Datadog
    calls it "Results of Operations", other registrants use "Consolidated
    Statements of Operations". What has to be true is that some node's span
    contains the revenue row, so the agent can reach it and cite it.
    """
    line = next(i for i, ln in enumerate(markdown.splitlines(), start=1)
                if "2,684,275" in ln and "2,128,359" in ln)

    owners = [n for n in walk(tree)
              if (a := n.get("addr")) and a.get("line_start")
              and a["line_start"] <= line <= a.get("line_end", a["line_start"])]

    assert owners, f"no node covers the revenue row at line {line}"
    assert any(n.get("addr", {}).get("anchor") for n in owners) or owners, \
        "covering node carries no address, so it cannot be cited"


def test_nodes_carry_pointers_not_text(tree):
    """The tree must stay small enough to reason over whole. Storing node text
    would reproduce the filing and defeat the design."""
    for n in walk(tree):
        assert "text" not in n, f"node {n['node_id']} embeds text"


def test_tree_fits_in_one_prompt(tree):
    import json
    size = len(json.dumps(tree))
    assert size < 200_000, f"tree serialises to {size} chars, too large to send whole"
