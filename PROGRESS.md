# PROGRESS

## Now

- **Current step:** 4 — Index (Azure AI Search, Free tier, Southeast Asia)
- **Next action:** before any Azure call, confirm the open questions below. Then:
  `src/bnm_rag/index/` that (1) builds one search document per chunk from `chunks.jsonl`
  (text with heading path, plus filterable `doc_id`, `kind`, `obligation`, `applies_to`,
  `effective_from`, `effective_until`, page, source URL; no stored status), (2) embeds with
  Azure OpenAI `text-embedding-3-small`, (3) creates the index and uploads. Check the index size
  stays under the Free tier's 50 MB. Then an eval script: recall@5 of each golden question's
  `expected` chunks for keyword, vector and hybrid search, written to
  `docs/03-retrieval-results.md`. Azure tests use the `azure` pytest marker (opt-in).
- **Open questions for Karam:**
  1. Is the Azure subscription ready, and may I create (Free tier only) an AI Search service
     and an Azure OpenAI resource with a `text-embedding-3-small` deployment in Southeast Asia?
     Resource group name? (Check the embedding model is offered in that region first.)
  2. Put the keys/endpoints in `.env` (names in `.env.example`); I check them by name only.
  3. Still open from step 2: RMiT Appendix 12 is pending NACSA's endorsement. If you learn the
     date, give it and I'll set it.
- **Design note for step 5:** don't hard-filter retrieval on `applies_to`. "This rule doesn't
  bind you" is often the right answer (golden g18, g34, g44 cite chunks that exclude the asker),
  so use `applies_to` to label citations and steer the answer, not to drop chunks.
- **Read for this step:** `docs/02-phase1-plan.md` → Stack, Monthly cost, step 4;
  `evals/golden.yaml`; `.env.example`. Run `uv run python -m bnm_rag.parse` first (chunks are
  git-ignored).

## Steps (Phase 1)

Details and the check for each step: `docs/02-phase1-plan.md` → "Build steps".

- [x] 0. Repo setup
- [x] 1. Parser (PDF → `corpus/chunks.jsonl`)
- [x] 2. Metadata (Part A, applicability YAML, FAQ links, out-of-corpus list)
- [x] 3. Golden set (`evals/golden.yaml`, reviewed by Karam)
- [ ] 4. Index (Azure AI Search Free tier; retrieval comparison)
- [ ] 5. Agent (tools, structured reply, citation validation)
- [ ] 6. API + UI locally
- [ ] 7. Deploy to Azure
- [ ] 8. Case-study README

## Log

Newest first. One entry per work session: what was done, decisions, anything surprising.

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
