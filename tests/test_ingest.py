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
TENK = CORPUS / "SNOW_10K_FY2024.htm"

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
                if "2,806,489" in ln and "2,065,659" in ln), None)
    assert row is not None, "FY2024 and FY2023 revenue are not on one line"
    assert re.search(r"\bRevenue\b", row, re.I), f"row label lost: {row[:120]}"
    assert row.count("|") >= 3, f"not a markdown table row: {row[:120]}"


def test_income_statement_rows_are_intact(markdown):
    """Neighbouring rows survive too, so the grid is a grid."""
    for label, value in [("Cost of revenue", "898,558"), ("Gross profit", "1,907,931")]:
        assert any(label.lower() in ln.lower() and value in ln
                   for ln in markdown.splitlines()), f"{label} lost {value}"


def test_table_unit_statement_survives(markdown):
    """Scale is meaningless without it. A figure in thousands read as units is
    wrong by 1000x, which is the bug this assertion exists to catch."""
    i = markdown.find("2,806,489")
    assert i > 0
    assert re.search(r"in thousands", markdown[max(0, i - 4000):i], re.I), \
        "no unit statement precedes the income statement"


# ── the tree ─────────────────────────────────────────────────────────────

def test_tree_finds_the_filing_structure(tree):
    titles = [n["title"].upper() for n in walk(tree)]
    assert any("PART I" in t for t in titles)
    assert any("PART II" in t for t in titles)


def test_statements_of_operations_is_a_node(tree):
    node = next((n for n in walk(tree)
                 if "STATEMENTS OF OPERATIONS" in n["title"].upper()), None)
    assert node is not None, "income statement is not addressable as a node"
    assert node.get("addr"), "node carries no address, so it cannot be cited"


def test_nodes_carry_pointers_not_text(tree):
    """The tree must stay small enough to reason over whole. Storing node text
    would reproduce the filing and defeat the design."""
    for n in walk(tree):
        assert "text" not in n, f"node {n['node_id']} embeds text"


def test_tree_fits_in_one_prompt(tree):
    import json
    size = len(json.dumps(tree))
    assert size < 200_000, f"tree serialises to {size} chars, too large to send whole"
