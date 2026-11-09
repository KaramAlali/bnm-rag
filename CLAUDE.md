# CLAUDE.md — BNM regulation assistant (bnm-rag)

A chat app that answers questions about Bank Negara Malaysia's payments and e-money rules from
their official policy documents, with paragraph-level citations, and is deployed on Azure.
A portfolio project: public repo, public demo, Karam's own (no client).

## Start of every session

When the user says "continue" (or anything like it):

1. Read **`PROGRESS.md` → "Now"** first. It names the current step, the next action, open
   questions, and the docs to read for that step.
2. Read only what "Now" points to. Do not re-read the whole repo or every doc.
3. If "Open questions" lists anything, ask those before building.
4. Tell the user in one or two lines where you are picking up, then start.

## Keeping progress current

- **Update `PROGRESS.md` before every commit request and at the end of every session**, so the
  next session can start from it alone:
  - "Now": the current step, the exact next action (specific enough to start on without
    re-reading), open questions, and what to read for it.
  - Tick a step's box only when its check (from the plan) passes.
  - Add one dated line to the top of "Log": what was done, decisions, surprises.
- Keep "Now" short; history goes in "Log".
- When a decision changes, also update `docs/02-phase1-plan.md` and this file. New findings
  about the documents go in `docs/01-corpus-report.md`.
- **Git: never commit without asking the user first.** Show the changes and a proposed
  message, then wait for a yes.

## Rules from the corpus (do not relax without asking)

- **Never present an exposure draft as a rule.** `open-finance_ed` is a proposal. Answers say
  "proposed", even though the draft states an effective date.
- **Status is computed, never stored.** `in force` / `not yet in force` / `proposed` /
  `superseded` comes from `kind` + `effective_from` / `effective_until` against today's date at
  answer time. Effective dates can differ by
  paragraph (RMiT 10.31, IFTF Appendix II, Merchant Acquiring, Complaints Handling 12.1–12.4),
  RMiT Appendix 12 waits for NACSA's endorsement, and Tech Requirements' date is computed (one
  year after 12 March 2026). `bnm_rag.metadata.status` computes it.
- **Every citation must come from that run's tool results.** A reply citing anything else is
  sent back to the model.
- **RMiT vs Tech Requirements depends on the firm.** Tier-1 payment providers follow RMiT (plus
  Tech Requirements paragraph 2.2); Tiers 2–4 follow Tech Requirements. Never mix them in one
  answer without saying which applies to whom.
- **"Not covered" beats a guess.** If the corpus doesn't cover it, say so and name the document
  that would (from the out-of-corpus list) when known.
- **Not legal advice.** The UI says so; answers point to the source paragraph.

## Corpus and data

- `corpus/raw/`: the 20 BNM PDFs (git-ignored; `corpus/sources.csv` has every URL, reference,
  issue and effective date). Re-download on Windows with
  `scripts/download_corpus.ps1` (reads the URLs from `sources.csv`).
- `corpus/text/`, `corpus/measurements.json`: from `scripts/measure_corpus.py` (git-ignored,
  regenerate any time).
- `corpus/chunks.jsonl` and `corpus/chunks.json` (the same chunks as one indented array, for
  reading): both written by `uv run python -m bnm_rag.parse` in one run (~30 s), and
  git-ignored because they hold the documents' full text. **Keep them in sync:** never edit
  either by hand or write one without the other; a test fails if they differ. Parser tests on
  the real PDFs skip when `corpus/raw/` is empty.
- `corpus/curated/figures.yaml`: hand transcriptions of the 8 figures the parser cannot read
  (pictures, one scrambled diagram); merged into the chunks with `figure: true`.
- Step 2 metadata (`src/bnm_rag/metadata/`) runs inside the same parse command:
  `corpus/curated/effective_dates.yaml` (date exceptions, each with a quote a test checks
  against the PDF text) and `corpus/curated/applicability.yaml` (roles, who each paragraph
  applies to, the Tech Requirements tiers) are hand-written; `corpus/related_docs.json`
  (related/superseded documents and the out-of-corpus list) is generated but **committed**,
  because the app needs it where the PDFs are not available; a test fails if it is stale.
- Index (step 4): `uv run python -m bnm_rag.index` rebuilds the Azure AI Search index from
  `chunks.jsonl` (drops and recreates it). The index holds every chunk field, so the deployed
  app needs no `chunks.jsonl`. Embeddings are cached in `corpus/embeddings.cache.jsonl`
  (git-ignored). Retrieval eval: `uv run python -m bnm_rag.index.evaluate` →
  `evals/retrieval_results.md`.
- Licensing: index the documents, show short excerpts, always link to the source PDF. Never
  republish whole documents.

## Environment

- Windows 11, PowerShell and Git Bash, Docker Desktop. Use `127.0.0.1` rather than `localhost`.
- Python 3.12+, `uv`. Lint `uv run ruff check`, test `uv run pytest`.
- Secrets only in `.env` (git-ignored). **Never print keys** in tool output or chat; check
  variables by name only.
- Azure: region **Southeast Asia** for every resource. AI Search starts on the **Free** tier.
  Do not create paid Azure resources (Basic search, extra replicas) without asking.
- Tests that call an LLM or Azure are opt-in markers, never in the default `pytest` run.

## Key decisions

- LangChain 1.x `create_agent` + structured reply; LLM via OpenRouter with a fallback chain.
- Azure AI Search hybrid (BM25 + vector); embeddings via Azure OpenAI.
- No database in Phase 1 (stateless chat). FastAPI + a React/Vite UI in one container on Azure
  Container Apps; Bicep + GitHub Actions (OIDC) to deploy.
- PyMuPDF for parsing; the few applicability tables are hand-written YAML with tests.
