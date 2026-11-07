"""FAQ ↔ paragraph links (corpus report finding 8).

FAQ answers cite "[Paragraph 10.31]"; the parser keeps those as `para_refs`. Here they become
`refers_to` on the FAQ chunk (chunk ids in its policy document) and `faq_links` on each cited
paragraph, so retrieving a paragraph can bring its FAQ answers with it.
"""

from __future__ import annotations

import re

NUMBER = re.compile(r"\d+(?:\.\d+)+")


def ref_numbers(ref: str) -> list[str]:
    """'17.1 and 17.2' → ['17.1', '17.2']; '6.2 (d), Paragraph 6.5 (a)' → ['6.2', '6.5']."""
    return NUMBER.findall(ref)


def link_faqs(chunks: list[dict]) -> list[str]:
    """Sets refers_to / faq_links in place; returns the refs that match no paragraph."""
    by_id = {c["chunk_id"]: c for c in chunks}
    for c in chunks:
        c["refers_to"] = []
        c["faq_links"] = []
    unresolved = []
    for c in chunks:
        if c["kind"] != "faq" or not c["parent_doc"]:
            continue
        for ref in c["para_refs"]:
            for number in ref_numbers(ref):
                target = by_id.get(f"{c['parent_doc']}:{number}")
                if target is None:
                    unresolved.append(f"{c['chunk_id']} → {number}")
                    continue
                if target["chunk_id"] not in c["refers_to"]:
                    c["refers_to"].append(target["chunk_id"])
                if c["chunk_id"] not in target["faq_links"]:
                    target["faq_links"].append(c["chunk_id"])
    return unresolved
