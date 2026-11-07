"""Related and superseded documents, and the out-of-corpus list (corpus report finding 9).

Read from each policy document's Part A: section 6 (related) and section 7 (superseded), or
wherever a Part A paragraph says "supersedes". Each named document is matched to the indexed
document that now holds it, if any: its current version (RMiT 2023 → rmit_pd), or the indexed
document that superseded it (the 2022 e-banking fraud letters → rmit_pd). The rest form the
out-of-corpus list the agent uses to say "that's in the Outsourcing policy document, which
isn't indexed".
"""

from __future__ import annotations

import re

from bnm_rag.metadata.dates import DATE, parse_date

ITEM = re.compile(r"^\(([a-z]|[ivx]+)\)\s*(.+)$")
ISSUED = re.compile(r"\s*,?\s*(?:issued(?: on)?|dated)\s+(" + DATE.pattern + r")")
REFERENCE = re.compile(r"\s*\((BNM/[^)]+)\)")
# "Paragraphs 30 to 34 of the Policy Document on …" (Tech Requirements 7.1) and
# "Paragraph 33 – Specific requirements for acquirers in policy document on …" (Merchant
# Acquiring 7.1): only those paragraphs were superseded.
PARAGRAPHS = (re.compile(r"^Paragraphs?\s+(\d+(?:\s+to\s+\d+)?)\s+of\s+(?:the\s+)?", re.I),
              re.compile(r"^Paragraphs?\s+(\d+(?:\s+to\s+\d+)?)\s+[–-].*?\s+in\s+", re.I))
BLANK_PAGE = re.compile(r"\s*The rest of the page is intentionally left (?:as )?blank\.?", re.I)
ACT = re.compile(r"(?:[A-Z][\w’']*\s+)+Act \d{4}")
# Wrappers around the same document's name: "Dear CEOs Letter on Specifications on Measures to
# Combat …" and "Notification on Specifications Relating to Measures to Combat …" name the same
# letter. Stripped repeatedly for matching only; titles are shown as printed.
PREFIX = re.compile(
    r"^(?:the\s+|policy documents?\s+on\s+|policy documents?\s+|guidelines?\s+on\s+|"
    r"dear ceos letter on\s+|circular of notification on\s+|notifications?\s+on\s+|"
    r"industry letter on\s+|specification letter on\s+|specifications?\s+(?:on|relating to)\s+)",
    re.I)
SUFFIX = re.compile(r"\s+policy document$", re.I)
# Renamed documents (the AML/CFT policy document gained "Countering Proliferation Financing").
ALIASES = {"anti-money laundering": "anti-money laundering, cft and tfs"}

# The indexed document that is the current version of a named one, by the start of its
# normalised title. The Interoperable Credit Transfer Framework was replaced by the IFTF
# (iftf_pd 7.1).
CURRENT = {
    "risk management in technology": "rmit_pd",
    "technology requirements": "techreq-psr_pd",
    "electronic money": "emoney_pd",
    "electronic know-your-customer": "ekyc_pd",
    "payment system operator": "pso_pd",
    "merchant acquiring services": "merchant-acq_pd",
    "interoperable fund transfer framework": "iftf_pd",
    "interoperable credit transfer framework": "iftf_pd",
    "management of customer information": "mcipd_pd",
    "complaints handling": "complaints_pd",
    "financial technology regulatory sandbox": "sandbox_pd",
    "open finance": "open-finance_ed",
}


def normalise(title: str) -> str:
    """A matching key: 'Policy Document on Outsourcing' and 'Outsourcing' → 'outsourcing'.
    Acronyms in brackets go; descriptive brackets stay (two Corporate Governance documents
    differ only by '(applicable to prescribed development financial institutions)')."""
    t = re.sub(r"\s*\([^)\s]*\)", "", title.strip())
    while (stripped := PREFIX.sub("", t)) != t:
        t = stripped
    t = " ".join(SUFFIX.sub("", t).lower().split())
    return next((key for start, key in ALIASES.items() if t.startswith(start)), t)


