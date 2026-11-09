"""The golden set end to end (plan step 5 check): ask every question as of the golden set's
date, score the replies in code, and have an LLM judge check the facts.

Code scores (no LLM):
  coverage   the reply's coverage equals the expected one (answered / partial / not_covered)
  expected   share of the question's `expected` chunks the reply cites
  drafts     on draft questions, the reply says "proposed" (the validator enforces it too)
  valid      every citation passed the checks (nothing left unresolved after the fixes)
LLM judge (JUDGE_MODEL, default z-ai/glm-5.3; a different model from the answerer where
possible), given the question, the answer and the cited paragraphs' text:
  must_say       each required fact is stated
  must_not_say   each forbidden claim is absent
  faithful       every claim in the answer is supported by the cited paragraphs
The judge is spot-checked by hand; its notes are in the per-question file.

Writes evals/agent_answers.jsonl (every reply, citations, tool calls, judge verdicts) and
evals/agent_results.md. Costs a few US cents per full run.

Usage: uv run python -m bnm_rag.agent.evaluate [g01 g02 ...] [--workers 4] [--no-judge]
Naming questions reruns just those and merges them into the saved replies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import yaml
from pydantic import BaseModel, Field

from bnm_rag.agent.run import REQUEST_TIMEOUT_MS
from bnm_rag.parse.document import ROOT

GOLDEN = ROOT / "evals" / "golden.yaml"
ANSWERS = ROOT / "evals" / "agent_answers.jsonl"
RESULTS = ROOT / "evals" / "agent_results.md"
DEFAULT_JUDGE = "z-ai/glm-5.3"


class FactCheck(BaseModel):
    fact: str
    verdict: bool = Field(description="must_say: the answer states it (in any wording). "
                                      "must_not_say: the answer makes this claim.")
    note: str = Field(description="One short sentence: where or why.")


class Judgement(BaseModel):
    must_say: list[FactCheck] = Field(description="One entry per required fact, in order.")
    must_not_say: list[FactCheck] = Field(description="One entry per forbidden claim, in order.")
    faithful: bool = Field(description="Every factual claim in the answer is supported by the "
                                       "cited paragraphs (or is general framing).")
    unsupported: list[str] = Field(default_factory=list, description=(
        "Claims in the answer that the cited paragraphs do not support."))


JUDGE_PROMPT = """\
You check an answer about Bank Negara Malaysia regulations against a marking scheme and \
against the paragraphs it cites. Be strict but fair: a fact counts as stated if the answer \
says it in other words or with equivalent numbers; a forbidden claim counts only if the answer \
actually makes it (mentioning it in order to deny it does not count).

For faithfulness: the cited paragraphs below include their status, dates, applicability and \
footnotes exactly as the answerer saw them, so claims drawn from those lines are supported. \
When the answer says the documents don't cover something and points elsewhere (another \
document or authority, e.g. the Securities Commission for crypto exchanges), that pointer and \
its brief description are not unsupported claims.

Question: {question}
Answers are judged as of {as_of}.

Required facts (must_say):
{must_say}

Forbidden claims (must_not_say):
{must_not_say}

The answer:
<answer>
{answer}
</answer>

