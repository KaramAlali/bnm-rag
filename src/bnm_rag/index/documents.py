"""Chunk ↔ search document. Pure functions, no Azure calls, so they are tested offline.

The index is the app's run-time copy of the corpus: the deployed app has no chunks.jsonl (it is
git-ignored because it holds the documents' full text), so every chunk field must survive the
round trip `chunk_from_document(search_document(chunk, vector))`. Fields the search filters or
shows get their own index field; the rest travel as one JSON string in `meta`.
Status is not stored (CLAUDE.md): it is computed from kind and the effective dates at answer time.
"""

from __future__ import annotations

import base64
import json

# Chunk fields that get their own index field (see schema.py); everything else goes in `meta`.
OWN_FIELDS = ("chunk_id", "doc_id", "para_no", "kind", "obligation", "title", "reference",
              "heading_path", "text", "page_start", "page_end", "source_url", "figure",
              "issued", "effective_from", "effective_until", "applies_to")


def doc_key(chunk_id: str) -> str:
    """Azure Search keys allow only letters, digits, '_', '-' and '='; chunk ids have ':', ' '
    and '/' ("rmit_pd:Appendix 5 / 3.2"), so the key is the chunk id in URL-safe base64."""
    return base64.urlsafe_b64encode(chunk_id.encode("utf-8")).decode("ascii")


def embedding_text(chunk: dict) -> str:
    """What is embedded and what BM25 searches (one text, so the keyword/vector comparison is
    fair): document title and reference, where the paragraph sits, its number and S/G mark,
    the text, then its footnotes."""
    head = chunk["title"] + (f" ({chunk['reference']})" if chunk.get("reference") else "")
    label = chunk["para_no"]
    if chunk["obligation"] in ("S", "G"):
        label += f" [{chunk['obligation']}]"
    lines = [head]
    if chunk["heading_path"]:
        lines.append(" > ".join(chunk["heading_path"]))
    lines += [label, chunk["text"]]
    lines += [f"Footnote {f['n']}: {f['text']}" for f in chunk.get("footnotes", [])]
    return "\n".join(lines)


def search_document(chunk: dict, vector: list[float]) -> dict:
    doc = {k: chunk.get(k) for k in OWN_FIELDS}
    doc["id"] = doc_key(chunk["chunk_id"])
    doc["content"] = embedding_text(chunk)
    doc["vector"] = vector
    doc["meta"] = json.dumps({k: v for k, v in chunk.items() if k not in OWN_FIELDS},
                             ensure_ascii=False)
    return doc


def chunk_from_document(doc: dict) -> dict:
    """The chunk back from a search result (search scores and index-only fields dropped)."""
    chunk = {k: doc.get(k) for k in OWN_FIELDS}
    chunk.update(json.loads(doc["meta"]))
    return chunk
