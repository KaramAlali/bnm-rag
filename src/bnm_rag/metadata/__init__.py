"""Step 2: metadata added to the parser's chunks (effective dates, who a paragraph applies to,
FAQ links, version) and the related/out-of-corpus document list. Run as part of
`uv run python -m bnm_rag.parse`, so chunks.jsonl and chunks.json always carry it.
"""

from __future__ import annotations

from bnm_rag.metadata.applicability import assign_roles
from bnm_rag.metadata.dates import assign_dates, iso_date
from bnm_rag.metadata.links import link_faqs
from bnm_rag.metadata.related import related_documents


def enrich(chunks: list[dict], sources: list[dict]) -> dict:
    """Adds the metadata fields to every chunk, in place; returns the related-documents list.
    Raises if an FAQ cites a paragraph that does not exist."""
    by_doc = {src["file"].removesuffix(".pdf"): src for src in sources}
    for c in chunks:
        issued = by_doc[c["doc_id"]]["issued"].split()[0]
        c["issued"] = issued
        c["version"] = f"{c['reference'] or c['doc_id']}@{issued}#{c['file_sha256']}"
    assign_dates(chunks, {d: iso_date(src["issued"]) for d, src in by_doc.items()})
    assign_roles(chunks)
    unresolved = link_faqs(chunks)
    if unresolved:
        raise ValueError(f"FAQ references to missing paragraphs: {unresolved}")
    return related_documents(chunks)
