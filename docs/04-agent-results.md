# 04 — Agent results (step 5)

**Question:** asked as a user would ask them, does the agent answer the golden set's 44
questions correctly, citing the right paragraphs, with each rule's status, and saying "not
covered" or "proposed" where it should?

**Set-up (run 2026-11-09):**
- **Agent:** LangChain 1.4 `create_agent`, judged as of the golden set's date (7 November 2026).
  It has four tools:
  - `search_regulations` (hybrid search, drafts excluded unless asked for);
  - `get_paragraph` (full text plus linked FAQ answers);
  - `get_document_frame` (a document's Applicability, Effective date and Superseded
    paragraphs);
  - `list_documents` (the corpus plus the documents it cites that aren't indexed).
- **Reply:** a structured `Reply` (answer, citations, coverage, pointer), checked in code
  before it's shown:
  - every citation was returned by a tool in this run;
  - an answered reply cites something;
  - a draft is called a proposal.
  A failing reply is sent back to the model, up to twice.
- **Models:** `deepseek/deepseek-v4.1-flash-1017` (it answered every question), with
  `z-ai/glm-5.3` as the fallback. The judge is `z-ai/glm-5.3`.

Re-run with `uv run python -m bnm_rag.agent.evaluate`, which takes about 30 minutes with 4
workers and costs a few cents. Naming questions reruns just those. Per-question results are in
[`evals/agent_results.md`](../evals/agent_results.md). The raw replies are in
`evals/agent_answers.jsonl`, which is git-ignored because it holds the cited paragraphs' full
text.

## Results

| check | result |
|---|---|
| questions answered without error | 39 / 44 (89%) |
| coverage as expected | 34 / 39 (87%) |
| expected paragraphs cited | 68 / 73 (93%) |
| questions citing every expected paragraph | 31 / 36 (86%) |
| draft questions answered as "proposed" | 3 / 3 |
| replies passing the citation checks | 39 / 39 (2 after being sent back once) |
| judge: required facts stated | 80 / 84 (95%) |
| judge: forbidden claims made | 2 / 25 (g12, g27) |
| judge: faithful to the cited paragraphs | 32 / 39 (82%) |
| tool calls per question | 11 on average (4 to 31) |
| time per question | 34 s on average |

**Compared with step 4:** a single raw search put 51% of the expected paragraphs in the top 5.
The agent cites 93% of them, because it rewrites questions in regulatory terms, searches
several times and fetches each document's frame paragraphs. g01, the question every single
search got wrong, now cites all three expected paragraphs and states all four required facts.

## Spot-check of everything the judge or the code flagged

I read the 14 flagged answers against the cited paragraphs.

**Real errors (5):**
- **g12 "What changed in the new RMiT?":** it gives a detailed change list and says
  `answered`. Only the current RMiT is indexed, so it should say a full comparison isn't
  possible (`partial`). This is the only real coverage error.
- **g27 (eligible EMI: RMiT or Tech Requirements?):** it says TR Appendix 10 applies to an
  eligible EMI. Appendix 10 applies only to merchant acquiring business.
- **g13 (stand-in processing deadline):** the main answer is right. A closing aside says a firm
  above the RM1.5bn / 7m thresholds "moves to Tier-1". Above those thresholds is Tier-2;
  Tier-1 means meeting the RMiT criteria.
- **g34 (does a standard EMI have to join the shared payment infrastructure?):** the answer
  ("no", citing IFTF 9.2 and footnote 16) is right. A side claim that a standard EMI isn't a
  "financial institution" under IFTF 5.2 is wrong: the definition includes approved issuers of
  a designated payment instrument.
- **g18 (complaint resolution time):** it misses that only Complaints 12.1–12.4 bind a standard
  EMI, with the rest encouraged as best practice. It also claims, without support, that the
  e-Money PD requires Ombudsman for Financial Services membership.

**Small overreach (3):**
- **g14:** it works out the first track-record quarter and due date, which the paragraphs don't
  state.
- **g44:** it describes PSO 18.2–18.3 without citing them.
- **g08:** it leaves out one example the golden set lists (rooted or jailbroken devices).

**The judge is too strict (1):** g21, for naming the part of the document a paragraph sits in.
Some of the judge's notes in g12 and g44 object to issue dates the agent read from
`list_documents`. Chunks shown to the model and the judge don't carry the issue date yet.

**Coverage labels the agent defends (4):** g11, g33 and g35 say `partial` instead of
`answered`, and g04 says `partial` instead of `not_covered`. In each one the agent answers from
the corpus and names the un-indexed documents that also apply (AML/CFT, Outsourcing, the
insurance product rules). For "which documents apply to a merchant acquirer?" (g11), `partial`
is arguably more accurate than the golden label. **Decision for Karam:** accept `partial` for
these, or keep the labels strict.

**Faithfulness after the spot-check:** 33 of 39 answers have no unsupported claim (g21 cleared).
4 have one wrong side claim (g13, g18, g34, g27), and 2 overreach a little (g14, g44).

## The 5 errors

g06, g10, g26, g28 and g37 ended without the structured reply: the model stopped with plain text
and never called the `Reply` tool. There are two fixes:
- `ask()` now sends that case back with "give your final answer by calling the Reply tool", like
  any other failed check.
- Model calls now time out after 120 s. Before, a call had no timeout, and one stalled call
  held g16 for 405 s.

**Neither fix has been checked against these five questions yet.** At Karam's call there was no
rerun on 2026-11-09.

## Pass bar and fixes since this run

The pass bar, agreed 2026-11-09, is in `docs/02-phase1-plan.md` (step 5). This run meets the
quality targets but fails two hard rules: the forbidden claims in g12 and g27, and the 5
crashes.

Fixes made after the run. None is measured yet, since Karam chose no full rerun:
- **g27:** the agent read TR 2.2 ("2.7, 13.3 and Appendix 10") literally. The narrowing to
  merchant acquirers is in 2.6(d), footnote 7 and FAQ Q3, none of them linked to 2.2. 2.2 now
  carries a curated applicability note saying so (`corpus/curated/applicability.yaml`). This
  is a data gap, not prompt tuning.
- **g12:** a general prompt rule: only the current version of each document is indexed, so a
  "what changed" question gets a partial answer limited to what the documents themselves say.
- **g13 and g14 type overreach:** a prompt rule against stating dates, deadlines or sums the
  paragraphs don't give.
- **Issue date:** each chunk shown to the model, and to the judge, now carries its document's
  issue date.
- **Crashes:** the no-`Reply` crash is sent back, and model calls time out after 120 s.

**Still to try:** GLM-5.3 as the answerer (DeepSeek answered every question here).

## Targeted rerun and verdict (2026-11-09)

Karam asked for a rerun of only the 7 questions the fixes target (g06, g10, g12, g26, g27, g28,
g37), merged into the full run's results:
- **The 5 former crashes** now all answer and cite every expected paragraph. g37 says `partial`,
  as the golden set expects.
- **g27:** "Appendix 10 applies only if you conduct merchant acquiring business [2.6]". No
  forbidden claim.
- **g12:** "only the current RMiT is indexed, so a clause-by-clause comparison isn't possible",
  with coverage `partial`. The judge call failed because the OpenRouter credits had run out, so
  g12 was **checked by hand**:
  - both required facts are stated;
  - its change list matches the RMiT FAQ's own revision history (v4.0 items i–iii) and is
    attributed to it, so it isn't invented;
  - it is faithful.
  The golden's `must_not_say` for g12 ("a detailed list of changes presented as coming from
  the documents") was written before anyone noticed the FAQ's revision history. Karam may want
  to reword it ("…not drawn from the indexed documents").
- **New flag:** g28 describes RMiT Appendix 10's topics beyond the one Appendix 10 paragraph it
  cites. This is small overreach, of the same kind as g44.

Merged results (`evals/agent_results.md`), against the pass bar:

| | bar | result |
|---|---|---|
| Hard rule: no draft presented as a rule | every question | ✅ 3/3 |
| Hard rule: citations only from tool results | every question | ✅ 44/44 |
| Hard rule: no `must_not_say` claim | every question | ✅ 0/28 |
| Hard rule: no invented out-of-corpus answer | every question | ✅ (g03, g36 not covered; g04 partial with the right pointer) |
| Hard rule: no crashes | every question | ✅ 44/44 |
| Expected paragraphs cited | ≥ 90% | ✅ 95% (83/87) |
| `must_say` facts stated | ≥ 90% | ✅ 98% (99/101) |
| Faithful to cited paragraphs | ≥ 85% | ✅ 86% (38/44): the judge's 37/44, plus g21 cleared by hand |
| Coverage label right | ≥ 85% | ✅ 91% (40/44) |

**Step 5 passes.** Remaining unfaithful answers: g13, g14, g18, g34 (wrong side claims) and
g28, g44 (small overreach). The new prompt rule against unstated inferences targets g13 and
g14, but those weren't rerun.
