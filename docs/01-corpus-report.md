# 01 — Corpus report: Phase 1 (BNM payments and e-money)

Measured on 31 October 2026 from the 20 PDFs in `corpus/raw/`. Every number here can be
re-run with `python scripts/measure_corpus.py` (writes `corpus/measurements.json` and the
extracted text in `corpus/text/`). Sources, reference numbers and dates: `corpus/sources.csv`.

## Summary

- **20 PDFs, 619 pages, about 327k tokens** of text (1.31M characters with whitespace collapsed).
  11 policy documents (10 final + 1 exposure draft), 5 FAQs, 4 feedback statements.
- **All text PDFs, no scans, English only.** Only cover pages are near-empty. But 7 figures
  are pictures with no text layer, 4 of them real content (finding 11).
- **One template for every policy document**: Part A sections 1–7 are always Introduction,
  Applicability, Legal provisions, Effective date, Interpretation, Related documents,
  Superseded documents. Metadata can be parsed, not hand-entered.
- **886 S (standard, enforceable) and 229 G (guidance) paragraphs** across 10 of the 11 policy
  documents. The Sandbox framework uses plain numbering with no S/G. (`measure_corpus.py` says
  881: its regex misses 5 paragraphs; see finding 10.)
- **Too big for context on every question** (327k tokens ≈ $1 per question at $3/M input, and beyond many models' context windows), and Phase 3 multiplies it. RAG is the right design here, unlike
  Kedai Rumah's three short policies.

## Inventory

| File | Kind | Pages | ~Tokens | S | G | Appendix share |
|---|---|---:|---:|---:|---:|---:|
| rmit_pd | policy | 113 | 66,704 | 111 | 10 | 75% |
| techreq-psr_pd | policy | 76 | 43,753 | 102 | 13 | 59% |
| emoney_pd | policy | 77 | 40,686 | 232 | 69 | 50% |
| merchant-acq_pd | policy | 69 | 30,480 | 120 | 72 | 13% |
| mcipd_pd | policy | 37 | 20,009 | 98 | 17 | 46% |
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
| **Total** | | **619** | **~327k** | **886** | **229** | |

Tokens are characters ÷ 4 with whitespace collapsed (an estimate, not a tokenizer count).
Appendix share is the part of the text after the first appendix heading. S/G counts are the
parser's (step 1), checked against the measurement script paragraph by paragraph.

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
   - Found in step 2: RMiT 10.35(e) starts 15 October 2027; RMiT **Appendix 12** (the NCII Code
     of Practice) "comes into effect upon endorsement by the CE of NACSA", so it is pending
     (its 2.2 keeps main-body requirements on the main body's date); IFTF Appendix II gives
     9.3, 9.4, 9.8, 9.11 the Nexus date and 9.7(b), 9.12(b) 30 June 2028; Open Finance staggers
     paragraph 8.4 by firm size (2027, 2028, 2029) and 8.6 from 2028.
   - Found in step 3: Tech Requirements 7.1 supersedes the technology sections of other
     documents: e-Money PD 27-31, Merchant Acquiring 17-21 (7.1 says "17 to 22", but 22 holds
     no IT requirements) and PSO 18-19 (for operators of designated payment systems only,
     since 2.3 excludes other operators). Read as taking effect on 12 March 2027, so until
     then an e-wallet's tech rules are e-Money PD 27-31. Chunks get `effective_until`; status
     becomes `superseded`.
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
   Step 2 result: 136 references, 46 distinct documents outside the corpus
   (`corpus/related_docs.json`). The same document appears under several names ("Dear CEOs
   Letter on…", "Notification on…", "Specifications on…"; AML/CFT was renamed), so names are
   normalised before grouping. RMiT 7.1 superseded the 2022 e-banking fraud letters and the
   Fraud Detection Standard; IFTF and Open Finance still cite them, so those references point to
   `rmit_pd`. Not in any section 6: the Securities Commission (crypto), which the agent will need
   as a hand-written pointer in step 5.

10. **Layout quirks found while parsing (step 1).** Each one is handled in `src/bnm_rag/parse/`
    and has a test.
    - S/G markers are often separate text blocks beside the number (Complaints, MCIPD,
      e-Money), so lines are rebuilt from position, not from the PDF's block order.
    - Merchant Acquiring 14.6 has three "S" glyphs stacked on one spot; MCIPD 8.1–8.4 have
      seven spaces after "S". Both fooled the measurement regex (881 → really 886 S).
    - Running headers and footers sit at different heights per document; they are found as
      text repeated across pages, not by a fixed margin.
    - Footnote markers are superscript or smaller-font digits; footnote text is 9–10 pt at the
      page bottom. One e-KYC table caption is 10 pt too, so only lines directly above the first
      footnote count as a carried-over footnote.
    - Ruled tables (Tech Requirements 2.4, e-KYC Table 1, MCIPD's disclosure table) come out one
      line per row, cells joined with " | ". Table detection only runs on pages with a grid of
      rulings (it is slow, and no table was missed by that filter).
    - The e-KYC FAQ and the Complaints feedback statement are one big table (the latter on
      pages rotated 90°); they are split by fixed column positions, one chunk per row.
    - Numbering restarts: RMiT/Tech Requirements Appendix 2 (Cash SST, then Non-Cash SST) and
      the e-Money FAQ (Part A, then Part B). The sub-heading or part goes into `para_no`.
    - Interpretation paragraphs (5.2) are long: 4.5k–10k characters of definitions (median
      chunk: ~320). Fine for embedding limits; revisit if retrieval suffers (step 4). MCIPD's
      15.6k-character 13.2 turned out to be a broken table (finding 11).

11. **Figures the parser cannot read (found after step 1, fixed in step 1).** A check of every
    page line against `chunks.jsonl` found body text lost only in figures and a few headings.
    Fixes: the 8 figures are transcribed by hand in `corpus/curated/figures.yaml` (chunks
    carrying one have `figure: true`); stacked headings are kept (`heading_path` gets the
    group heading too) and wrapped ones joined (gap under 4 pt); appendices keep a section
    level; the Open Finance preface is chunk `preface` (officers' names and emails left out);
    MCIPD's table is one chunk per item (`13.2 / item 1` … `item 8`, named after the
    paragraph it is printed in; the S in 13.1 is what makes the conditions binding). What was
    found:
    - **Pictures, no text layer** (invisible to PyMuPDF text extraction):
      - Sandbox PD Appendix I (application and assessment flowchart, outcomes table, p26),
        Appendix III (prototype development, p32) and Appendix IV (Green Lane operational
        mechanism: 12 months, 20,000 customers, safeguards, p33);
      - Sandbox FAQ Q1 (the whole answer is an eligibility table: which entities can use the
        Standard Sandbox vs Green Lane, p2);
      - Complaints Handling Appendix I (sample complaints flowchart, p14);
      - RMiT FAQ p22 and Tech Requirements FAQ p23 (cloud key-management patterns,
        illustrative, explained by the text around them).
    - **Vector diagram:** Open Finance Diagram 1 (p4) has real text, but its boxes come out
      interleaved across columns and the bold labels were taken as headings and dropped.
    - **Headings dropped:** a bold heading directly followed by another heading is overwritten,
      e.g. RMiT Appendix 12 section titles (p84–107), so they are missing from `heading_path`.
    - **Front matter skipped by design:** cover-page "Applicable to" lists (step 2 reads
      section 2 Applicability instead) and the Open Finance preface on p3 ("proposed",
      feedback deadline), which should become an intro chunk.
    - **MCIPD 13.2** was one 15.6k-character chunk: the note in 13.2 plus the 8-item,
      3-column table printed after it, which 13.1 and 13.2 both call "the table below", over pages 21–31. Rows continuing
      on a new page lose their ruling, so cells came out one word-column per line or split
      mid-row.
    - Still not indexed, on purpose: cover pages (title, "Applicable to" lists, issue date),
      tables of contents, and the field labels of blank application forms (Sandbox
      Appendices II and V, MCIPD Appendices II–V).
    - Also fixed: an unmapped glyph standing alone is a bullet ("•"), not an apostrophe.

## Size of the index

The parser gives **2,157 chunks** (1,115 S/G paragraphs, the rest unmarked paragraphs, appendix
items, ~200 FAQ answers and feedback rows, 8 with figure transcriptions). Small for Azure AI Search; the cost question is
the service tier, not the index size.

## Out of scope for Phase 1

AML/CFT, the card policy documents, BCM, Outsourcing, discussion papers, application forms and
the MCIPD Excel templates. The Limited Purpose e-Money Exemption Order 2024 is listed on the
e-Money page but not downloaded yet.

## Licensing

These are BNM's documents. The app indexes them, shows short excerpts and always links to the
source PDF; it does not republish them in full.
