# PROGRESS

## Now

- **Current step:** 6 — API + UI locally (FastAPI + React/Vite, citation chips, `docker compose up`)
- **Step 5 passed (2026-11-09):** every hard rule of the pass bar held; expected cited 95%,
  facts 98%, faithful 86% after hand checks, coverage 91% (`docs/04-agent-results.md`).
- **Blocker: OpenRouter credits ran out** (HTTP 402) during the last eval. Karam must top up
  before the agent can answer again (step 6 needs it to test in the browser).
- **Next action:** top up OpenRouter (Karam), then build step 6:
  - FastAPI `POST /chat` wrapping `bnm_rag.agent.run.ask`, with server-sent progress events
    (tool calls) and the final `Answer`;
  - the React + Vite + TypeScript + Tailwind UI: citation chips open the paragraph text and
    the PDF page link (`citation()["url"]`), the "not legal advice" notice, status badges;
  - one Docker image, and `docker compose up` for local runs.
  Check: the four "done" questions work in the browser.
- **Azure (2026-11-09):** Free Trial, spending limit on, MFA; CLI via `az login`. All in
  `rg-bnm-rag`, Southeast Asia: AI Search `srch-bnm-rag-1pk6` (Free) holding index `bnm-rag`
  (2,157 docs, 15.2 MB of 50 MB); Azure OpenAI `oai-bnm-rag-1pk6` with deployment
  `text-embedding-3-small` (GlobalStandard, the only type offered there; 100K TPM). Providers
  registered: Search and CognitiveServices only (add Container Apps, ACR, Key Vault, Log
  Analytics at step 7). `.env` holds both endpoints and keys.
- **LLM (2026-11-09):** OpenRouter, key in `.env` (Karam).
  - Karam chose GLM and DeepSeek. `.env` now holds
    `OPENROUTER_MODELS=deepseek/deepseek-v4.1-flash-1017,z-ai/glm-5.3`: DeepSeek's dated
    snapshot first, GLM as the fallback. Comma-separated, tried in order. The eval's judge is
    `z-ai/glm-5.3` (`JUDGE_MODEL`), so it isn't the model that answered.
  - Both support tools and structured output on OpenRouter. Both made a correct tool call in a
    smoke test.
  - Prices per million tokens, input/output: GLM-5.3 $0.07/$1.40, DeepSeek V4.1 Flash
    $0.05/$0.57.
- **Index commands:** rebuild `uv run python -m bnm_rag.index` (embeddings cached in
  `corpus/embeddings.cache.jsonl`, git-ignored); eval `uv run python -m bnm_rag.index.evaluate`
  → `evals/retrieval_results.md`; live checks `uv run pytest -m azure`.
- **Agent commands:** ask `uv run python -m bnm_rag.ask "…" [--date YYYY-MM-DD] [--verbose]`;
  golden eval `uv run python -m bnm_rag.agent.evaluate [ids]` → `evals/agent_results.md`
  (replies in `evals/agent_answers.jsonl`, git-ignored); live test `uv run pytest -m llm`.
- **Open questions for Karam:**
  1. g12's `must_not_say` ("a detailed list of changes presented as coming from the documents")
     predates finding the RMiT FAQ's own revision history, which the agent now quotes and
     attributes correctly. Reword it to "…not drawn from the indexed documents"?
  2. Coverage labels: g11, g33, g35 say `partial` (and g04 `partial`, not `not_covered`)
     because un-indexed documents also apply. Accept `partial` there, or keep the labels strict?
  3. Still open from step 2: RMiT Appendix 12 is pending NACSA's endorsement. If you learn the
     date, give it and I'll set it.
- **Decision (Karam, 2026-11-09): definitions stay whole.** The Interpretation paragraphs
  (5.2, 2.5k–7k characters each) stay one chunk per document. They're never in the top 5, so
  the agent fetches them with `get_paragraph(doc_id, "5.2")` when a defined term matters. No
  parser change.
- **Design note for step 5:** don't hard-filter retrieval on `applies_to`. "This rule doesn't
  bind you" is often the right answer (golden g18, g34, g44 cite chunks that exclude the asker),
  so use `applies_to` to label citations and steer the answer, not to drop chunks.
- **Read for this step:** `docs/02-phase1-plan.md` → Stack (API, UI), step 6, "What done
  means"; `src/bnm_rag/agent/run.py` (`ask`, `Answer`) and `reply.py` (`citation`).

## Steps (Phase 1)

Details and the check for each step: `docs/02-phase1-plan.md` → "Build steps".