def display(title: str) -> str:
    """'the policy document on the Payment Card Reform Framework' →
    'Policy Document on Payment Card Reform Framework'; 'The Personal Data …' → 'Personal …'."""
    t = re.sub(r"^(?:the\s+)?policy document on\s+(?:the\s+)?", "Policy Document on ", title,
               flags=re.I)
    return re.sub(r"^The\s+", "", t)


def current_version(title: str) -> str | None:
    t = normalise(title)
    return next((doc for start, doc in CURRENT.items() if t.startswith(start)), None)


def parse_item(text: str) -> dict:
    text = BLANK_PAGE.sub("", text).strip().rstrip(";.").strip()
    text = re.sub(r";?\s*and$", "", text).strip()
    issued = ref = paragraphs = None
    if m := REFERENCE.search(text):
        ref, text = m[1], (text[: m.start()] + text[m.end():]).strip()
    if m := ISSUED.search(text):
        issued, text = parse_date(m[1]).isoformat(), text[: m.start()].strip()
    for pattern in PARAGRAPHS:
        if m := pattern.match(text):
            paragraphs, text = m[1], text[m.end():]
            break
    return {"title": display(text.strip(" ,;")), "issued": issued, "reference": ref,
            "paragraphs": paragraphs}


def part_a_sources(chunks: list[dict]) -> list[tuple[dict, str]]:
    """(chunk, relation) for every Part A paragraph that names related or superseded documents."""
    out = []
    for c in chunks:
        if c["kind"] not in ("policy_document", "exposure_draft") or c.get("appendix"):
            continue
        if not (c.get("part") or "").upper().startswith("PART A"):
            continue
        section = (c.get("section") or "").lstrip()
        if "supersede" in c["text"]:
            out.append((c, "superseded"))
        elif section.startswith("6"):
            out.append((c, "related"))
    return out


def items_of(c: dict) -> list[tuple[str | None, str]]:
    lines = [" ".join(line.split()) for line in c["text"].split("\n")]
    items = [(m[1], m[2]) for line in lines if (m := ITEM.match(line))]
    if items:
        return items
    flat = " ".join(lines)
    if m := re.search(r"supersedes the (.+?)(?:\.\s|\.$|$)", flat):
        return [(None, m[1])]
    return [(None, act) for act in dict.fromkeys(ACT.findall(flat))]


def related_documents(chunks: list[dict]) -> dict:
    links = []
    for c, relation in part_a_sources(chunks):
        for item, text in items_of(c):
            entry = parse_item(text)
            links.append({
                "doc_id": c["doc_id"], "para_no": c["para_no"], "item": item,
                "relation": relation, **entry,
                "in_corpus": current_version(entry["title"]),
            })
    # A document an indexed one superseded in full now lives in that indexed document.
    replaced = {normalise(link["title"]): link["doc_id"] for link in links
                if link["relation"] == "superseded" and not link["paragraphs"]}
    for link in links:
        if link["in_corpus"]:
            continue
        key = normalise(link["title"])
        link["in_corpus"] = next((doc for old, doc in replaced.items()
                                  if key.startswith(old) or old.startswith(key)), None)
    outside: dict[str, dict] = {}
    for link in links:
        if link["in_corpus"]:
            continue
        entry = outside.setdefault(normalise(link["title"]),
                                   {"title": link["title"], "references": [], "cited_by": []})
        if len(link["title"]) > len(entry["title"]):
            entry["title"] = link["title"]
        if link["reference"] and link["reference"] not in entry["references"]:
            entry["references"].append(link["reference"])
        item = f"({link['item']})" if link["item"] else ""
        entry["cited_by"].append(f"{link['doc_id']} {link['para_no']}{item} {link['relation']}")
    return {"links": links,
            "out_of_corpus": sorted(outside.values(), key=lambda e: e["title"].lower())}
