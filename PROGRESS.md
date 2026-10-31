# PROGRESS

## Now

- **Current step:** 2 — Metadata
- **Next action:** write `src/bnm_rag/metadata/` that reads each policy document's Part A
  chunks from `corpus/chunks.jsonl` (sections 4 Effective date, 6 Related documents, 7
  Superseded) and produces per-chunk `effective_from` (date or `pending: <event>`), starting with
  tests for every case in report finding 3 (Tech Requirements = issue + 1 year; RMiT 10.31;
  IFTF 4.1 → Appendix II; Merchant Acquiring staggered; Complaints 12.1–12.4; Open Finance
  proposed). Then `corpus/curated/applicability.yaml`, FAQ links (chunks already carry
  `para_refs`), and the out-of-corpus list from section 6.
- **Open questions for Karam:** check the 8 transcriptions in `corpus/curated/figures.yaml`
  against the PDF pages listed there, then fill in its "Checked … by" line.
- **Read for this step:** `docs/02-phase1-plan.md` → "Build steps", step 2, and "The chunk";
  `docs/01-corpus-report.md` findings 3, 7, 8, 9. Run `uv run python -m bnm_rag.parse` first
  (`chunks.jsonl` and `chunks.json` are git-ignored; the parser writes both).

## Steps (Phase 1)

Details and the check for each step: `docs/02-phase1-plan.md` → "Build steps".

- [x] 0. Repo setup
- [x] 1. Parser (PDF → `corpus/chunks.jsonl`)
- [ ] 2. Metadata (Part A, applicability YAML, FAQ links, out-of-corpus list)
- [ ] 3. Golden set (`evals/golden.yaml`, reviewed by Karam)
- [ ] 4. Index (Azure AI Search Free tier; retrieval comparison)
- [ ] 5. Agent (tools, structured reply, citation validation)
- [ ] 6. API + UI locally
- [ ] 7. Deploy to Azure
- [ ] 8. Case-study README

## Log

Newest first. One entry per work session: what was done, decisions, anything surprising.

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
