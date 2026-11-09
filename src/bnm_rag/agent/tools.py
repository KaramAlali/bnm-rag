"""The agent's tools. Each returns text for the model plus the chunks it showed as an artifact,
so the reply's citations can be checked against what this run actually retrieved.

The tools take a `Backend` (the Azure index by default; an in-memory one in tests) and the date
answers are judged on, because status is computed per paragraph at answer time.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.tools import BaseTool, tool

from bnm_rag.agent.catalog import document_status, documents, out_of_corpus
from bnm_rag.metadata.status import PROPOSED, later_parts, status

SNIPPET = 1500  # characters of text per search result; get_paragraph returns the full text
FRAME = ("applicability", "effective_date", "superseded")
OBLIGATION = {"S": "S (standard: must comply)", "G": "G (guidance: encouraged)"}


@dataclass
class Backend:
    search: Callable[..., list[dict]]        # (query, top=, filter=) → ranked chunks
    get_chunk: Callable[[str], dict | None]  # chunk_id → chunk
    chunks_where: Callable[[str], list[dict]]  # OData filter → chunks


def azure_backend() -> Backend:
    from bnm_rag.index import azure

    return Backend(search=lambda q, top, filter: azure.search(q, "hybrid", top, filter),
                   get_chunk=azure.get_chunk, chunks_where=azure.chunks_where)


def status_line(chunk: dict, today: dt.date) -> str:
    s = status(chunk, today)
    if s is None:
        return f"{chunk['kind'].replace('_', ' ')}: explains rules, not a rule itself"
    if s == PROPOSED:
        return ("PROPOSED: exposure draft, not a rule (its dates are proposals: "
                f"{chunk.get('effective_from') or 'none stated'})")
    line = f"{s} on {today}"
    if chunk.get("effective_from"):
        line += f" (effective from {chunk['effective_from']}"
        line += f", superseded on {chunk['effective_until']})" if chunk.get(
            "effective_until") else ")"
    for e in later_parts(chunk, today):
        what = e.get("items") or "some parts"
        who = f" for {e['who']}" if e.get("who") else ""
        if e.get("from"):
            line += f"; {what}{who} only from {e['from']}"
        if e.get("until"):
            line += f"; {what}{who} superseded on {e['until']}"
    if chunk.get("effective_note"):
        line += f". Note: {chunk['effective_note']}"
    return line


def render(chunk: dict, today: dt.date, full: bool = False) -> str:
    """One chunk as the model sees it, headed by the chunk_id it must cite."""
    where = f"page {chunk['page_start']}" + (
        f"-{chunk['page_end']}" if chunk.get("page_end") not in (None, chunk["page_start"])
        else "")
    head = f"[{chunk['chunk_id']}] {chunk['title']}"
    if chunk.get("reference"):
        head += f" ({chunk['reference']})"
    if chunk.get("issued"):
        head += f", issued {chunk['issued']}"
    lines = [head, f"Paragraph {chunk['para_no']}, {where}"]
    if chunk.get("obligation") in OBLIGATION:
        lines.append(f"Obligation: {OBLIGATION[chunk['obligation']]}")
    lines.append(f"Status: {status_line(chunk, today)}")
    if chunk.get("applies_to"):
        lines.append("Applies to: " + ", ".join(chunk["applies_to"]))
    if chunk.get("applies_note"):
        lines.append(f"Applicability note: {chunk['applies_note']}")
    if chunk.get("faq_links"):
        lines.append("FAQ answers on this paragraph: " + ", ".join(chunk["faq_links"]))
    if chunk.get("refers_to"):
        lines.append("This FAQ answer refers to: " + ", ".join(chunk["refers_to"]))
    text = chunk["text"]
    if not full and len(text) > SNIPPET:
        text = text[:SNIPPET] + " [...] (truncated: get_paragraph for the full text)"
    lines.append(text)
    lines += [f"Footnote {f['n']}: {f['text']}" for f in chunk.get("footnotes") or []]
    return "\n".join(lines)


def _doc_filter(doc_ids: list[str] | None) -> list[str]:
    """Only known doc ids reach an OData filter (the model chooses them)."""
    known = documents()
    bad = [d for d in doc_ids or [] if d not in known]
    if bad:
        raise ValueError(f"unknown doc_id {bad}; call list_documents for the valid ones")
    return list(doc_ids or [])


def make_tools(today: dt.date, backend: Backend | None = None) -> list[BaseTool]:
    backend = backend or azure_backend()

    @tool(response_format="content_and_artifact")
    def search_regulations(query: str, doc_ids: list[str] | None = None,
                           include_drafts: bool = False, top: int = 8
                           ) -> tuple[str, list[dict]]:
        """Hybrid (keyword + meaning) search over the paragraphs of BNM's payments and e-money
        documents. Write the query in the documents' own terms (e.g. "Technology Requirements
        tier thresholds" rather than the user's situation). Search several times with different
        wordings for different parts of a question. Optionally restrict to some doc_ids.
        Exposure drafts (proposals) are left out unless include_drafts is true."""
        try:
            ids = _doc_filter(doc_ids)
        except ValueError as e:
            return str(e), []
        clauses = [] if include_drafts else ["kind ne 'exposure_draft'"]
        if ids:
            clauses.append(f"search.in(doc_id, '{','.join(ids)}', ',')")
        hits = backend.search(query, top=max(1, min(top, 15)),
                              filter=" and ".join(clauses) or None)
        if not hits:
            return "No paragraphs found. Try other wording, or include_drafts=true.", []
        return "\n\n---\n\n".join(render(c, today) for c in hits), hits

    @tool(response_format="content_and_artifact")
    def get_paragraph(doc_id: str, para_no: str) -> tuple[str, list[dict]]:
        """The full text of one paragraph (e.g. doc_id "rmit_pd", para_no "10.31", or
        "Appendix 5 / 3.2", or "Q4" in an FAQ), with its footnotes and the FAQ answers linked
        to it. Use it for long paragraphs cut off in search results, for definitions
        (Interpretation, usually para_no "5.2"), and for paragraphs other paragraphs refer to."""
        chunk = backend.get_chunk(f"{doc_id}:{para_no}")
        if chunk is None:
            return f"No paragraph {doc_id}:{para_no}.", []
        shown = [chunk]
        parts = [render(chunk, today, full=True)]
        for fid in chunk.get("faq_links") or []:
            faq = backend.get_chunk(fid)
            if faq:
                shown.append(faq)
                parts.append("Linked FAQ answer:\n" + render(faq, today, full=True))
        return "\n\n---\n\n".join(parts), shown

    @tool(response_format="content_and_artifact")
    def get_document_frame(doc_id: str) -> tuple[str, list[dict]]:
        """A policy document's frame: its Applicability (who it binds), Effective date and
        Superseded paragraphs. Call it for every policy document an answer relies on, since
        search rarely finds these paragraphs and answers must say who a rule applies to and
        from when."""
        try:
            _doc_filter([doc_id])
        except ValueError as e:
            return str(e), []
        kinds = ",".join(FRAME)
        chunks = backend.chunks_where(
            f"doc_id eq '{doc_id}' and search.in(frame_kind, '{kinds}', ',')")
        if not chunks:
            return f"{doc_id} has no Applicability / Effective date / Superseded paragraphs.", []
        chunks.sort(key=lambda c: (c["page_start"], _para_key(c["para_no"])))
        return "\n\n---\n\n".join(render(c, today, full=True) for c in chunks), chunks

    @tool
    def list_documents() -> str:
        """The indexed documents (doc_id, title, kind, reference, dates, status today) and the
        documents they cite that are NOT indexed. Use it to pick doc_ids, and to name the
        right document when a question is not covered."""
        lines = [f"Indexed documents (status on {today}):"]
        for d in documents().values():
            ref = f", {d['reference']}" if d["reference"] else ""
            eff = f", effective {d['effective']}" if d["effective"] else ""
            lines.append(f"- {d['doc_id']}: {d['title']} [{d['kind']}{ref}; issued "
                         f"{d['issued']}{eff}; {document_status(d, today)}]")
        lines.append("\nCited by these documents but NOT indexed (not covered here):")
        lines += [f"- {o['title']}" for o in out_of_corpus()]
        return "\n".join(lines)

    return [search_regulations, get_paragraph, get_document_frame, list_documents]


def _para_key(para_no: str) -> list[tuple[int, int | str]]:
    """'2.10' after '2.9'; numbers before words, so mixed parts never compare int to str."""
    parts = para_no.replace("/", ".").split(".")
    return [(0, int(p)) if p.strip().isdigit() else (1, p.strip()) for p in parts]
