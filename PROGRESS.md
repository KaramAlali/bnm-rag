# PROGRESS

## Now

- **Current step:** 0 — Repo setup (committed locally; check passes)
- **Next action:** create the GitHub repo when Karam says so
  (`gh repo create bnm-rag --public --source . --push`), then tick step 0. Step 1 (parser)
  can start meanwhile; it doesn't need the remote.
- **Open questions for Karam:** when to create the public repo `KaramAlali/bnm-rag`.
- **Read for this step:** nothing more. For step 1: `docs/02-phase1-plan.md` → "Build steps",
  step 1, and `docs/01-corpus-report.md`.

## Steps (Phase 1)

Details and the check for each step: `docs/02-phase1-plan.md` → "Build steps".

- [ ] 0. Repo setup
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
