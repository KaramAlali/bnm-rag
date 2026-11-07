"""Status is computed at answer time, never stored (CLAUDE.md, corpus report finding 3)."""

from __future__ import annotations

import datetime as dt

IN_FORCE, NOT_YET, PROPOSED = "in force", "not yet in force", "proposed"
SUPERSEDED = "superseded"


def _reached(day: str | None, today: dt.date) -> bool:
    if day is None or day.startswith("pending"):
        return False
    return dt.date.fromisoformat(day) <= today


def status(chunk: dict, today: dt.date) -> str | None:
    """'proposed' for an exposure draft, whatever date it states; 'superseded' once another
    document has replaced the paragraph (e-Money PD 27-31 by Tech Requirements); None for FAQs
    and feedback statements, which explain rules rather than set them."""
    if chunk["kind"] == "exposure_draft":
        return PROPOSED
    if chunk["kind"] != "policy_document":
        return None
    if _reached(chunk.get("effective_until"), today):
        return SUPERSEDED
    return IN_FORCE if _reached(chunk["effective_from"], today) else NOT_YET


def later_parts(chunk: dict, today: dt.date) -> list[dict]:
    """Changes still to come for some sub-items or firms, for answers like "(a) and (c) apply
    from 30 September 2027" or "for designated operators, replaced on 12 March 2027"."""
    out = []
    for e in chunk.get("effective_exceptions", []):
        starts_later = e.get("from") is not None and not _reached(e["from"], today)
        ends_later = e.get("until") is not None and not _reached(e["until"], today)
        if starts_later or ends_later:
            out.append(e)
    return out
