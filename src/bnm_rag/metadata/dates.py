"""Effective dates per chunk (corpus report finding 3).

Each policy document's default comes from its paragraph 4.1; the exceptions are in
corpus/curated/effective_dates.yaml, each with a quote a test checks against the PDF text.
Chunks get `effective_from` (ISO date or "pending: <event>"), `effective_exceptions` (later
dates for some sub-items or some firms) and `effective_note`. FAQs and feedback statements are
not rules and get None.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

from bnm_rag.metadata.select import matches_any

CURATED = Path(__file__).resolve().parents[3] / "corpus" / "curated"
RULE_KINDS = ("policy_document", "exposure_draft")

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
DATE = re.compile(rf"(\d{{1,2}})\s+((?:{'|'.join(m[:3] for m in MONTHS)})[a-z]*)\s+(\d{{4}})")
COMES_INTO_EFFECT = re.compile(r"comes? into (?:immediate )?effect on " + DATE.pattern)
ONE_YEAR_AFTER_ISSUE = re.compile(r"one \(1\) year after the date of its issuance")


def parse_date(text: str) -> dt.date:
    """'28 November 2025' → date(2025, 11, 28); '23 Aug 2022' works too."""
    m = DATE.search(text)
    if not m:
        raise ValueError(f"no date in {text!r}")
    month = [x[:3] for x in MONTHS].index(m[2][:3]) + 1
    return dt.date(int(m[3]), month, int(m[1]))


def iso_date(value: str) -> dt.date | None:
    """sources.csv 'issued': '2026-09-25 (re-issue)' → a date; '2026-09 (file date)' → None."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})\b", value or "")
    return dt.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def add_one_year(day: dt.date) -> dt.date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year + 1, day=28)


def document_default(doc_chunks: list[dict], issued: dt.date | None) -> dt.date:
    """The date in paragraph 4.1 ('comes into effect on …' or one year after issuance)."""
    para = next((c for c in doc_chunks if c["para_no"] == "4.1" and not c.get("appendix")), None)
    if para is None:
        raise ValueError(f"{doc_chunks[0]['doc_id']}: no paragraph 4.1")
    text = " ".join(para["text"].split())
    if ONE_YEAR_AFTER_ISSUE.search(text):
        if issued is None:
            raise ValueError(f"{para['chunk_id']}: needs an issue date")
        return add_one_year(issued)
    m = COMES_INTO_EFFECT.search(text)
    if not m:
        raise ValueError(f"{para['chunk_id']}: no effective date in {text[:120]!r}")
    return parse_date(m.group(0))


def load_exceptions() -> list[dict]:
    with open(CURATED / "effective_dates.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _as_text(value: dt.date | str) -> str:
    return value.isoformat() if isinstance(value, dt.date) else " ".join(str(value).split())


def assign_dates(chunks: list[dict], issued: dict[str, dt.date | None]) -> None:
    """Sets effective_from / effective_exceptions / effective_note on every chunk, in place."""
    by_doc: dict[str, list[dict]] = {}
    for c in chunks:
        by_doc.setdefault(c["doc_id"], []).append(c)
    exceptions = load_exceptions()
    for doc_id, doc_chunks in by_doc.items():
        rules = doc_chunks[0]["kind"] in RULE_KINDS
        default = document_default(doc_chunks, issued.get(doc_id)) if rules else None
        for c in doc_chunks:
            c["effective_from"] = default.isoformat() if default else None
            c["effective_until"] = None
            c["effective_exceptions"] = []
            c["effective_note"] = None
        for e in (e for e in exceptions if e["doc_id"] == doc_id):
            if ("from" in e) == ("until" in e):
                raise ValueError(f"effective_dates.yaml: {doc_id} {e['paras']} needs from or until")
            hit = [c for c in doc_chunks if matches_any(c, e["paras"])]
            if not hit:
                raise ValueError(f"effective_dates.yaml: {doc_id} {e['paras']} matches no chunk")
            start = _as_text(e["from"]) if "from" in e else None
            end = _as_text(e["until"]) if "until" in e else None
            source = f"{e['source_doc']} {e['source']}" if e.get("source_doc") else e["source"]
            for c in hit:
                if e.get("items") or e.get("who"):
                    c["effective_exceptions"].append({
                        "from": start,
                        "until": end,
                        "items": e.get("items"),
                        "who": " ".join(e["who"].split()) if e.get("who") else None,
                        "source": source,
                    })
                elif end:
                    c["effective_until"] = end
                else:
                    c["effective_from"] = start
                if e.get("note"):
                    c["effective_note"] = " ".join(e["note"].split())
