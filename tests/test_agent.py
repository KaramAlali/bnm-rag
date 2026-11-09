"""Step 5 agent, offline: how chunks are shown to the model, the tools over an in-memory
backend, and the reply checks. The live agent is opt-in (`uv run pytest -m llm`)."""

import datetime as dt

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from bnm_rag.agent.catalog import document_status, documents, out_of_corpus
from bnm_rag.agent.reply import Reply, citation, cited_ids, problems
from bnm_rag.agent.run import retrieved_chunks
from bnm_rag.agent.tools import Backend, _para_key, make_tools, render, status_line

TODAY = dt.date(2026, 11, 7)


def chunk(cid, kind="policy_document", **kw):
    doc_id, para_no = cid.split(":", 1)
    base = {
        "chunk_id": cid, "doc_id": doc_id, "para_no": para_no, "kind": kind,
        "obligation": "S", "title": f"Title of {doc_id}", "reference": None,
        "section": None, "heading_path": [], "text": f"Text of {cid}.", "footnotes": [],
        "page_start": 4, "page_end": 4, "source_url": f"https://bnm.example/{doc_id}.pdf",
        "effective_from": "2025-01-31", "effective_until": None, "effective_exceptions": [],
        "effective_note": None, "applies_to": ["standard_emi"], "applies_note": None,
        "faq_links": [], "refers_to": [], "figure": False,
    }
    return base | kw


CHUNKS = {c["chunk_id"]: c for c in [
    chunk("emoney_pd:20.8", faq_links=["emoney_faq:Q6"]),
    chunk("emoney_faq:Q6", kind="faq", obligation="none", effective_from=None),
    chunk("open-finance_ed:4.1", kind="exposure_draft", effective_from="2027-01-01"),
    chunk("techreq-psr_pd:2.10", section="2 Applicability", effective_from="2027-03-12"),
    chunk("techreq-psr_pd:2.4", section="2 Applicability", effective_from="2027-03-12"),
]}


class FakeBackend:
    def __init__(self):
        self.filters = []

    def search(self, query, top, filter):
        self.filters.append(filter)
        return [c for c in CHUNKS.values()
                if not (filter and "exposure_draft" in filter and c["kind"] == "exposure_draft")]

    def get_chunk(self, cid):
        return CHUNKS.get(cid)

    def chunks_where(self, filter):
        self.filters.append(filter)
        return [c for c in CHUNKS.values() if c["doc_id"] == "techreq-psr_pd"]


@pytest.fixture
def tools_and_backend():
    fake = FakeBackend()
    backend = Backend(search=fake.search, get_chunk=fake.get_chunk,
                      chunks_where=fake.chunks_where)
    return {t.name: t for t in make_tools(TODAY, backend)}, fake


def call(t, **args):
    """Invoke a content_and_artifact tool the way the agent does; returns (text, artifact)."""
    msg = t.invoke({"type": "tool_call", "id": "1", "name": t.name, "args": args})
    return msg.content, msg.artifact


# --- what the model sees -------------------------------------------------------------------


def test_status_lines():
    assert status_line(CHUNKS["emoney_pd:20.8"], TODAY).startswith("in force on 2026-11-07")
    assert status_line(CHUNKS["techreq-psr_pd:2.4"], TODAY).startswith("not yet in force")
    assert status_line(CHUNKS["open-finance_ed:4.1"], TODAY).startswith("PROPOSED")
    assert "not a rule itself" in status_line(CHUNKS["emoney_faq:Q6"], TODAY)
    later = chunk("rmit_pd:10.31", effective_from="2025-11-28", effective_exceptions=[
        {"from": "2027-09-30", "until": None, "items": "(a), (c)", "who": None}])
    assert "(a), (c) only from 2027-09-30" in status_line(later, TODAY)
    gone = chunk("emoney_pd:27.1", effective_until="2027-03-12")
    assert "superseded on 2027-03-12" in status_line(gone, TODAY)


def test_render_heads_with_the_chunk_id_and_truncates_search_results():
    long = chunk("rmit_pd:5.2", text="x" * 5000)
    shown = render(long, TODAY)
    assert shown.startswith("[rmit_pd:5.2] ")
    assert "get_paragraph for the full text" in shown
    assert "x" * 5000 in render(long, TODAY, full=True)


def test_paragraph_order_is_numeric():
    paras = ["2.10", "2.4", "Appendix 1 / 2", "2.9"]
    assert sorted(paras, key=_para_key) == ["2.4", "2.9", "2.10", "Appendix 1 / 2"]


# --- tools -----------------------------------------------------------------------------------


def test_search_leaves_drafts_out_unless_asked(tools_and_backend):
    tools, fake = tools_and_backend
    _, shown = call(tools["search_regulations"], query="open finance")
    assert "open-finance_ed:4.1" not in {c["chunk_id"] for c in shown}
    assert fake.filters[-1] == "kind ne 'exposure_draft'"
    _, shown = call(tools["search_regulations"], query="open finance", include_drafts=True,
                    doc_ids=["open-finance_ed"])
    assert "open-finance_ed:4.1" in {c["chunk_id"] for c in shown}
    assert fake.filters[-1] == "search.in(doc_id, 'open-finance_ed', ',')"


