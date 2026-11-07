"""Shared fixtures. The corpus fixtures parse the real PDFs once per test run (~30 s) and are
only used by modules marked `needs_pdfs`, which skip when corpus/raw/ is empty (e.g. in CI)."""

import copy

import pytest

from bnm_rag.metadata import enrich
from bnm_rag.parse.document import CORPUS, parse_document, sources

SOURCES = {s["file"].removesuffix(".pdf"): s for s in sources()}
needs_pdfs = pytest.mark.skipif(
    not all((CORPUS / "raw" / s["file"]).exists() for s in SOURCES.values()),
    reason="corpus PDFs not downloaded (scripts/download_corpus.ps1)",
)


@pytest.fixture(scope="session")
def corpus() -> dict[str, dict[str, dict]]:
    """doc_id → chunk_id → chunk, as the parser makes them (before step 2 metadata)."""
    out = {}
    for doc_id, src in SOURCES.items():
        chunks, _ = parse_document(src)
        out[doc_id] = {c["chunk_id"]: c for c in chunks}
    return out


@pytest.fixture(scope="session")
def enriched(corpus) -> tuple[dict[str, dict], dict]:
    """(chunk_id → chunk with metadata, related_docs) — what `python -m bnm_rag.parse` writes."""
    chunks = copy.deepcopy([c for doc in corpus.values() for c in doc.values()])
    related = enrich(chunks, list(SOURCES.values()))
    return {c["chunk_id"]: c for c in chunks}, related
