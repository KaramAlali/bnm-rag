"""Fixture tests on the real PDFs. Skipped when corpus/raw/ is empty (e.g. in CI)."""

import json
import re
from collections import Counter

import pytest

from bnm_rag.parse.document import CORPUS, parse_document, sources

SOURCES = {s["file"].removesuffix(".pdf"): s for s in sources()}
pytestmark = pytest.mark.skipif(
    not all((CORPUS / "raw" / s["file"]).exists() for s in SOURCES.values()),
    reason="corpus PDFs not downloaded (scripts/download_corpus.ps1)",
)

# S/G paragraph counts, checked by hand. corpus/measurements.json says 881/229: its regex
# missed MCIPD 8.1-8.4 (seven spaces after "S") and Merchant Acquiring 14.6 (three "S"
# glyphs stacked in the PDF), so the true totals are 886/229.
OBLIGATIONS = {
    "techreq-psr_pd": (102, 13),
    "rmit_pd": (111, 10),
    "emoney_pd": (232, 69),
    "ekyc_pd": (33, 11),
    "pso_pd": (69, 23),
    "merchant-acq_pd": (120, 72),
    "iftf_pd": (32, 5),
    "mcipd_pd": (98, 17),
    "complaints_pd": (35, 4),
    "open-finance_ed": (54, 5),
    "sandbox_pd": (0, 0),
}


@pytest.fixture(scope="session")
def corpus() -> dict[str, dict[str, dict]]:
    """doc_id → chunk_id → chunk, for the whole corpus (parsed once, ~30 s)."""
    out = {}
    for doc_id, src in SOURCES.items():
        chunks, _ = parse_document(src)
        out[doc_id] = {c["chunk_id"]: c for c in chunks}
    return out


def chunk(corpus, chunk_id: str) -> dict:
    return corpus[chunk_id.split(":")[0]][chunk_id]


def test_rmit_8_1_keeps_sub_items_with_their_paragraph(corpus):
    c = chunk(corpus, "rmit_pd:8.1")
    assert c["obligation"] == "S"
    assert c["page_start"] == c["page_end"] == 8
    assert c["heading_path"] == [
        "PART B POLICY REQUIREMENTS",
        "8 Governance",
        "Responsibilities of the Board of Directors",
    ]
    lines = c["text"].split("\n")
    assert lines[0].startswith("The board must establish and approve the technology risk appetite")
    assert [ln[:3] for ln in lines[1:]] == ["(a)", "(b)", "(c)", "(d)", "(e)"]
    assert "rmit_pd:8.2" in corpus["rmit_pd"]


def test_rmit_footnote_is_moved_out_of_the_body(corpus):
    c = chunk(corpus, "rmit_pd:8.3")
    assert "board-level committee which shall be responsible" in c["text"]
    assert [f["n"] for f in c["footnotes"]] == [9]
    assert c["footnotes"][0]["text"].startswith("The board of a financial institution may either")
    assert "Board Risk Committee" not in c["text"]


def test_tech_requirements_tier_table_and_glued_footnotes(corpus):
    """The "value3,4" case: markers stripped, both footnotes attached, table read by row."""
    c = chunk(corpus, "techreq-psr_pd:2.4")
    assert c["obligation"] == "none"  # Part A has no S/G
    assert "value3" not in c["text"]
    rows = c["text"].split("\n")
    assert rows[1] == "Tiers | Criteria | Regulations Applied"
    assert rows[3].startswith("Tier-2 | PSRs with annual transaction value of more than RM1.5")
    assert rows[3].endswith("| TR PD")
    notes = {f["n"]: f["text"] for f in c["footnotes"]}
    assert set(notes) == {3, 4, 5}
    assert notes[4].startswith("The criteria shall be determined every January")


def test_ekyc_appendix_2_table_1_across_two_pages(corpus):
    c = chunk(corpus, "ekyc_pd:Appendix 2 / 10")
    assert c["appendix"] == "Appendix 2"
    assert c["heading_path"] == ["Appendix 2: False Acceptance Rate and sampling"]
    assert (c["page_start"], c["page_end"]) == (19, 20)
    assert "Table 1: FAR thresholds and actions to be taken" in c["text"]
    assert "\nLevel 1 (0% – 3%) | A financial institution shall continuously monitor" in c["text"]
    assert "\nLevel 3 (> 5%) |" in c["text"]


def test_stacked_s_markers(corpus):
    c = chunk(corpus, "merchant-acq_pd:14.6")
    assert c["obligation"] == "S"
    assert c["text"].startswith("Acquirers shall ensure that the outsourcing arrangement")
    assert "S S" not in chunk(corpus, "merchant-acq_pd:14.5")["text"]


@pytest.mark.parametrize("doc_id", sorted(OBLIGATIONS))
def test_obligation_counts(corpus, doc_id):
    counts = Counter(c["obligation"] for c in corpus[doc_id].values())
    assert (counts["S"], counts["G"]) == OBLIGATIONS[doc_id]


def test_faq_questions_and_paragraph_links(corpus):
    c = chunk(corpus, "rmit_faq:Q4")
    assert c["text"].startswith("Q: How should a non-bank registered merchant acquirer")
    assert "\nA: Aggregate transaction value" in c["text"]
    assert c["para_refs"] == ["5.2"]
    assert len([k for k in corpus["rmit_faq"] if re.fullmatch(r"rmit_faq:Q\d+", k)]) == 67
    part_b = chunk(corpus, "emoney_faq:Part B / Q1")  # Part B restarts at 1
    assert part_b["text"].startswith("Q: What is Limited Purpose EMI")


