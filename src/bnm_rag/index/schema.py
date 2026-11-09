"""The Azure AI Search index definition: one document per chunk, BM25 over `content`, HNSW
(cosine) over `vector`. Free tier: 50 MB in all, so the vector field is `stored=False` (searchable,
never returned; saves a second copy of every vector) and int8 scalar compression is available
behind `compress=True` if the index grows close to the limit.
"""

from __future__ import annotations

from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    ScalarQuantizationCompression,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

DIMENSIONS = 1536  # text-embedding-3-small
ANALYZER = "en.microsoft"  # English stemming ("requirements" matches "requirement")

String = SearchFieldDataType.STRING
Strings = SearchFieldDataType.Collection(SearchFieldDataType.STRING)


def _field(name: str, type_: str = String, **kw) -> SearchField:
    # Retrievable by default; nothing searchable, filterable or sortable unless asked for.
    opts = {"searchable": False, "filterable": False, "sortable": False, "facetable": False}
    return SearchField(name=name, type=type_, **(opts | kw))


def index_definition(name: str, compress: bool = False) -> SearchIndex:
    fields = [
        _field("id", key=True, filterable=True),
        _field("chunk_id", filterable=True),
        _field("doc_id", filterable=True, facetable=True),
        _field("para_no"),
        _field("kind", filterable=True, facetable=True),
        _field("obligation", filterable=True, facetable=True),
        _field("title"),
        _field("reference"),
        _field("heading_path", Strings),
        _field("text"),
        _field("content", searchable=True, retrievable=False, analyzer_name=ANALYZER),
        _field("page_start", SearchFieldDataType.INT32),
        _field("page_end", SearchFieldDataType.INT32),
        _field("source_url"),
        _field("figure", SearchFieldDataType.BOOLEAN, filterable=True),
        _field("issued", filterable=True, sortable=True),
        # ISO dates or "pending: <event>", kept as strings; status is computed, not stored.
        _field("effective_from", filterable=True),
        _field("effective_until", filterable=True),
        _field("applies_to", Strings, filterable=True, facetable=True),
        # Index-only (not a chunk field): applicability / effective_date / interpretation /
        # superseded for Part A frame paragraphs, else null (documents.frame_kind).
        _field("frame_kind", filterable=True),
        _field("meta"),
        SearchField(
            name="vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.SINGLE),
            searchable=True,
            retrievable=False,
            stored=False,
            vector_search_dimensions=DIMENSIONS,
            vector_search_profile_name="vec",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(
            name="hnsw",
            parameters=HnswParameters(metric=VectorSearchAlgorithmMetric.COSINE),
        )],
        profiles=[VectorSearchProfile(
            name="vec",
            algorithm_configuration_name="hnsw",
            compression_name="int8" if compress else None,
        )],
        compressions=[ScalarQuantizationCompression(compression_name="int8")] if compress else None,
    )
    return SearchIndex(name=name, fields=fields, vector_search=vector_search)