- [x] 0. Repo setup
- [x] 1. Parser (PDF → `corpus/chunks.jsonl`)
- [x] 2. Metadata (Part A, applicability YAML, FAQ links, out-of-corpus list)
- [x] 3. Golden set (`evals/golden.yaml`, reviewed by Karam)
- [x] 4. Index (Azure AI Search Free tier; retrieval comparison)
- [x] 5. Agent (tools, structured reply, citation validation)
- [ ] 6. API + UI locally
- [ ] 7. Deploy to Azure
- [ ] 8. Case-study README

## Log

Newest first. One entry per work session: what was done, decisions, anything surprising.

- 2026-11-09 — Step 5 passed. Karam asked for a rerun of only the 7 targeted questions.
  - The 5 former crashes all answer now.
  - g27 now limits Appendix 10 to merchant acquiring.
  - g12 now says a comparison isn't possible and answers partial. Its judge call failed
    because the OpenRouter credits ran out (HTTP 402), so it was hand-checked and passed: the
    list matches the RMiT FAQ's revision history.
  - Merged run: 44/44 answered, 0 forbidden claims, expected cited 95%, facts 98%, faithful
    86% (judge 37/44 plus g21 cleared by hand), coverage 91%.
  - The judge now retries once when it returns no verdict. A partial rerun merges into the
    saved results.

- 2026-11-09 — Step 5 built, not yet ticked.
  - **Models:** Karam chose GLM and DeepSeek. Then `.env` was changed to DeepSeek's dated
    snapshot first, GLM as the fallback.
  - **Definitions:** Karam decided they stay whole; the agent fetches 5.2 with `get_paragraph`.
  - **Index:** gained an index-only `frame_kind` field (applicability / effective_date /
    interpretation / superseded), so `get_document_frame(doc_id)` fetches those paragraphs by
    filter. The index was rebuilt from cached embeddings; storage is 15.0 MB.
  - **Agent** (`src/bnm_rag/agent/`):
    - four tools that return their chunks as artifacts;
    - a structured `Reply`;
    - checks: citations must come from this run's tool results (footnote and sub-item
      suffixes such as "2.4, footnote 4" resolve to the paragraph), an answer must cite
      something, a draft must be called "proposed";
    - up to 2 sends back, `ModelFallbackMiddleware`, a 120 s request timeout;
    - the CLI `bnm_rag.ask`;
    - `agent/evaluate.py`: code scores plus a GLM-5.3 judge that sees the cited paragraphs as
      the agent saw them.
    - New dependencies: langchain 1.4, langchain-openrouter.
  - **Golden run** (`docs/04-agent-results.md`): 39 of 44 answered, 93% of expected paragraphs
    cited (vs 51% for one raw search), 95% of required facts, 2 forbidden claims (g12, g27).
  - **Spot-check:** 5 real errors, 3 small overreaches, 1 over-strict judge, 4 debatable
    `partial` labels.
  - **Surprises:**
    - ChatOpenRouter has no timeout by default; one stalled call held a question for 405 s.
    - 5 questions ended without calling the Reply tool. That's now sent back like any other
      failed check, but not rerun yet, at Karam's call.
    - `evals/agent_answers.jsonl` holds the cited paragraphs' full text, so it's git-ignored.
  - 121 offline tests pass.
  - **Later the same day:**
    - Karam agreed the pass bar (plan step 5, golden.yaml header) and asked for no full
      rerun.
    - g27 traced to a data gap: TR 2.2 lists Appendix 10, but its acquirer-only scope sits in
      2.6(d), footnote 7 and FAQ Q3, none linked to 2.2. Fixed with a curated note on 2.2;
      index rebuilt, all embeddings from cache.
    - Prompt rules added for "what changed" (g12) and for not inferring dates or sums.
    - The issue date added to rendered chunks.

- 2026-11-09 — Step 4 done: `src/bnm_rag/index/`:
  - `documents.py`: chunk ↔ search document. The key is the chunk id in base64, because chunk
    ids contain ':', ' ' and '/'. Fields the app filters on or shows get their own index field;
    the rest go in a JSON `meta` field. Every chunk round-trips exactly, so the deployed app
    needs only the index. No status stored.
  - `schema.py`: BM25 on `content` (en.microsoft analyzer); HNSW cosine on `vector`, set to
    `stored: false`; int8 compression behind `--compress`.
  - `azure.py`: an OpenAI v1 client on the Azure endpoint, plus embeddings cached in
    `corpus/embeddings.cache.jsonl`.
  - `search()`: keyword, vector and hybrid modes.
  - `evaluate.py`: recall@5/10/20, all@5 and hit@5, by group and by content vs frame paragraph.
  - New dependencies: azure-search-documents 12, openai 3, python-dotenv.

  Index built: 2,157 documents, 15.2 MB of storage (30% of 50 MB); the vector index of 38.3 MB
  has no Free-tier quota. Embedding took about 300k tokens, under 1 cent, in 250 s. Results in
  `docs/03-retrieval-results.md`: recall@5 is keyword 35%, vector 47%, hybrid 51% (all@5 22/29/37%).
  Frame paragraphs (applicability, effective date, interpretation, superseded) reach the top 5
  only about 25% of the time, so in step 5 they come from metadata or lookup, not search.
  Surprise: g01 ("e-wallet with RM800m") retrieves the e-Money PD wallet limits in every mode,
  while the same question in regulatory terms (g09) finds Tech Requirements 2.4 at rank 1, so
  the agent must rewrite queries. 104 offline tests and 4 Azure tests pass.

