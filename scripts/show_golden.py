"""Print golden-set questions with their expected paragraphs, for reviewing against the PDFs.

Usage: uv run python scripts/show_golden.py            (all questions)
       uv run python scripts/show_golden.py g13 g18    (just these)

For each question: the question, firm, coverage, must/must-not facts, then each expected
chunk with its PDF page, status on the golden set's as_of date, who it applies to, and text.
Needs corpus/chunks.jsonl (uv run python -m bnm_rag.parse).
"""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import yaml

from bnm_rag.metadata.status import later_parts, status

ROOT = Path(__file__).resolve().parents[1]


def main(wanted: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with open(ROOT / "corpus" / "chunks.jsonl", encoding="utf-8") as f:
        chunks = {c["chunk_id"]: c for c in map(json.loads, f)}
    with open(ROOT / "evals" / "golden.yaml", encoding="utf-8") as f:
        golden = yaml.safe_load(f)
    day = golden["as_of"]
    for q in golden["questions"]:
        if wanted and q["id"] not in wanted:
            continue
        print("=" * 100)
        print(f"{q['id']}  {q['question']}")
        print(f"firm: {q['firm'] or '(not said)'}   coverage: {q['coverage']}   "
              f"reviewed: {q['reviewed']}")
        for fact in q["must_say"]:
            print(textwrap.fill(fact, 96, initial_indent="  + ", subsequent_indent="    "))
        for fact in q["must_not_say"]:
            print(textwrap.fill(fact, 96, initial_indent="  - ", subsequent_indent="    "))
        if q.get("pointer"):
            print(f"  pointer: {q['pointer']}")
        for cid in q["expected"]:
            c = chunks[cid]
            later = "; ".join(f"{e.get('items') or e.get('who')} {e.get('from') or 'until'} "
                              f"{e.get('until') or ''}".strip() for e in later_parts(c, day))
            print(f"\n  [{cid}]  {c['source_url']}#page={c['page_start']}")
            print(f"  status on {day}: {status(c, day)}"
                  f"{'  (later: ' + later + ')' if later else ''}"
                  f"   applies to: {', '.join(c['applies_to'])}")
            if c.get("applies_note"):
                print(textwrap.fill(c["applies_note"], 96, initial_indent="  note: ",
                                    subsequent_indent="        "))
            for line in c["text"].split("\n"):
                print(textwrap.fill(line, 96, initial_indent="    ", subsequent_indent="    "))
        if q["also_ok"]:
            print(f"\n  also ok: {', '.join(q['also_ok'])}")
        print()


if __name__ == "__main__":
    main(sys.argv[1:])
