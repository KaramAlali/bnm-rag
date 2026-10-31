"""Parser rules that need no PDFs (these run in CI)."""

import pytest

from bnm_rag.parse.chunk import APPENDIX, NUM_PARA, SG_PARA, SUBITEM, follows, number, short
from bnm_rag.parse.document import figures, sources
from bnm_rag.parse.layout import Span, clean, join_text, render


@pytest.mark.parametrize(
    ("new", "last"),
    [
        ("8.2", "8.1"),
        ("9.1", "8.6"),  # next section
        ("8.5", "8.2"),  # small gap
        ("13.2.1", "13.2"),  # one level deeper
        ("13.3", "13.2.4"),  # back up a level
        ("14.1", "13.2.4"),
    ],
)
def test_follows_accepts_next_numbers(new, last):
    assert follows(number(new), number(last))


@pytest.mark.parametrize(
    ("new", "last"),
    [
        ("2.4", "8.1"),  # a cross-reference that went backwards
        ("8.1", "8.1"),
        ("8.9", "8.2"),  # too far ahead
        ("9.5", "8.6"),  # new section must start low
    ],
)
def test_follows_rejects_unlikely_numbers(new, last):
    assert not follows(number(new), number(last))


def test_paragraph_patterns():
    m = SG_PARA.match("S 8.1 The board must establish")
    assert (m["sg"], m["num"], m["rest"]) == ("S", "8.1", "The board must establish")
    assert SG_PARA.match("G 16.7")["num"] == "16.7"
    assert NUM_PARA.match("13.2.1 The NCII entity shall")["num"] == "13.2.1"
    assert NUM_PARA.match("10.37, 10.54(d) and") is None


def test_appendix_heading_pattern():
    m = APPENDIX.match("Appendix 2: False Acceptance Rate and sampling")
    assert (m["n"], m["title"]) == ("2", "False Acceptance Rate and sampling")
    assert APPENDIX.match("APPENDIX IV")["n"] == "IV"
    assert APPENDIX.match("Appendix 10.2 of") is None


def test_subitem_pattern():
    assert SUBITEM.match("(a) approve the corresponding")
    assert SUBITEM.match("(iii) number and value")
    assert not SUBITEM.match("(the Bank) shall")


def test_join_text_keeps_hyphenated_words_whole():
    assert join_text(["day-to-", "day management"]) == "day-to-day management"
    assert join_text(["the e-", "KYC solution"]) == "the e-KYC solution"
    assert join_text(["the board must", "approve"]) == "the board must approve"
    assert join_text(["as follows -", "the board"]) == "as follows - the board"


def span(x0, text, size=12.0, sup=False):
    return Span(x0, 0, x0 + 6 * len(text), 12, text, size, False, sup)


def test_render_strips_footnote_markers():
    notes: list[int] = []
    spans = [
        span(100, "annual transaction value"),
        span(250, "3,4", 8.0, sup=True),
        span(262, " of more"),
    ]
    assert render(spans, 12.0, notes) == "annual transaction value of more"
    assert notes == [3, 4]


def test_render_keeps_ordinal_suffixes():
    notes: list[int] = []
    spans = [span(100, "from 1"), span(136, "st", 8.0, sup=True), span(149, " to 31")]
    assert render(spans, 12.0, notes) == "from 1st to 31"
    assert notes == []


def test_clean_turns_an_unmapped_glyph_into_a_bullet_or_apostrophe():
    assert clean("� verify the customer�s identity") == "• verify the customer's identity"


def test_short_cuts_long_headings_at_a_word():
    assert short("Contact representative:") == "Contact representative"
    cut = short("Part D: Minimum controls to be assessed by the independent External Service")
    assert cut == "Part D: Minimum controls to be assessed by the independent"


def test_curated_figures_are_well_formed():
    """corpus/curated/figures.yaml: every entry points at a real document and page range."""
    docs = {s["file"].removesuffix(".pdf"): s for s in sources()}
    entries = [fig for doc_id in docs for fig in figures(doc_id)]
    assert len(entries) == 8
    for fig in entries:
        assert fig["text"].strip() and fig["para_no"], fig
        assert isinstance(fig["page"], int) and fig["page"] >= 1, fig
        assert len(fig.get("region", [0, 0, 0, 0])) == 4, fig
