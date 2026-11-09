"""Build the Azure AI Search index from corpus/chunks.jsonl: embed every chunk (cached), drop and
recreate the index, upload, then print the index size against the Free tier's 50 MB.

Usage: uv run python -m bnm_rag.index [--compress]
Needs corpus/chunks.jsonl (uv run python -m bnm_rag.parse) and the Azure values in .env.
"""

from __future__ import annotations

import json
import sys
import time

from bnm_rag.index.azure import embed, env, index_client, search_client
from bnm_rag.index.documents import embedding_text, search_document
from bnm_rag.index.schema import index_definition
from bnm_rag.parse.document import CORPUS

FREE_TIER_BYTES = 50 * 1024 * 1024
UPLOAD_BATCH = 100


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f} MB"


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with open(CORPUS / "chunks.jsonl", encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    print(f"{len(chunks)} chunks")

    t = time.monotonic()
    vectors, new = embed([embedding_text(c) for c in chunks])
    print(f"embedded: {new} new, {len(chunks) - new} from cache ({time.monotonic() - t:.0f} s)")

    name = env("AZURE_SEARCH_INDEX")
    indexes = index_client()
    if name in set(indexes.list_index_names()):
        indexes.delete_index(name)
        print(f"dropped index {name}")
    indexes.create_index(index_definition(name, compress="--compress" in argv))
    print(f"created index {name}" + (" (int8 compression)" if "--compress" in argv else ""))

    docs = [search_document(c, v) for c, v in zip(chunks, vectors, strict=True)]
    failed = []
    for i in range(0, len(docs), UPLOAD_BATCH):
        results = search_client().upload_documents(docs[i:i + UPLOAD_BATCH])
        failed += [r.key for r in results if not r.succeeded]
    if failed:
        raise RuntimeError(f"{len(failed)} documents failed to upload, e.g. {failed[:3]}")
    print(f"uploaded {len(docs)} documents")

    # Index statistics lag the upload (over a minute on the Free tier); wait for the count.
    print("waiting for index statistics ...")
    for _ in range(60):
        stats = indexes.get_index_statistics(name)
        if stats.document_count == len(docs):
            break
        time.sleep(5)
    else:
        print("statistics not updated yet; re-check later with get_index_statistics")
        return
    # The Free tier's 50 MB quota counts storage_size; the vector index (HNSW, in memory) has
    # no separate quota on Free (service statistics: vector_index_size_counter quota None).
    used = stats.storage_size
    print(f"documents {stats.document_count}, storage {mb(used)} "
          f"({used / FREE_TIER_BYTES:.0%} of the Free tier's 50 MB), "
          f"vector index {mb(stats.vector_index_size)}")


if __name__ == "__main__":
    main(sys.argv[1:])