def test_unknown_doc_ids_never_reach_a_filter(tools_and_backend):
    tools, fake = tools_and_backend
    text, shown = call(tools["search_regulations"], query="x", doc_ids=["x' or 1 eq 1"])
    assert "unknown doc_id" in text and shown == [] and fake.filters == []
    text, shown = call(tools["get_document_frame"], doc_id="nope")
    assert "unknown doc_id" in text and shown == []


def test_get_paragraph_brings_its_faq_answers(tools_and_backend):
    tools, _ = tools_and_backend
    text, shown = call(tools["get_paragraph"], doc_id="emoney_pd", para_no="20.8")
    assert [c["chunk_id"] for c in shown] == ["emoney_pd:20.8", "emoney_faq:Q6"]
    assert "Linked FAQ answer" in text
    text, shown = call(tools["get_paragraph"], doc_id="emoney_pd", para_no="99")
    assert shown == []


def test_document_frame_is_in_paragraph_order(tools_and_backend):
    tools, fake = tools_and_backend
    _, shown = call(tools["get_document_frame"], doc_id="techreq-psr_pd")
    assert [c["para_no"] for c in shown] == ["2.4", "2.10"]
    assert "frame_kind" in fake.filters[-1]


def test_list_documents_has_the_corpus_and_the_out_of_corpus_list(tools_and_backend):
    tools, _ = tools_and_backend
    text = tools["list_documents"].invoke({})
    assert len(documents()) == 20
    assert all(f"- {d}:" in text for d in documents())
    assert out_of_corpus()[0]["title"] in text


def test_document_status():
    docs = documents()
    assert document_status(docs["techreq-psr_pd"], TODAY) == "not yet in force"
    assert document_status(docs["rmit_pd"], TODAY) == "in force"
    assert document_status(docs["open-finance_ed"], TODAY) == "proposed"
    assert "not a rule" in document_status(docs["rmit_faq"], TODAY)


# --- reply checks ------------------------------------------------------------------------------


def reply(answer="Limit [emoney_pd:20.8].", citations=("emoney_pd:20.8",), coverage="answered"):
    return Reply(answer=answer, citations=list(citations), coverage=coverage)


def test_a_reply_citing_what_was_retrieved_passes():
    assert problems(reply(), CHUNKS) == []


def test_citations_must_come_from_tool_results():
    issues = problems(reply(citations=["emoney_pd:99.9"]), CHUNKS)
    assert len(issues) == 1 and "emoney_pd:99.9" in issues[0]
    issues = problems(reply(answer="See [rmit_pd:1.1].", citations=[]), CHUNKS)
    assert "rmit_pd:1.1" in issues[0]


def test_inline_citations_join_the_list():
    r = reply(answer="A [emoney_pd:20.8] and B [emoney_faq:Q6].", citations=["emoney_pd:20.8"])
    assert cited_ids(r) == ["emoney_pd:20.8", "emoney_faq:Q6"]


def test_footnote_and_sub_item_suffixes_resolve_to_the_paragraph():
    r = reply(answer="Tier [emoney_pd:20.8, footnote 4] and [emoney_pd:20.8(b)].",
              citations=["emoney_pd:20.8; emoney_faq:Q6"])
    assert cited_ids(r, CHUNKS) == ["emoney_pd:20.8", "emoney_faq:Q6"]
    assert problems(r, CHUNKS) == []
    assert problems(reply(citations=["emoney_pd:20.9(b)"]), CHUNKS)  # 20.9 never retrieved


def test_answers_must_cite_something():
    assert problems(reply(answer="Yes.", citations=[]), CHUNKS)
    assert problems(reply(answer="Not covered.", citations=[], coverage="not_covered"),
                    CHUNKS) == []


def test_a_draft_is_never_presented_as_a_rule():
    cite = ["open-finance_ed:4.1"]
    assert problems(reply(answer="EMIs must share data [open-finance_ed:4.1].",
                          citations=cite), CHUNKS)
    assert problems(reply(answer="The draft proposes that EMIs share data "
                                 "[open-finance_ed:4.1].", citations=cite), CHUNKS) == []


def test_citation_fields_come_from_the_chunk():
    c = citation(CHUNKS["techreq-psr_pd:2.4"], TODAY)
    assert c["status"] == "not yet in force"
    assert c["url"] == "https://bnm.example/techreq-psr_pd.pdf#page=4"


def test_retrieved_chunks_come_from_tool_artifacts():
    msgs = [AIMessage(""), ToolMessage("t", tool_call_id="1",
                                       artifact=[CHUNKS["emoney_pd:20.8"]]),
            ToolMessage("list", tool_call_id="2")]
    assert set(retrieved_chunks(msgs)) == {"emoney_pd:20.8"}


# --- opt-in: the live agent (uv run pytest -m llm) ---------------------------------------------


@pytest.mark.llm
@pytest.mark.azure
def test_live_agent_answers_a_draft_question_as_proposed():
    from bnm_rag.agent.run import ask

    ans = ask("Does our e-wallet have to share customer data under BNM's open finance rules?",
              today=TODAY)
    assert ans.unresolved == []
    assert "propos" in ans.answer.lower()
    assert any(c["doc_id"] == "open-finance_ed" for c in ans.citations)