The paragraphs it cites:
<paragraphs>
{paragraphs}
</paragraphs>
"""


def load() -> tuple[str, list[dict]]:
    with open(GOLDEN, encoding="utf-8") as f:
        g = yaml.safe_load(f)
    return str(g["as_of"]), g["questions"]


def judge_model():
    from langchain_openrouter import ChatOpenRouter

    from bnm_rag.index.azure import env

    return ChatOpenRouter(model=os.environ.get("JUDGE_MODEL", DEFAULT_JUDGE),
                          openrouter_api_key=env("OPENROUTER_API_KEY"), temperature=0,
                          max_retries=2, request_timeout=REQUEST_TIMEOUT_MS,
                          app_title="bnm-rag-judge")


def judge(q: dict, ans: dict, as_of: str, model) -> dict:
    bullets = lambda xs: "\n".join(f"- {x}" for x in xs) or "(none)"  # noqa: E731
    paragraphs = "\n\n---\n\n".join(ans["sources"].values()) or "(none cited)"
    prompt = JUDGE_PROMPT.format(question=q["question"], as_of=as_of,
                                 must_say=bullets(q["must_say"]),
                                 must_not_say=bullets(q["must_not_say"]),
                                 answer=ans["answer"], paragraphs=paragraphs)
    # The judge sometimes returns no structured verdict (g12, 2026-11-09); try once more.
    for _ in range(2):
        verdict: Judgement | None = model.with_structured_output(Judgement).invoke(prompt)
        if verdict is not None:
            return verdict.model_dump()
    raise RuntimeError("the judge returned no verdict twice")


def code_scores(q: dict, ans: dict) -> dict:
    cited = [c["chunk_id"] for c in ans["citations"]]
    exp = q["expected"]
    allowed = set(exp) | set(q.get("also_ok") or [])
    return {
        "coverage_ok": ans["coverage"] == q["coverage"],
        "expected_cited": sum(e in cited for e in exp), "expected_n": len(exp),
        "other_citations": [c for c in cited if c not in allowed],
        "draft_ok": ("propos" in ans["answer"].lower()) if "draft" in q["tags"] else None,
        "valid": not ans["unresolved"],
    }


def run_one(q: dict, today, agent, jm) -> dict:
    from bnm_rag.agent.run import ask

    t = time.monotonic()
    try:
        ans = asdict(ask(q["question"], today=today, agent=agent))
    except Exception as e:  # one failure must not sink the run; it is reported
        return {"id": q["id"], "error": f"{type(e).__name__}: {e}"[:500]}
    ans["seconds"] = round(time.monotonic() - t, 1)
    row = {"id": q["id"], **ans, "scores": code_scores(q, ans)}
    if jm is not None:
        try:
            row["judge"] = judge(q, ans, str(today), jm)
        except Exception as e:
            row["judge_error"] = f"{type(e).__name__}: {e}"[:300]
    print(f"{q['id']}: {ans['coverage']:<11} cited {row['scores']['expected_cited']}/"
          f"{row['scores']['expected_n']} expected, {len(ans['tool_calls'])} tool calls, "
          f"{ans['seconds']} s", flush=True)
    return row


def pct(a: float, b: float) -> str:
    return f"{a / b:.0%} ({a:g}/{b:g})" if b else "-"


def report(rows: list[dict], questions: dict[str, dict], as_of: str) -> str:
    ok = [r for r in rows if "error" not in r]
    errors = [r for r in rows if "error" in r]
    judged = [r for r in ok if "judge" in r]
    s = [r["scores"] for r in ok]
    answerable = [r for r in ok if r["scores"]["expected_n"]]
    drafts = [x for x in s if x["draft_ok"] is not None]
    must = [f["verdict"] for r in judged for f in r["judge"]["must_say"]]
    must_not = [f["verdict"] for r in judged for f in r["judge"]["must_not_say"]]
    lines = [
        "# Agent results on the golden set (generated)",
        "",
        f"`uv run python -m bnm_rag.agent.evaluate`, {time.strftime('%Y-%m-%d')}, answers as "
        f"of {as_of}. Models: "
        + ", ".join(f"{m} ({n})" for m, n in Counter(r["model"] for r in ok).most_common())
        + f". Judge: {os.environ.get('JUDGE_MODEL', DEFAULT_JUDGE)}. "
        "Analysis: `docs/04-agent-results.md`.",
        "",
        "| check | result |",
        "|---|---|",
        f"| questions answered without error | {pct(len(ok), len(rows))} |",
        f"| coverage as expected | {pct(sum(x['coverage_ok'] for x in s), len(s))} |",
        f"| expected paragraphs cited (all questions with some) | "
        f"{pct(sum(r['scores']['expected_cited'] for r in answerable), sum(r['scores']['expected_n'] for r in answerable))} |",  # noqa: E501
        f"| questions citing every expected paragraph | "
        f"{pct(sum(r['scores']['expected_cited'] == r['scores']['expected_n'] for r in answerable), len(answerable))} |",  # noqa: E501
        f"| draft questions saying \"proposed\" | {pct(sum(x['draft_ok'] for x in drafts), len(drafts))} |",  # noqa: E501
        f"| replies passing citation checks | {pct(sum(x['valid'] for x in s), len(s))} |",
        f"| replies sent back at least once | {pct(sum(r['fixes'] > 0 for r in ok), len(ok))} |",
        f"| judge: required facts stated | {pct(sum(must), len(must))} |",
        f"| judge: forbidden claims made | {pct(sum(must_not), len(must_not))} |",
        f"| judge: faithful to cited paragraphs | {pct(sum(r['judge']['faithful'] for r in judged), len(judged))} |",  # noqa: E501
        f"| tool calls per question (mean) | {sum(len(r['tool_calls']) for r in ok) / max(len(ok), 1):.1f} |",  # noqa: E501
        f"| seconds per question (mean) | {sum(r['seconds'] for r in ok) / max(len(ok), 1):.0f} |",  # noqa: E501
        "",
        "## Per question",
        "",
        "| id | coverage (expected → got) | expected cited | must say | must not | faithful "
        "| tools | fixes |",
        "|---|---|---|---|---|---|---:|---:|",
    ]
    for r in sorted(rows, key=lambda r: r["id"]):
        q = questions[r["id"]]
        if "error" in r:
            lines.append(f"| {r['id']} | ERROR: {r['error'][:80]} | | | | | | |")
            continue
        sc, j = r["scores"], r.get("judge")
        cov = q["coverage"] if sc["coverage_ok"] else f"**{q['coverage']} → {r['coverage']}**"
        exp = f"{sc['expected_cited']}/{sc['expected_n']}" if sc["expected_n"] else "-"
        if j:
            ms = sum(f["verdict"] for f in j["must_say"])
            must_cell = f"{ms}/{len(j['must_say'])}"
            if ms < len(j["must_say"]):
                must_cell = f"**{must_cell}**"
            mn = sum(f["verdict"] for f in j["must_not_say"])
            mn_cell = f"**{mn}**" if mn else "0"
            faithful = "yes" if j["faithful"] else "**no**"
        else:
            must_cell = mn_cell = faithful = "-"
        lines.append(f"| {r['id']} | {cov} | {exp} | {must_cell} | {mn_cell} | {faithful} "
                     f"| {len(r['tool_calls'])} | {r['fixes']} |")
    if errors:
        lines += ["", f"{len(errors)} question(s) failed with an error (see the table)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    import datetime as dt

    from bnm_rag.agent.run import build_agent

    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m bnm_rag.agent.evaluate")
    p.add_argument("ids", nargs="*")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--no-judge", action="store_true")
    a = p.parse_args()

    as_of, qs = load()
    questions = {q["id"]: q for q in qs}
    chosen = [q for q in qs if not a.ids or q["id"] in a.ids]
    today = dt.date.fromisoformat(as_of)
    agent = build_agent(today)
    jm = None if a.no_judge else judge_model()
    t = time.monotonic()
    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(lambda q: run_one(q, today, agent, jm), chosen))
    if a.ids and ANSWERS.exists():
        # A rerun of some questions replaces just those rows; the report covers all.
        with open(ANSWERS, encoding="utf-8") as f:
            kept = [r for r in map(json.loads, f) if r["id"] not in set(a.ids)]
        rows = kept + rows
    with open(ANSWERS, "w", encoding="utf-8", newline="\n") as f:
        for r in sorted(rows, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    text = report(rows, questions, as_of)
    RESULTS.write_text(text, encoding="utf-8", newline="\n")
    print(text.split("## Per question")[0])
    print(f"{time.monotonic() - t:.0f} s → {ANSWERS.relative_to(ROOT)}, "
          f"{RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
