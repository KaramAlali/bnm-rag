# bnm-rag

A chat assistant that answers questions about Bank Negara Malaysia's payments and e-money
rules from their official policy documents, with paragraph-level citations. Not legal advice.

Work in progress. Plan: [`docs/02-phase1-plan.md`](docs/02-phase1-plan.md); status: [`PROGRESS.md`](PROGRESS.md).

## Setup

```bash
uv sync
powershell -ExecutionPolicy Bypass -File scripts/download_corpus.ps1   # BNM PDFs → corpus/raw/
cp .env.example .env                                                    # then fill in keys
uv run ruff check
uv run pytest
```

The source PDFs are not in this repo; `corpus/sources.csv` lists each one's official BNM URL.
