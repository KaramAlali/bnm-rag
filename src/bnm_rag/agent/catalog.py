"""The corpus as the agent sees it: the 20 indexed documents (corpus/sources.csv) and the
documents they cite that are not indexed (corpus/related_docs.json). Both files are committed,
so this works without the PDFs or chunks.jsonl.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
from functools import cache

from bnm_rag.metadata.status import status
from bnm_rag.parse.document import CORPUS

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


@cache
def documents() -> dict[str, dict]:
    """doc_id → {doc_id, title, kind, reference, issued, effective, effective_from, source_url}.
    `effective` is the free-text note from sources.csv; `effective_from` its leading date."""
    with open(CORPUS / "sources.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        doc_id = r["file"].removesuffix(".pdf")
        m = ISO.match(r["effective"]) if r["kind"] == "policy_document" else None
        out[doc_id] = {
            "doc_id": doc_id, "title": r["document"], "kind": r["kind"],
            "reference": r["reference"] or None, "issued": r["issued"],
            "effective": r["effective"] or None, "effective_from": m.group(0) if m else None,
            "source_url": r["source_url"],
        }
    return out


@cache
def out_of_corpus() -> list[dict]:
    with open(CORPUS / "related_docs.json", encoding="utf-8") as f:
        return json.load(f)["out_of_corpus"]


def document_status(doc: dict, today: dt.date) -> str:
    """Document-level status for the catalog. Paragraph-level dates can differ (RMiT 10.31,
    Complaints 12.1-12.4, ...): answers use each paragraph's own status, not this."""
    if doc["kind"] in ("faq", "feedback_statement"):
        return "explains rules (not a rule itself)"
    return status({"kind": doc["kind"], "effective_from": doc["effective_from"]}, today) or ""
