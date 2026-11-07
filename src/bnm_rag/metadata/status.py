"""Status is computed at answer time, never stored (CLAUDE.md, corpus report finding 3)."""

from __future__ import annotations

import datetime as dt

IN_FORCE, NOT_YET, PROPOSED = "in force", "not yet in force", "proposed"


def _started(start: str | None, today: dt.date) -> bool:
    if start is None or start.startswith("pending"):
        return False
    return dt.date.fromisoformat(start) <= today


def status(chunk: dict, today: dt.date) -> str | None:
    """'proposed' for an exposure draft, whatever date it states; None for FAQs and feedback
    statements, which explain rules rather than set them."""
    if chunk["kind"] == "exposure_draft":
        return PROPOSED
    if chunk["kind"] != "policy_document":
        return None
    return IN_FORCE if _started(chunk["effective_from"], today) else NOT_YET


def later_parts(chunk: dict, today: dt.date) -> list[dict]:
    """Sub-items or firms whose date has not come yet, for answers like "(a) and (c) apply
    from 30 September 2027"."""
    return [e for e in chunk.get("effective_exceptions", []) if not _started(e["from"], today)]