- 2026-11-09 — Step 4 prep: Karam created the Azure account (Free Trial, spending limit on)
  and turned on MFA; Azure CLI installed via winget. Registered `Microsoft.Search` and
  `Microsoft.CognitiveServices` (no resources created). Resource group name agreed:
  `rg-bnm-rag`. Surprise: `text-embedding-3-small` has no regional Standard deployment in
  Southeast Asia, only GlobalStandard (requests may be processed in any Azure region; fine for
  public BNM documents) with a 1000K TPM quota, far above the ~330k tokens to embed once.
  Discussed dropping Azure (in-app BM25 + vectors) vs a `Retriever` interface with Azure as
  one backend; no change decided, the plan stays on Azure. Then created (Karam approved the
  commands, including accepting the Azure OpenAI terms via `--yes`): `rg-bnm-rag`, Free search
  `srch-bnm-rag-1pk6`, Azure OpenAI `oai-bnm-rag-1pk6` + `text-embedding-3-small` deployment;
  `.env` written from `.env.example` (keys never printed); both services smoke-tested.
  Surprise: opening the Foundry portal from the OpenAI resource silently created a Foundry
  (`AIServices`) resource + project in **West US 3**, named after Karam's email; deleted on
  Karam's yes (soft-deleted 48 h, not purged). Lesson: when using the Foundry portal, pick the
  existing `oai-bnm-rag-1pk6` and decline any "create project/resource" prompt.

- 2026-11-07 — Step 3 done: Karam reviewed all 44 golden questions (`reviewed: true`). By
  signing off g01, g08, g30, g43, g44 he accepted the Tech Requirements 7.1 readings: supersession
  takes effect on 12 March 2027; Merchant Acquiring 17-21 only; PSO 18-19 only for designated
  payment system operators.

- 2026-11-07 — Golden set pre-check by Claude (g03–g44, against the printed paragraphs):
  16 questions had a required fact backed only by an `also_ok` paragraph; those paragraphs moved
  into `expected` (rule: every `must_say` fact rests on an `expected` chunk; dates may come
  from chunk metadata). g11 dropped the Appendix 10 detail; g28 gained today's e-Money PD cloud
  rules (28.51) next to the 2027 Tech Requirements ones. Karam reviewed g01, g02 (g01 now
  expects Tech Requirements 7.1). The rest stay `reviewed: false` until Karam checks them.

- 2026-11-07 — Step 2 committed (50454ef, not pushed). Step 3 drafted: `evals/golden.yaml`,
  44 questions (4 "done", draft trap x3, RMiT vs Tech Requirements, every finding-3 date case,
  thresholds, FAQ-backed, out-of-corpus incl. crypto → SC, 4 in Malay), each with firm roles,
  expected chunk_ids and must/must-not facts; `tests/test_golden.py` checks the format and that
  every chunk_id exists. Surprise while drafting: Tech Requirements 7.1 supersedes e-Money PD
  27-31, Merchant Acquiring 17-21 and PSO 18-19 (designated operators), so step 2 gained
  `effective_until` and a `superseded` status; until 12 March 2027 an e-wallet's tech rules
  are e-Money PD 27-31. Cross-check: computed status/applicability agree with every expected
  answer; three questions deliberately cite chunks that exclude the asker. 95 tests pass.

