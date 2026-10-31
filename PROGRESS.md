# PROGRESS

## Now

- **Current step:** 1 — Parser (PDF → `corpus/chunks.jsonl`)
- **Next action:** add PyMuPDF (`uv add pymupdf`), then write fixture tests first for the
  known paragraphs (RMiT S 8.1, e-KYC Appendix 2 Table 1, the "value3,4" footnote case) and
  build the parser in `src/bnm_rag/` until they pass; then compare S/G counts with
  `corpus/measurements.json` (881/229).
- **Open questions for Karam:** none
- **Read for this step:** `docs/02-phase1-plan.md` → "Build steps", step 1, and
  `docs/01-corpus-report.md`.

## Steps (Phase 1)

Details and the check for each step: `docs/02-phase1-plan.md` → "Build steps".

- [x] 0. Repo setup
- [ ] 1. Parser (PDF → `corpus/chunks.jsonl`)
- [ ] 2. Metadata (Part A, applicability YAML, FAQ links, out-of-corpus list)
- [ ] 3. Golden set (`evals/golden.yaml`, reviewed by Karam)
- [ ] 4. Index (Azure AI Search Free tier; retrieval comparison)
- [ ] 5. Agent (tools, structured reply, citation validation)
- [ ] 6. API + UI locally
- [ ] 7. Deploy to Azure
- [ ] 8. Case-study README

## Log

Newest first. One entry per work session: what was done, decisions, anything surprising.

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
