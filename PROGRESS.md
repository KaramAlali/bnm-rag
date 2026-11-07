# PROGRESS

## Now

- **Current step:** 3 — Golden set
- **Next action:** draft `evals/golden.yaml`, ~40 questions in the demo persona's voice
  (compliance/tech lead at an e-wallet or payment gateway). Each: `question`, `expected`
  chunk_ids, `must_say` / `must_not_say` facts, `coverage` (answered | partial | not_covered),
  and the firm roles assumed (from `corpus/curated/applicability.yaml`). Cover: the four
  "done" questions; the Open Finance draft trap; RMiT vs Tech Requirements (eligible vs standard
  EMI, the RM800m e-wallet); each finding-3 date case (RMiT 10.31, Appendix 12 pending, IFTF
  Nexus, Complaints 12.1–12.4); thresholds (tiers, 5% market share, RM50m card issuer); FAQ-backed
  answers; out-of-corpus (AML/CFT, Outsourcing, crypto → Securities Commission); a few in Malay.
  Add a test that every expected chunk_id exists in `chunks.jsonl`. Then Karam reviews each
  expected answer against the PDF.
- **Open questions for Karam:**
  1. RMiT Appendix 12 is marked pending NACSA's endorsement. If you know it has been endorsed
     (and from when), give the date and I'll set it.
- **Read for this step:** `docs/02-phase1-plan.md` → "Who it's for", "What done means", step 3;
  `corpus/curated/applicability.yaml` (roles); `corpus/related_docs.json` (out-of-corpus titles).
  Run `uv run python -m bnm_rag.parse` first (chunks are git-ignored).

## Steps (Phase 1)

Details and the check for each step: `docs/02-phase1-plan.md` → "Build steps".

- [x] 0. Repo setup
- [x] 1. Parser (PDF → `corpus/chunks.jsonl`)
- [x] 2. Metadata (Part A, applicability YAML, FAQ links, out-of-corpus list)
- [ ] 3. Golden set (`evals/golden.yaml`, reviewed by Karam)
- [ ] 4. Index (Azure AI Search Free tier; retrieval comparison)
- [ ] 5. Agent (tools, structured reply, citation validation)
- [ ] 6. API + UI locally
- [ ] 7. Deploy to Azure
- [ ] 8. Case-study README

## Log

Newest first. One entry per work session: what was done, decisions, anything surprising.

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
