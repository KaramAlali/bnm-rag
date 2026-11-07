"""Who each chunk applies to, from corpus/curated/applicability.yaml (report findings 5, 7).

Chunks get `applies_to` (role ids, in the YAML's order) and `applies_note`. FAQs and feedback
statements take their policy document's roles (`parent_doc`).
"""

from __future__ import annotations

from functools import cache

import yaml

from bnm_rag.metadata.dates import CURATED
from bnm_rag.metadata.select import matches_any


@cache
def load() -> dict:
    with open(CURATED / "applicability.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check(data: dict) -> None:
    """Every role named anywhere must be in the vocabulary."""
    known = set(data["roles"])
    named: list[str] = list(data["tech_requirements_tiers"]["rmit_roles"])
    named += data["tech_requirements_tiers"]["tier4_roles"]
    for doc in data["documents"].values():
        named += doc["roles"]
        for row in doc.get("table", []):
            named += row["roles"]
        for rule in doc.get("rules", []):
            for op in ("only", "remove", "add"):
                named += rule.get(op, [])
    unknown = sorted(set(named) - known)
    if unknown:
        raise ValueError(f"applicability.yaml: unknown roles {unknown}")


def parent_doc(doc_id: str, policy_ids: set[str]) -> str | None:
    """rmit_faq → rmit_pd, emoney_fs → emoney_pd; None for a policy document itself."""
    if doc_id in policy_ids:
        return None
    stem = doc_id.rsplit("_", 1)[0]
    return next((p for p in sorted(policy_ids) if p.rsplit("_", 1)[0] == stem), None)


def chunk_roles(chunk: dict, doc: dict, order: list[str]) -> tuple[list[str], str | None]:
    roles = set(doc["roles"])
    notes: list[str] = []
    rows = [r for r in doc.get("table", []) if matches_any(chunk, r["paras"])]
    if rows:
        roles = {role for r in rows for role in r["roles"]}
        notes += [r["note"] for r in rows if r.get("note")]
    for rule in doc.get("rules", []):
        if not matches_any(chunk, rule["paras"], rule.get("except")):
            continue
        if "only" in rule:
            roles &= set(rule["only"])
        roles -= set(rule.get("remove", []))
        roles |= set(rule.get("add", []))
        if rule.get("note"):
            notes.append(rule["note"])
    note = " ".join(" ".join(n.split()) for n in notes) or None
    return [r for r in order if r in roles], note


def assign_roles(chunks: list[dict]) -> None:
    data = load()
    check(data)
    docs, order = data["documents"], list(data["roles"])
    policy_ids = {c["doc_id"] for c in chunks if c["kind"] in ("policy_document", "exposure_draft")}
    missing = policy_ids - set(docs)
    if missing:
        raise ValueError(f"applicability.yaml: no entry for {sorted(missing)}")
    for c in chunks:
        parent = parent_doc(c["doc_id"], policy_ids)
        c["parent_doc"] = parent
        if parent:
            c["applies_to"] = [r for r in order if r in docs[parent]["roles"]]
            c["applies_note"] = None
        else:
            c["applies_to"], c["applies_note"] = chunk_roles(c, docs[c["doc_id"]], order)


def tech_requirements_tier(
    roles: set[str], annual_value_rm: float | None = None, annual_volume: int | None = None
) -> dict:
    """Tech Requirements 2.4: which tier a payment services regulatee is in, and which
    document it follows. Tier-1 (RMiT) and Tier-4 depend on the firm type; Tier-2 and Tier-3 on
    last calendar year's transaction value (RM) and volume."""
    t = load()["tech_requirements_tiers"]
    rmit = sorted(roles & set(t["rmit_roles"]))
    if rmit:
        return {"tier": 1, "follows": "rmit_pd",
                "reason": f"{', '.join(rmit)} is covered by RMiT; of Tech Requirements only "
                          "paragraph 2.2 (2.7, 13.3, Appendix 10) applies"}
    if roles & set(t["tier4_roles"]):
        return {"tier": 4, "follows": "techreq-psr_pd",
                "reason": "non-digital currency exchange MSB: paragraph 16 only"}
    if annual_value_rm is None or annual_volume is None:
        return {"tier": None, "follows": "techreq-psr_pd",
                "reason": "Tier-2 or Tier-3: needs last year's transaction value and volume"}
    if annual_value_rm > t["value_threshold_rm"] or annual_volume > t["volume_threshold"]:
        return {"tier": 2, "follows": "techreq-psr_pd",
                "reason": "value above RM1.5 billion or volume above 7 million"}
    return {"tier": 3, "follows": "techreq-psr_pd",
            "reason": "value at most RM1.5 billion and volume at most 7 million"}
