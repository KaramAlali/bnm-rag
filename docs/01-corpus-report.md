# 01 — Corpus report: Phase 1 (BNM payments and e-money)

Measured on 31 October 2026 from the 20 PDFs in `corpus/raw/`. Every number here can be
re-run with `python scripts/measure_corpus.py` (writes `corpus/measurements.json` and the
extracted text in `corpus/text/`). Sources, reference numbers and dates: `corpus/sources.csv`.

## Summary

- **20 PDFs, 619 pages, about 327k tokens** of text (1.31M characters with whitespace collapsed).
  11 policy documents (10 final + 1 exposure draft), 5 FAQs, 4 feedback statements.
- **All text PDFs, no scans, English only.** Only cover pages are near-empty.
- **One template for every policy document**: Part A sections 1–7 are always Introduction,
  Applicability, Legal provisions, Effective date, Interpretation, Related documents,
  Superseded documents. Metadata can be parsed, not hand-entered.
- **881 S (standard, enforceable) and 229 G (guidance) paragraphs** across 10 of the 11 policy
  documents. The Sandbox framework uses plain numbering with no S/G.
- **Too big for context on every question** (327k tokens ≈ $1 per question at $3/M input, and beyond many models' context windows), and Phase 3 multiplies it. RAG is the right design here, unlike
  Kedai Rumah's three short policies.

## Inventory

| File | Kind | Pages | ~Tokens | S | G | Appendix share |
|---|---|---:|---:|---:|---:|---:|
| rmit_pd | policy | 113 | 66,704 | 111 | 10 | 75% |
| techreq-psr_pd | policy | 76 | 43,753 | 102 | 13 | 59% |
| emoney_pd | policy | 77 | 40,686 | 232 | 69 | 50% |
| merchant-acq_pd | policy | 69 | 30,480 | 119 | 72 | 13% |
| mcipd_pd | policy | 37 | 20,009 | 94 | 17 | 46% |
| ekyc_pd | policy | 30 | 16,734 | 33 | 11 | 46% |
| sandbox_pd | policy | 39 | 14,843 | 0 | 0 | 62% |
| pso_pd | policy | 26 | 13,596 | 69 | 23 | – |
| open-finance_ed | **exposure draft** | 28 | 12,908 | 54 | 5 | 6% |
| iftf_pd | policy | 18 | 9,374 | 32 | 5 | 5% |
| complaints_pd | policy | 15 | 7,160 | 35 | 4 | 9% |
| rmit_faq | FAQ | 25 | 16,957 | – | – | – |
| techreq-psr_faq | FAQ | 24 | 14,116 | – | – | – |
| ekyc_faq | FAQ | 9 | 4,014 | – | – | – |
| sandbox_faq | FAQ | 7 | 3,618 | – | – | – |
| emoney_faq | FAQ | 9 | 3,492 | – | – | – |
| complaints_fs | feedback | 7 | 4,051 | – | – | – |
| emoney_fs | feedback | 4 | 1,722 | – | – | – |
| iftf_fs | feedback | 3 | 1,730 | – | – | – |
| pso_fs | feedback | 3 | 1,187 | – | – | – |
| **Total** | | **619** | **~327k** | **881** | **229** | |

Tokens are characters ÷ 4 with whitespace collapsed (an estimate, not a tokenizer count).
Appendix share is the part of the text after the first appendix heading.

## Findings that shape the design

Each finding ends with the decision it leads to.

1. **Paragraph = chunk.** Policy paragraphs are numbered `8.1`, with `(a)` and `(i)` sub-items,
   and in Part B onwards most start with `S` or `G` (`S 8.1 The board must…`, `G 8.3 The board
   may…`). Part A has no markers; Sandbox has none at all.
   → One chunk per numbered paragraph, sub-items kept with their parent. Field
   `obligation: S | G | none`.

2. **Appendices are most of the text in the big documents** (RMiT 75%, Tech Requirements 59%,
   Sandbox 62%, e-Money 50%). They use their own numbering (RMiT Appendix 12 goes to `19.2.6`)
   and are mostly unmarked.
   → Appendix-aware chunking: keep the appendix number and title in every chunk's header.
   Whether an appendix item is binding comes from the paragraph that points to it; to be checked
   during the build, not assumed.

3. **Effective dates differ inside one document**, and one has to be computed:
   - Tech Requirements: "one (1) year after the date of its issuance" → 12 March 2027.
   - RMiT: 28 November 2025, but some paragraphs (e.g. 10.31) from 30 September 2027.
   - IFTF: some paragraphs start on the "live operationalisation date" of the Nexus scheme, not
     yet announced; others by 30 June 2028 (Appendix II).
   - Merchant Acquiring: 15 March 2022, staggered for non-bank acquirers.
   - Complaints Handling: in force since 1 April 2026; paragraphs 12.1–12.4 since 28 March 2025.
   - **Open Finance is an exposure draft** that says it "comes into effect on 1 January 2027". A
     naive bot would repeat that as a rule. Its feedback closed on 1 March 2026; no final policy
     yet.
   → Per-chunk `effective_from` (a date, or `pending: <event>`) and `kind`. Status
   (`in force` / `not yet in force` / `proposed`) is computed at question time against today's
   date, never stored.

4. **Documents are re-issued in place.** The RMiT file is a 25 September 2026 re-issue under the
   same reference (BNM/RH/PD 028-98) with the 2025 effective date unchanged.
   → Version = reference + issue date + file hash. Re-ingesting replaces that version's chunks.

5. **Tables are few, uncaptioned and decide who a rule applies to.** Only two have a "Table n"
   caption (e-KYC, e-Money). Tech Requirements' tier table (paragraph 2.4) extracts with its
   columns interleaved ("of more TR PD than RM1.5 billion").
   → A handful of applicability tables are parsed with a layout-aware parser or written by hand
   as structured data, and tested.

6. **Footnotes break the text.** Footnote numbers are glued to words (`annual transaction
   value3,4`) and the footnotes sit at the page bottom, often mid-paragraph.
   → Strip markers from the body, attach each footnote to the paragraph that cites it, drop the
   `x of y` page footers but keep page numbers for citations.

7. **RMiT and Tech Requirements are near-duplicates** (same appendices on cloud, cybersecurity,
   mobile apps, fraud detection) but apply to different firms: Tier-1 payment providers follow
   RMiT (plus Tech Requirements paragraph 2.2 only); Tiers 2–4 follow Tech Requirements.
   → `applies_to` metadata per document, and a filter from the user's firm type. Without it,
   retrieval returns both and the answer mixes them.

8. **FAQs point back to paragraphs.** RMiT's FAQ has 42 `[Paragraph x.y]` links, Tech
   Requirements' 39, Sandbox's 9.
   → One chunk per question and answer, with links stored, so retrieving a paragraph can bring
   its FAQ with it.

9. **Many references lead outside the corpus.** Section 6 of each document lists roughly 5–19 related
   documents (AML/CFT, Outsourcing, BCM, BNM's fraud letters); Complaints Handling cites 9 other BNM
   references by number.
   → An "out of corpus" list built from section 6, so the agent can answer "that's in the
   Outsourcing policy document, which isn't indexed yet" instead of guessing.

## Size of the index

About 1,350 numbered paragraphs, plus appendix items and about 170 FAQ questions: roughly
**2,000–3,000 chunks**. Small for Azure AI Search; the cost question is the service tier, not
the index size.

## Out of scope for Phase 1

AML/CFT, the card policy documents, BCM, Outsourcing, discussion papers, application forms and
the MCIPD Excel templates. The Limited Purpose e-Money Exemption Order 2024 is listed on the
e-Money page but not downloaded yet.

## Licensing

These are BNM's documents. The app indexes them, shows short excerpts and always links to the
source PDF; it does not republish them in full.
