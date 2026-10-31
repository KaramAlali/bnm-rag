"""Parse every PDF listed in corpus/sources.csv into corpus/chunks.jsonl and corpus/chunks.json.

The two files hold the same chunks in the same order: one per line (for streaming and the
index), and one indented array (for reading). Both are written from the same run.

Usage: uv run python -m bnm_rag.parse [--verbose]
"""

from __future__ import annotations

import json
import sys
from collections import Counter

from bnm_rag.parse.document import CORPUS, parse_document, sources


def main(argv: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    verbose = "--verbose" in argv
    jsonl, pretty = CORPUS / "chunks.jsonl", CORPUS / "chunks.json"
    total: Counter[str] = Counter()
    every: list[dict] = []
    for src in sources():
        chunks, rejected = parse_document(src)
        ob = Counter(c["obligation"] for c in chunks)
        total.update(ob)
        total["chunks"] += len(chunks)
        print(f"{src['file']:22} {len(chunks):5} chunks  S {ob['S']:4}  G {ob['G']:4}"
              f"  rejected numbers {len(rejected)}")
        if verbose:
            for r in rejected:
                print("    rejected", r)
        every.extend(chunks)
    with open(jsonl, "w", encoding="utf-8", newline="\n") as f:
        for c in every:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(pretty, "w", encoding="utf-8", newline="\n") as f:
        json.dump(every, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"{'total':22} {total['chunks']:5} chunks  S {total['S']:4}  G {total['G']:4}"
          f"  → {jsonl.name}, {pretty.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