def test_table_documents_are_split_by_row(corpus):
    para_nos = [k.split(":")[1] for k in corpus["ekyc_faq"]]
    assert para_nos == ["intro", *[f"Q{i}" for i in range(1, 17)], "closing", "Appendix I"]
    c = chunk(corpus, "ekyc_faq:Q1")
    assert c["text"].startswith("Q: Would procuring e-KYC services from a 3rd party")
    assert c["footnotes"][0]["text"].startswith("For the avoidance of doubt")
    row = chunk(corpus, "complaints_fs:1")["text"]  # a page rotated 90°
    assert row.startswith("Area: Effective date of the CH PD\nFeedback received: ")
    assert "1 April 2026" in row


def test_exposure_draft_keeps_its_kind(corpus):
    assert {c["kind"] for c in corpus["open-finance_ed"].values()} == {"exposure_draft"}


def test_every_chunk_is_well_formed(corpus):
    for doc in corpus.values():
        for c in doc.values():
            assert c["text"].strip(), c["chunk_id"]
            assert 1 <= c["page_start"] <= c["page_end"], c["chunk_id"]
            assert "#" not in c["chunk_id"], "para_no should be unique within a document"
            if not c["para_no"].startswith("intro"):
                assert "Issued on" not in c["text"], c["chunk_id"]  # running footer
                assert not re.search(r"\b\d+ of \d+\s*$", c["text"]), c["chunk_id"]


def test_appendix_keeps_section_and_numbered_sub_heading(corpus):
    c = chunk(corpus, "rmit_pd:Appendix 12 / 5.1.1")
    assert c["heading_path"][1:] == [
        "5 Cyber Security Policy and Objectives",
        "5.1 Cyber Security Policy",
    ]


def test_stacked_and_wrapped_headings(corpus):
    ekyc = chunk(corpus, "ekyc_pd:8.4")["heading_path"]
    assert ekyc[-2:] == ["Identification and verification (IDV) of customers through e-KYC",
                         "A. General requirements"]
    section = chunk(corpus, "rmit_pd:17.1")["section"]
    assert section.endswith("related to Cloud Services and Emerging Technology")
    wrapped = chunk(corpus, "rmit_pd:Appendix 6")["heading_path"][-1]
    assert wrapped.endswith("participation with regulated entities")


def test_mcipd_disclosure_table_is_one_chunk_per_item(corpus):
    """The 8-item table printed inside 13.2 runs over pages 21-31 with no grid on most pages."""
    doc = corpus["mcipd_pd"]
    items = [k for k in doc if k.startswith("mcipd_pd:13.2 / item ")]
    assert items == [f"mcipd_pd:13.2 / item {n}" for n in range(1, 9)]
    assert len(chunk(corpus, "mcipd_pd:13.2")["text"]) < 300  # just the note above the table
    lines = chunk(corpus, "mcipd_pd:13.2 / item 1")["text"].split("\n")
    assert lines[0].startswith("Purpose: Compliance with an order or request made by an")
    assert lines[1].startswith("Disclosed to: An investigating officer authorised under")
    assert lines[2] == "Conditions: (a) The request must be specific in relation to-"
    assert lines[3].startswith("i. name and identification number of the customer")
    assert any(ln.startswith("• the digital order issued by PDRM") for ln in lines)
    item3 = chunk(corpus, "mcipd_pd:13.2 / item 3")["text"]
    assert item3.startswith("Purpose: Performance of functions of the financial institution which")
    assert chunk(corpus, "mcipd_pd:13.3")["obligation"] == "S"


def test_exposure_draft_preface(corpus):
    c = chunk(corpus, "open-finance_ed:preface")
    assert "proposed regulatory requirements for open finance" in c["text"]
    assert "1 March 2026" in c["text"]
    assert "annekang@" not in c["text"]  # officers' names and addresses are left out
    prefaces = [k for doc in corpus.values() for k in doc if k.endswith(":preface")]
    assert prefaces == ["open-finance_ed:preface"]


def test_figures_are_transcribed(corpus):
    green_lane = chunk(corpus, "sandbox_pd:Appendix IV")
    assert green_lane["figure"] and green_lane["page_start"] == 33
    assert "up to 20,000 unique customers per solution" in green_lane["text"]
    q1 = chunk(corpus, "sandbox_faq:Q1")
    assert "Fintech company | eligible | not eligible" in q1["text"]
    diagram = chunk(corpus, "open-finance_ed:1 / Diagram 1")
    assert "Single account view, including personal financial management" in diagram["text"]
    every = [c for doc in corpus.values() for c in doc.values()]
    assert sum(c["figure"] for c in every) == 8
    assert not any("access decisions" in " ".join(c["heading_path"]) for c in every)


def test_chunks_json_matches_chunks_jsonl():
    """`python -m bnm_rag.parse` writes both files from one run; they must stay identical."""
    jsonl, pretty = CORPUS / "chunks.jsonl", CORPUS / "chunks.json"
    if not (jsonl.exists() and pretty.exists()):
        pytest.skip("run `uv run python -m bnm_rag.parse` first")
    with open(jsonl, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    with open(pretty, encoding="utf-8") as f:
        assert json.load(f) == lines
