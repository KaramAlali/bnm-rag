"""Azure clients (from .env), embeddings with a local cache, and search.

Keys come from the environment (.env locally); nothing here prints them.
"""

from __future__ import annotations

import array
import base64
import hashlib
import json
import os
from collections.abc import Iterator, Sequence
from functools import cache
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from dotenv import load_dotenv
from openai import OpenAI

from bnm_rag.index.documents import chunk_from_document, doc_key
from bnm_rag.parse.document import CORPUS, ROOT

# Embeddings already paid for, keyed by (deployment, text): rebuilding the index after a schema
# change re-embeds nothing. Git-ignored; vectors as base64 float32, one JSON object per line.
CACHE = CORPUS / "embeddings.cache.jsonl"
BATCH = 64  # chunks per embeddings request (largest chunk ~2.6k tokens; 100K TPM quota)

MODES = ("keyword", "vector", "hybrid")


def env(name: str) -> str:
    load_dotenv(ROOT / ".env")
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set (copy .env.example to .env and fill it in)")
    return value


@cache
def openai_client() -> OpenAI:
    # Azure OpenAI's v1 API: the plain OpenAI client, the deployment name as the model.
    endpoint = env("AZURE_OPENAI_ENDPOINT").rstrip("/")
    return OpenAI(base_url=f"{endpoint}/openai/v1/", api_key=env("AZURE_OPENAI_API_KEY"),
                  max_retries=10)


def index_client() -> SearchIndexClient:
    return SearchIndexClient(env("AZURE_SEARCH_ENDPOINT"),
                             AzureKeyCredential(env("AZURE_SEARCH_API_KEY")))


@cache
def search_client() -> SearchClient:
    return SearchClient(env("AZURE_SEARCH_ENDPOINT"), env("AZURE_SEARCH_INDEX"),
                        AzureKeyCredential(env("AZURE_SEARCH_API_KEY")))


def _cache_key(deployment: str, text: str) -> str:
    return hashlib.sha256(f"{deployment}\n{text}".encode()).hexdigest()


def _pack(vector: Sequence[float]) -> str:
    return base64.b64encode(array.array("f", vector).tobytes()).decode("ascii")


def _unpack(packed: str) -> list[float]:
    a = array.array("f")
    a.frombytes(base64.b64decode(packed))
    return a.tolist()


def _read_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {e["key"]: e["vector"] for e in map(json.loads, f)}


def _batches(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def embed(texts: list[str], cache_path: Path | None = CACHE) -> tuple[list[list[float]], int]:
    """Vectors for `texts` in order, and how many were newly embedded (the rest came from the
    cache). `cache_path=None` skips the cache (for queries)."""
    deployment = env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    keys = [_cache_key(deployment, t) for t in texts]
    known = _read_cache(cache_path) if cache_path else {}
    todo = sorted({k: t for k, t in zip(keys, texts, strict=True) if k not in known}.items())
    for batch in _batches(todo, BATCH):
        resp = openai_client().embeddings.create(model=deployment, input=[t for _, t in batch])
        new = {k: _pack(d.embedding) for (k, _), d in zip(batch, resp.data, strict=True)}
        known.update(new)
        if cache_path:
            with open(cache_path, "a", encoding="utf-8", newline="\n") as f:
                for k, v in new.items():
                    f.write(json.dumps({"key": k, "vector": v}) + "\n")
    return [_unpack(known[k]) for k in keys], len(todo)


def embed_query(text: str) -> list[float]:
    return embed([text], cache_path=None)[0][0]


def get_chunk(chunk_id: str) -> dict | None:
    """One chunk by id (a key lookup, no search), or None if there is no such chunk."""
    try:
        return chunk_from_document(search_client().get_document(doc_key(chunk_id)))
    except ResourceNotFoundError:
        return None


def chunks_where(filter: str, top: int = 100) -> list[dict]:
    """Every chunk matching an OData filter (no ranking), e.g. a document's frame paragraphs.
    Callers must build `filter` from validated values only (doc ids from the catalog)."""
    return [chunk_from_document(r) for r in search_client().search(
        search_text="*", filter=filter, top=top)]


def search(query: str, mode: str = "hybrid", top: int = 5, filter: str | None = None,
           candidates: int = 50) -> list[dict]:
    """Chunks for `query`, best first, each with its `score`.
    keyword: BM25 over `content`; vector: cosine nearest neighbours of the query embedding;
    hybrid: both, merged by Azure's reciprocal rank fusion (each side contributes up to
    `candidates`). `filter` is an OData filter, e.g. "kind ne 'exposure_draft'"."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    vector_queries = None
    if mode != "keyword":
        k = top if mode == "vector" else max(top, candidates)
        vector_queries = [VectorizedQuery(vector=embed_query(query), k_nearest_neighbors=k,
                                          fields="vector")]
    results = search_client().search(
        search_text=query if mode != "vector" else None,
        vector_queries=vector_queries,
        filter=filter,
        top=top,
    )
    out = []
    for r in results:
        chunk = chunk_from_document(r)
        chunk["score"] = r["@search.score"]
        out.append(chunk)
    return out
