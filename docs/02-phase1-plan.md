# 02 — Phase 1 plan: the MVP

**Goal:** a public chat app that answers questions about BNM's payments and e-money rules from
the 20 documents in `corpus/raw/`, cites the exact paragraph (with S/G and page), says whether
each rule is in force today, and says "not covered" instead of guessing. Deployed on Azure.

Read `01-corpus-report.md` first: most decisions below come from its findings.

## Who it's for

The 11 documents cover a payment firm's lifecycle: getting started (Sandbox), licence rules
(e-Money, Payment System Operator, Merchant Acquiring), tech and security (RMiT, Tech
Requirements), customer onboarding (e-KYC), customer data, complaints and transfers between
providers (IFTF).

**Served well**

| User | Example questions |
|---|---|
| Fintech founders starting a payment business | "Can we test our product in BNM's sandbox first? What's the Green Lane?" |
| Compliance and risk teams at e-wallets, payment gateways and remittance firms | "What's the deadline to report a customer data breach?" "Do we need approval to raise our wallet limit to RM5,000?" |
| CTOs, engineers and security teams at those firms | "What does BNM require for our mobile app's security?" "Which tier are we under Tech Requirements, and when must we comply?" |
| Product and onboarding teams | "Can we onboard customers with face verification? What error rate triggers a report to BNM?" |
| Consultants, auditors and lawyers advising payment firms | "Which BNM documents apply to a merchant acquirer?" "What changed in the new RMiT?" |

**Demo persona:** a compliance or tech lead at an e-wallet or payment gateway, the reader these
documents were written for. The golden set and the README examples use this persona.

**Partly served**

- Banks: RMiT, e-KYC, customer information and complaints apply to them, but most bank rules
  (capital, credit, outsourcing, AML) are not in Phase 1.
- Consumers: a few questions work (e-wallet refund times, how complaints must be handled), but
  the documents are written for firms.

**Not served yet** (the app answers "not covered" and names the right document when known)

- Crypto and digital-asset firms: regulated by the Securities Commission, Phase 3.
- Insurers, and questions on AML/CFT, card rules or outsourcing: documents outside the corpus.

**Access in Phase 1**

- Public link, no login. Per-visitor rate limit and a daily LLM spend cap control cost.
- Not legal advice: every answer shows the exact paragraph and links to BNM's PDF.
- Answers in English (the documents are English only). Questions in Malay should work; the
  golden set includes a few to check.

## What "done" means for Phase 1

- Someone opens the public URL, asks "We're an e-wallet with RM800m a year. Which tech rules
  apply and when?", and gets a correct answer with clickable citations to Tech Requirements
  paragraph 2.4 and the effective date 12 March 2027.
- Questions about the Open Finance exposure draft are answered as **proposed**, never as rules.
- Out-of-corpus questions (crypto exchanges, AML/CFT) get "not covered", naming the document
  that would cover it when the corpus knows it.
- A 40-question golden set passes the agreed bar (step 3), run in CI with no LLM calls for the
  retrieval part.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language, tooling | Python 3.12, `uv`, `ruff`, `pytest` | Same as Aina and Kedai Rumah |
| PDF parsing | PyMuPDF (`pymupdf`) | Text spans with font size, so footnote markers (superscripts) can be told apart from body digits. AGPL: fine for a public repo |
| Applicability tables | Hand-written YAML in `corpus/curated/`, with tests | Only a few tables matter and extraction mixes their columns (report finding 5) |
| Index | **Azure AI Search**, hybrid (BM25 + vector) | The Azure skill the job market asks for; built-in hybrid ranking |
| Embeddings | Azure OpenAI `text-embedding-3-small` (check region/deployment availability in step 4) | ~330k tokens to embed once, a few cents |
| Agent | LangChain 1.x `create_agent`, a few tools, structured reply | Same pattern as Kedai Rumah, multi-search for cross-document questions |
| LLM | OpenRouter model chain with fallback, as in Aina | Already working; Azure OpenAI chat can be swapped in later |
| API | FastAPI, `POST /chat` with server-sent progress events | Known stack |
| UI | React + Vite + TypeScript + Tailwind, built into the API image | One container to deploy |
| Tracing | LangSmith | Already used |
| Hosting | Azure Container Apps (scale to zero), Azure Container Registry, Key Vault, managed identity | Cheapest Azure way to run a container |
| Infra as code, CI/CD | Bicep in `infra/`, GitHub Actions with OIDC (no stored Azure secrets) | Repeatable deploys, a CS365-style pipeline |

**No database in Phase 1.** The chat is stateless (the browser sends the last few turns), and
feedback goes to LangSmith. Postgres comes in Phase 2 only if saved conversations or accounts
are needed. This keeps the monthly bill near zero.

**Region: Southeast Asia (Singapore) for everything.** Azure AI Search exists in Malaysia West
but its region table shows no semantic ranker there; Southeast Asia has it, for when we turn it
on.

