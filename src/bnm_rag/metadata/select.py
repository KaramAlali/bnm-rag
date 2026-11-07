"""Paragraph selectors used by the curated YAML files.

"all", "Part A", "Appendix 10", "12.3-12.9" (a range), "16" (16 and every 16.x), "9.3".
Numbered selectors only match main-body chunks: appendices restart their own numbering.
"""

from __future__ import annotations


def para_key(para_no: str | None) -> tuple[int, ...] | None:
    """ "13.2 / item 8" → (13, 2); "Q4", "preface", "Appendix 1 / 3" → None."""
    if not para_no:
        return None
    head = para_no.split(" / ")[0].strip()
    try:
        return tuple(int(p) for p in head.split("."))
    except ValueError:
        return None


def matches(chunk: dict, selector: str) -> bool:
    if selector == "all":
        return True
    if selector.startswith("Part "):
        part = (chunk.get("part") or "").upper()
        return part.startswith(selector.upper() + " ")
    if selector.startswith("Appendix "):
        return chunk.get("appendix") == selector
    if chunk.get("appendix"):
        return False
    key = para_key(chunk.get("para_no"))
    if key is None:
        return False
    if "-" in selector:
        lo, hi = (para_key(s) for s in selector.split("-"))
        if lo is None or hi is None:
            raise ValueError(f"bad range selector {selector!r}")
        return lo <= key[: len(hi)] and key[: len(lo)] <= hi
    want = para_key(selector)
    if want is None:
        raise ValueError(f"bad selector {selector!r}")
    return key[: len(want)] == want


def matches_any(chunk: dict, selectors: list[str], exclude: list[str] | None = None) -> bool:
    if exclude and any(matches(chunk, s) for s in exclude):
        return False
    return any(matches(chunk, s) for s in selectors)