- 2026-11-07 — Step 2 metadata done: `src/bnm_rag/metadata/`, run inside
  `python -m bnm_rag.parse`, so chunks gain `issued`, `version`, `effective_from`,
  `effective_exceptions`, `effective_note`, `applies_to`, `applies_note`, `parent_doc`,
  `faq_links`/`refers_to`. Karam checked the 8 figure transcriptions. Decisions: document dates
  parsed from 4.1, the 11 exceptions hand-written in `corpus/curated/effective_dates.yaml` with
  a quote per entry that a test checks against the chunk (they are worded differently in each
  document and some sit in the body); exceptions for some sub-items or firms are listed, not
  forced into one date; status computed in `metadata/status.py`. Applicability as 20 firm
  roles (a firm can hold several) in `corpus/curated/applicability.yaml`, with RMiT 2.2, Tech
  Requirements 2.2–2.6, IFTF's 2.2 table, Complaints 2.2–2.4 and MCIPD Part C as rules, plus
  `tech_requirements_tier()`. `corpus/related_docs.json` is committed (titles only; the app
  needs it without the PDFs). Surprises: RMiT Appendix 12 (NCII Code of Practice) is pending
  NACSA endorsement; RMiT 10.35(e) starts 15 Oct 2027; RMiT superseded the e-banking fraud
  letters that IFTF and Open Finance still cite; one document under up to 3 names. Corpus
  fixture moved to `tests/conftest.py`. 90 tests pass. Karam confirmed Tech Requirements
  2.4: Tier-2 if either the value or the volume threshold is exceeded (an "or"). Karam kept
  the firm-type readings: MCIPD leaves out merchant acquirers, MSBs and designated payment
  system operators (not in its FSP list); e-KYC keeps one insurer role with a "life and family
  takaful only" note.

- 2026-10-31 — Step 1 follow-up after Karam spotted Open Finance Diagram 1 missing and MCIPD
  13.2 at 15.6k chars. A check of every page line against the chunks found 7 figures that are
  pictures with no text layer (Sandbox Appendices I/III/IV incl. the Green Lane mechanism,
  Sandbox FAQ Q1's eligibility table, Complaints Appendix I, the RMiT/TR FAQ key-management
  diagram) plus the scrambled vector diagram. Decision: hand-transcribe them in
  `corpus/curated/figures.yaml` (not OCR or a vision LLM: 8 figures, one blurry); chunks get
  `figure: true`. Also: MCIPD's table split per item (`13.2 / item n`, fixed columns; Karam
  chose 13.2, where it is printed, over 13.1, which makes it binding); stacked headings kept and wrapped ones joined; appendices keep a section level; Open Finance
  preface chunk (no officers' emails); lone U+FFFD glyph = bullet. 2,157 chunks, S/G still
  886/229. The parser now also writes `corpus/chunks.json` (same chunks, indented array, for
  reading) in the same run; a test checks the two match. 46 tests pass. Report finding 11.

- 2026-10-31 — Step 1 parser done: `src/bnm_rag/parse/` (layout → chunk → document),
  `uv run python -m bnm_rag.parse` writes 2,146 chunks in ~30 s. 37 tests pass (16 rule tests
  run anywhere; 21 on the real PDFs skip without them). S/G counts are exact at 886/229; the
  measurement script's 881 missed MCIPD 8.1–8.4 and Merchant Acquiring 14.6 (report finding 10).
  Decisions: `chunks.jsonl` git-ignored (full text = republishing); FAQ chunks are "Q: …\nA: …"
  with `para_refs` from "[Paragraph x.y]"; e-KYC FAQ and Complaints FS split by fixed column
  positions (`TABLE_LAYOUTS`); repeated numbers get the part/sub-heading in `para_no`
  (e.g. `emoney_faq:Part B / Q1`). Known limits: 5.2 definition chunks are 4.5k–15.6k chars
  (revisit in step 4); a footnote carried onto a page with no new footnote isn't detected.

- 2026-10-31 — Created the public repo https://github.com/KaramAlali/bnm-rag and pushed
  `main`. Step 0 done.
- 2026-10-31 — Step 0 local setup: `git init` (branch `main`), `uv init --lib` (package
  `bnm_rag` in `src/`, Python 3.12+), dev deps ruff + pytest, ruff rules E/F/W/I/B/UP/SIM at
  100 cols, pytest markers `llm`/`azure` excluded by default, `.gitignore`, `.env.example`
  (names only), README stub. One smoke test, because pytest exits 5 on a truly empty suite.
  Ruff autofixed the imports in `scripts/measure_corpus.py` (dropped unused `sys`).
  Surprise: Python's `write_text` on Windows defaults to cp1252; pass `encoding="utf-8"` in
  every script that writes files. First commit made; Karam chose to hold off on creating the
  GitHub repo. Author email switched to the GitHub noreply address
  (`183481057+KaramAlali@users.noreply.github.com`, repo-level git config and `pyproject.toml`
  `authors`) so no personal or work address goes public.
- 2026-10-31 — Planning done outside Claude Code: corpus downloaded and measured
  (`docs/01-corpus-report.md`), Phase 1 plan written (`docs/02-phase1-plan.md`), this file and
  `CLAUDE.md` created. Nothing built yet.
