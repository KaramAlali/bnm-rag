"""Ask the agent one question from the command line.

Usage: uv run python -m bnm_rag.ask "Which tech rules apply to an e-wallet?" [--date 2026-11-07]
       [--verbose]   (also print every tool call)
Needs the Azure and OpenRouter values in .env. Not legal advice.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import textwrap

from bnm_rag.agent.run import ask


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m bnm_rag.ask")
    p.add_argument("question")
    p.add_argument("--date", type=dt.date.fromisoformat, default=None,
                   help="judge status on this date (default: today)")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    ans = ask(a.question, today=a.date)
    if a.verbose:
        for name, args in ans.tool_calls:
            print(f"  → {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
        print()
    print(ans.answer)
    print(f"\ncoverage: {ans.coverage}" + (f" | see: {ans.pointer}" if ans.pointer else ""))
    for c in ans.citations:
        ob = f" {c['obligation']}" if c["obligation"] in ("S", "G") else ""
        print(textwrap.shorten(
            f"  [{c['chunk_id']}]{ob} p.{c['page']} — {c['status'] or c['kind']} — {c['url']}",
            200))
    print(f"\nmodel: {ans.model} | tool calls: {len(ans.tool_calls)} | fixes: {ans.fixes}")
    if ans.unresolved:
        print("UNRESOLVED:", *ans.unresolved, sep="\n  ")
    print("Not legal advice: check the cited paragraphs.")


if __name__ == "__main__":
    main()
