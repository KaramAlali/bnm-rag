"""The agent's structured reply, the checks a reply must pass before it is shown, and the
citations as the user sees them (page, S/G, status, PDF link), filled in from the retrieved
chunks rather than from the model.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Literal

from pydantic import BaseModel, Field

from bnm_rag.metadata.status import status

INLINE = re.compile(r"\[([a-z0-9_-]+:[^\]\n]+)\]")


class Reply(BaseModel):
    """The final answer to the user's question."""

    answer: str = Field(description=(
        "The answer in English, in plain Markdown. Put the chunk_id in square brackets right "
        "after each claim it supports, e.g. 'Tier-2 ... [techreq-psr_pd:2.4]'. Say whether each "
        "rule is in force, not yet in force, superseded or proposed, and who it applies to."))
    citations: list[str] = Field(description=(
        "Every chunk_id the answer relies on, exactly as shown in [brackets] in this "
        "conversation's tool results, one per entry, with no footnote or sub-item added. "
        "Never cite anything you did not retrieve."))
    coverage: Literal["answered", "partial", "not_covered"] = Field(description=(
        "answered: the indexed documents answer it; partial: they answer part of it; "
        "not_covered: they don't (say so instead of guessing)."))
    not_covered_pointer: str | None = Field(default=None, description=(
        "For partial or not_covered: the document or authority that would cover it, if known "
        "(e.g. from list_documents' not-indexed list)."))


def cited_ids(reply: Reply, retrieved: dict[str, dict] | None = None) -> list[str]:
    """The citations list plus any inline [chunk_id] the list forgot, in order, deduplicated.
    Models sometimes add a footnote or sub-item ("techreq-psr_pd:2.4, footnote 4",
    "techreq-psr_pd:2.6(b)") or join two ids with ";"; with `retrieved` given, such a citation
    counts as the retrieved paragraph it names. Anything else is kept as written (and fails
    the check)."""
    raw = [*reply.citations, *INLINE.findall(reply.answer)]
    out: list[str] = []
    for item in raw:
        for part in item.split(";"):
            cid = _resolve(part.strip().strip("[]").strip(), retrieved)
            if cid and cid not in out:
                out.append(cid)
    return out


SUFFIX = re.compile(r"(?:,\s*footnotes?\s*\d+.*|\s*\((?:[a-z]|[ivx]+|\d+)\))$", re.I)


def _resolve(cid: str, retrieved: dict[str, dict] | None) -> str:
    if retrieved is None or cid in retrieved:
        return cid
    base = cid
    while (shorter := SUFFIX.sub("", base)) != base:
        base = shorter.strip()
        if base in retrieved:
            return base
    return cid


def problems(reply: Reply, retrieved: dict[str, dict]) -> list[str]:
    """Why a reply can't be shown yet ([] if it can). Sent back to the model to fix."""
    out = []
    ids = cited_ids(reply, retrieved)
    unknown = [c for c in ids if c not in retrieved]
    if unknown:
        out.append(f"These citations are not in this conversation's tool results: {unknown}. "
                   "Cite only chunk_ids shown in [brackets] in tool results; retrieve a "
                   "paragraph first (search_regulations or get_paragraph) if you need it.")
    if reply.coverage != "not_covered" and not ids:
        out.append("An answered or partial reply must cite the paragraphs it relies on.")
    drafts = [c for c in ids if c in retrieved and retrieved[c]["kind"] == "exposure_draft"]
    if drafts and "propos" not in reply.answer.lower():
        out.append(f"{drafts} come from an exposure draft. Say clearly that it is a proposal, "
                   "not a rule in force, even where the draft states an effective date.")
    return out


def citation(chunk: dict, today: dt.date) -> dict:
    """A citation as shown to the user, from the retrieved chunk (never from the model)."""
    url = chunk["source_url"]
    if chunk.get("page_start"):
        url += f"#page={chunk['page_start']}"
    return {
        "chunk_id": chunk["chunk_id"], "doc_id": chunk["doc_id"], "para_no": chunk["para_no"],
        "title": chunk["title"], "reference": chunk.get("reference"),
        "page": chunk.get("page_start"), "obligation": chunk.get("obligation"),
        "kind": chunk["kind"], "status": status(chunk, today), "url": url,
        "text": chunk["text"],
    }