## Monthly cost (Azure list prices, checked 31 Oct 2026)

| Item | MVP | With semantic ranker |
|---|---|---|
| AI Search | Free tier: $0 (50 MB; the ~2,000–3,000-chunk index should fit, check in step 4) | Basic: ~$74 per search unit; ranker free up to 1,000 queries/month |
| Container Apps | ~$0 (180k vCPU-s, 360k GiB-s and 2M requests free per month) | same |
| Container Registry (Basic) | ~$5 | same |
| Key Vault, logs | < $2 with a daily log cap | same |
| Embeddings | cents, once per re-index | same |
| LLM (OpenRouter) | a few dollars at demo traffic | same |
| **Total** | **~$5–15** | **~$80–90** |

The Free search tier has no SLA and no semantic ranker; it is for the MVP, not production. A new
Azure account also gets a 30-day $200 credit.

## The chunk (one record per paragraph)

```
doc_id, version (reference + issue date + file hash), kind (policy_document | faq |
feedback_statement | exposure_draft), reference, title,
part, section, para_no ("8.1", "Appendix 5 / 3.2"), heading_path,
obligation (S | G | none), text, footnotes[],
page_start, page_end, source_url,
effective_from (date | "pending: <event>"), applies_to [entity types],
faq_links [para_no], related_docs [titles]
```

**Status is never stored.** `in force` / `not yet in force` / `proposed` is computed from
`kind` and `effective_from` against today's date when a question is answered.

## Agent tools

- `search_regulations(query, entity_type?, doc_ids?, include_drafts=false)`: hybrid search,
  returns paragraphs with metadata and computed status.
- `get_paragraph(doc_id, para_no)`: the exact paragraph, its footnotes and linked FAQ answers.
- `list_documents()`: the corpus, with references, dates and kinds, plus the out-of-corpus list.

**Reply schema:** `answer`, `citations[] {doc_id, para_no, page, obligation, status}`,
`coverage: answered | partial | not_covered`, `not_covered_pointer?` (the document that would
cover it). Every citation must appear in that run's tool results, or the reply is sent back to
the model (the Aina/Kedai Rumah validation pattern).

## Build steps (in order; each ends with a check)

0. **Repo setup.** `git init`, `uv`, ruff, pytest, `.env.example`, `.gitignore` (keep
   `corpus/raw/*.pdf` out of git; `corpus/sources.csv` lists where to get them), GitHub repo.
   *Check:* `uv run pytest` passes on an empty suite.
1. **Parser.** PDF → `corpus/chunks.jsonl`: paragraphs with sub-items, S/G, appendix headers,
   footnotes moved out of the body, page numbers. *Check:* fixture tests on known paragraphs
   (e.g. RMiT S 8.1, e-KYC Appendix 2 Table 1, the "value3,4" footnote case); S/G counts match
   `corpus/measurements.json` (881/229) within a stated tolerance.
2. **Metadata.** Part A parser (effective dates and exceptions, superseded and related docs),
   merge with `sources.csv`, curated `applicability.yaml` (the Tech Requirements tiers, IFTF
   Table 1), FAQ → paragraph links, the out-of-corpus list. *Check:* tests for every effective-date
   case in report finding 3.
3. **Golden set, before retrieval.** ~40 questions in `evals/golden.yaml`: question, expected
   documents/paragraphs, must-say and must-not-say facts, expected coverage. Includes the
   draft trap, the RMiT-vs-Tech-Requirements split, threshold questions and out-of-corpus ones.
   Every expected answer checked against the PDF by a person. *Check:* reviewed by Karam.
4. **Index.** Create the Azure AI Search index (Free tier), embed and upload. Compare keyword,
   vector and hybrid on the golden set (recall@5 of expected paragraphs). *Check:* index size
   under the Free limit; recall numbers recorded in `docs/03-retrieval-results.md`.
5. **Agent.** Tools, structured reply, citation validation, status computation, a CLI
   (`uv run python -m bnm_rag.ask "…"`). *Check:* golden set end to end, code-scored (right
   coverage, cited paragraphs, no draft quoted as a rule), plus an LLM judge on faithfulness,
   spot-checked by hand.
6. **API + UI locally.** FastAPI + React, citation chips opening the paragraph and the PDF
   page link. `docker compose up` runs it all. *Check:* the four "done" questions above work in
   the browser.
7. **Deploy to Azure.** Bicep for the resource group, ACR, Container Apps environment and app,
   Key Vault, managed identity; GitHub Actions builds, pushes and deploys on merge to `main`.
   Per-IP rate limit and a daily LLM spend cap before the URL goes public. *Check:* smoke test
   against the public URL in the pipeline.
8. **Case-study README.** Problem, architecture diagram, trade-offs, eval results, cost.

## Not in Phase 1

Postgres, accounts, saved chats, the semantic ranker, the wider BNM corpus, SC documents,
MCP, scheduled re-ingestion. These are Phases 2–5 (see the project's phase table).
