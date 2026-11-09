"""Step 4 index: chunk ↔ search document, the index definition, the recall arithmetic (all
offline), and opt-in checks against the live Azure index (`uv run pytest -m azure`)."""

import re

import pytest
from conftest import needs_pdfs

from bnm_rag.index.documents import (
    OWN_FIELDS,
    chunk_from_document,
    doc_key,
    embedding_text,
    search_document,
)
from bnm_rag.index.evaluate import by_role, load_golden, ranks, role, scores, summarize
from bnm_rag.index.schema import DIMENSIONS, index_definition

CHUNK = {
    "chunk_id": "rmit_pd:Appendix 5 / 3.2", "doc_id": "rmit_pd", "para_no": "Appendix 5 / 3.2",
    "obligation": "S", "part": "APPENDICES", "section": None, "appendix": "Appendix 5",
    "heading_path": ["APPENDICES", "Appendix 5 Control measures"],
    "text": "A financial institution must ensure ...", "page_start": 70, "page_end": 71,
    "footnotes": [{"n": 31, "text": "Including cloud services."}], "para_refs": [],
    "figure": False, "kind": "policy_document",
    "title": "Risk Management in Technology (RMiT)", "reference": "BNM/RH/PD 028-98",
    "source_url": "https://www.bnm.gov.my/x.pdf", "file_sha256": "abc", "issued": "2023-06-01",
    "version": "BNM/RH/PD 028-98@2023-06-01#abc", "effective_from": "pending: NACSA",
    "effective_until": None, "effective_exceptions": [{"from": "2027-10-15", "items": ["(e)"]}],
    "effective_note": None, "parent_doc": None, "applies_to": ["bank", "eligible_emi"],
    "applies_note": None, "refers_to": [], "faq_links": ["rmit_faq:Q3"],
}
KEY_CHARS = re.compile(r"^[A-Za-z0-9_\-=]+$")


def test_key_is_valid_and_unique_per_chunk_id():
    assert KEY_CHARS.match(doc_key(CHUNK["chunk_id"]))
    assert doc_key("a:1") != doc_key("a:1.0")


def test_embedding_text_carries_title_place_label_and_footnotes():
    text = embedding_text(CHUNK)
    assert text.splitlines()[:3] == [
        "Risk Management in Technology (RMiT) (BNM/RH/PD 028-98)",
        "APPENDICES > Appendix 5 Control measures",
        "Appendix 5 / 3.2 [S]",
    ]
    assert "Footnote 31: Including cloud services." in text


def test_round_trip_keeps_every_field():
    doc = search_document(CHUNK, [0.0] * DIMENSIONS)
    assert chunk_from_document(doc) == CHUNK
    assert "status" not in doc  # computed at answer time, never stored


def test_document_fields_match_the_index_definition():
    doc = search_document(CHUNK, [0.0] * DIMENSIONS)
    fields = {f.name: f for f in index_definition("t").fields}
    assert set(doc) == set(fields)
    assert [f.name for f in fields.values() if f.key] == ["id"]
    assert fields["vector"].vector_search_dimensions == DIMENSIONS
    assert fields["vector"].stored is False
    assert {n for n, f in fields.items() if f.searchable} == {"content", "vector"}


def test_compression_is_opt_in():
    assert index_definition("t").vector_search.compressions is None
    profile = index_definition("t", compress=True).vector_search.profiles[0]
    assert profile.compression_name == "int8"


def test_recall_arithmetic():
    found = ranks(["a", "b", "c"], ["x", "a", "y", "y", "y", "y", "c"])
    assert found == {"a": 2, "b": None, "c": 7}
    assert scores(found, 5) == (1 / 3, False, True)
    assert scores(found, 10) == (2 / 3, False, True)
    s = summarize([found, {"a": 1}])
    assert s[5] == ((1 / 3 + 1) / 2, 0.5, 1.0)


def test_frame_paragraphs_are_told_apart():
    assert role({"section": "2 Applicability"}) == "frame"
    assert role({"section": "5. Interpretation"}) == "frame"
    assert role({"section": "7 Policy documents and circulars superseded"}) == "frame"
    assert role({"section": "4 Effective date"}) == "frame"
    assert role({"section": "10 Technology Operations Management"}) == "content"
    assert role({"section": None}) == "content"
    split = by_role({"m": {"q": {"a": 1, "b": 9, "c": None}}},
                    {"a": "content", "b": "frame", "c": "frame"})
    assert split["m"] == {"content": (1, 1), "frame": (0, 2)}


def test_eval_skips_questions_with_nothing_to_retrieve():
    qs = load_golden()
    assert qs and all(q["expected"] for q in qs)


@needs_pdfs
def test_every_corpus_chunk_round_trips(enriched):
    chunks, _ = enriched
    keys = set()
    for c in chunks.values():
        doc = search_document(c, [])
        assert chunk_from_document(doc) == c, c["chunk_id"]
        assert set(OWN_FIELDS) <= set(c), c["chunk_id"]
        keys.add(doc["id"])
    assert len(keys) == len(chunks)


# --- opt-in: the live index (uv run pytest -m azure) ---------------------------------------


@pytest.mark.azure
def test_live_index_has_every_chunk_and_round_trips():
    import json

    from bnm_rag.index.azure import env, index_client, search_client
    from bnm_rag.parse.document import CORPUS

    with open(CORPUS / "chunks.jsonl", encoding="utf-8") as f:
        chunks = {c["chunk_id"]: c for c in map(json.loads, f)}
    stats = index_client().get_index_statistics(env("AZURE_SEARCH_INDEX"))
    assert stats.document_count == len(chunks)
    assert stats.storage_size < 50 * 1024 * 1024
    cid = "techreq-psr_pd:2.4"
    got = chunk_from_document(search_client().get_document(doc_key(cid)))
    assert got == chunks[cid]


@pytest.mark.azure
@pytest.mark.parametrize("mode", ["keyword", "vector", "hybrid"])
def test_live_search_finds_the_tier_thresholds(mode):
    from bnm_rag.index.azure import search

    got = search("Tech Requirements Tier-2 threshold RM1.5 billion 7 million transactions",
                 mode=mode, top=10)
    assert "techreq-psr_pd:2.4" in [c["chunk_id"] for c in got]
