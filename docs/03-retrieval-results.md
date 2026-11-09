# 03 — Retrieval results (step 4)

**Question:** with the golden set's questions typed as-is, how often does Azure AI Search put
the paragraphs a correct answer must cite into the top 5, and is hybrid search worth it?

**Set-up (2026-11-09):** 2,157 chunks, one search document each, in the `bnm-rag` index on the
Free tier in Southeast Asia. The text embedded and the text BM25 searches are the same: document
title and reference, heading path, paragraph number with its S/G mark, the paragraph text, and
its footnotes. `text-embedding-3-small` vectors (1536 dimensions) go in an HNSW index with
cosine similarity. BM25 uses the `en.microsoft` analyzer. Hybrid search is Azure's
reciprocal rank fusion (RRF) of BM25 and the 50 nearest vectors. No filters, no reranker (the
semantic ranker isn't available on Free). 41 of the 44 golden questions have expected chunks; the
three not-covered ones are left out.

Rebuild with `uv run python -m bnm_rag.index` (about 4 minutes the first time; the embeddings
are then cached in `corpus/embeddings.cache.jsonl`). Re-measure with
`uv run python -m bnm_rag.index.evaluate`. Every rank for every question is in
[`evals/retrieval_results.md`](../evals/retrieval_results.md) (generated).

## Results

| mode | recall@5 | recall@10 | recall@20 | all@5 | hit@5 |
|---|---:|---:|---:|---:|---:|
| keyword (BM25) | 35% | 49% | 55% | 22% | 49% |
| vector | 47% | 55% | 68% | 29% | 63% |
| **hybrid** | **51%** | **56%** | **66%** | **37%** | **66%** |

recall@k is the share of a question's expected chunks in the top k, averaged over questions.
all@5 is the share of questions with every expected chunk in the top 5, and hit@5 the share with
at least one.

Expected chunks in the top 5, split by what the paragraph does:

| mode | content paragraphs | frame paragraphs |
|---|---:|---:|
| keyword | 36% (20/55) | 22% (7/32) |
| vector | 47% (26/55) | 28% (9/32) |
| hybrid | 56% (31/55) | 25% (8/32) |

"Frame" paragraphs come from the Applicability, Effective date, Interpretation and Superseded
sections: who the document applies to, what its terms mean, when it starts and what it replaces.

## Findings

1. **Hybrid is the best single mode, so the agent uses it.** It leads on recall@5 (51%) and by
   more on all@5 (37% vs 29% for vector). Vector alone goes deeper (68% at 20) but ranks worse
   near the top. BM25 alone is weakest, though it finds exact paragraph wording that vector
   search misses (g11 Tech Requirements 5.2 at rank 3, g13 RMiT FAQ Q18 at rank 5).
2. **One search with the user's own words gets about half the answer.** Even at depth 20, a third
   of the expected paragraphs are missing. The answer has to come from an agent that searches
   several times, not from one retrieval call. Step 5 is planned that way.
3. **Questions about the asker's situation pull in the wrong paragraphs.** g01 ("We're an
   e-wallet with RM800m a year. Which tech rules apply and when?") returns the e-Money PD's
   wallet limits (20.6–20.9) in every mode, because "e-wallet" and "RM" amounts match them. g09,
   which uses the regulation's own terms, finds Tech Requirements 2.4 at rank 1 in every mode.
   *Step 5:* the agent rewrites the question in regulatory terms and searches several times (for
   example once for "Technology Requirements tiers" and once for "e-money technology risk").
4. **Frame paragraphs are rarely found by search (25%), and that's expected.** "This policy
   document comes into effect on 12 March 2027" (Tech Requirements 4.1) shares no meaning with
   "when do the rules apply". *Step 5:* don't rely on search for them:
   - Every chunk already carries `effective_from`, `effective_until` and `applies_to`.
   - A `get_paragraph` call, or a "document frame" lookup, fetches a cited document's
     Applicability, Effective date and Superseded paragraphs.
5. **Long definition chunks are never in the top 5 in any mode.** The Interpretation paragraphs
   (5.2) in the golden set are 2.5k–7k characters. One vector for dozens of definitions matches no
   single question, and BM25 can't single them out either. Two options:
   - Split them into one chunk per defined term (a parser change; the noted step 1 limit).
   - Fetch them by number through `get_paragraph`.
   **Decision for Karam.**
6. **Questions in Malay retrieve as well as English ones in vector and hybrid search** (50%
   recall@5 for the 4 questions), but only 25% with BM25, as expected: the documents are English.
7. **Drafts and supersession are the weakest groups.** For Open Finance (g02, g40) and the
   e-Money vs Tech Requirements handover (g30), the deciding paragraphs are appendix tables and
   frame paragraphs. The agent's document-level tools (`list_documents`, the frame lookup) and
   computed status need to carry these, not search.

## Index size (the Free tier's 50 MB)

| | |
|---|---|
| Documents | 2,157 |
| Storage (counts towards the 50 MB quota) | 15.2 MB (30%) |
| Vector index (HNSW, in memory; no Free-tier quota per the service statistics) | 38.3 MB |

The vector field is `stored: false`: it's searchable but never returned, so the index keeps no
second copy of the vectors. int8 scalar compression is ready (`--compress`) but not needed. The
index can roughly triple before storage becomes a problem, which matters for Phase 2's wider
corpus.

## Cost and time

Embedding the whole corpus took about 300k tokens: under one US cent, and 250 s at the
deployment's 100K tokens-per-minute limit (the client waits out 429 rate-limit responses on its
own). An eval run makes 82 query embeddings and 123 searches.

## Not tried yet (worth trying if step 5 falls short)

- **Semantic ranker** (needs the Basic tier, about $74/month; ask first).
- **Weighting** the vector side of hybrid search.
- **Smaller or larger chunks.**
- **Query rewriting before the search.** This becomes the agent's job in step 5.
