"""Step 2 metadata on the real corpus: every effective-date case in corpus report finding 3,
who RMiT and Tech Requirements apply to, IFTF's table, FAQ links, the out-of-corpus list.
Skipped when corpus/raw/ is empty (e.g. in CI)."""

import datetime as dt
import json

from conftest import needs_pdfs

from bnm_rag.metadata.dates import load_exceptions
from bnm_rag.metadata.select import matches_any
from bnm_rag.metadata.status import later_parts, status
from bnm_rag.parse.document import CORPUS

pytestmark = needs_pdfs

TODAY = dt.date(2026, 11, 7)


def flat(text: str) -> str:
    return " ".join(text.split())


def test_every_exception_quote_is_in_its_source_paragraph(enriched):
    """effective_dates.yaml cannot drift from the PDF text."""
    chunks, _ = enriched
    for e in load_exceptions():
        source = chunks[f"{e.get('source_doc', e['doc_id'])}:{e['source']}"]
        assert flat(e["quote"]) in flat(source["text"]), e


def test_every_rule_has_a_date_and_explanations_have_none(enriched):
    chunks, _ = enriched
    for c in chunks.values():
        if c["kind"] in ("policy_document", "exposure_draft"):
            assert c["effective_from"], c["chunk_id"]
        else:
            assert c["effective_from"] is None and status(c, TODAY) is None


def test_tech_requirements_is_one_year_after_issue(enriched):
    chunks, _ = enriched
    tr = [c for c in chunks.values() if c["doc_id"] == "techreq-psr_pd"]
    assert {c["effective_from"] for c in tr} == {"2027-03-12"}
    assert status(chunks["techreq-psr_pd:2.4"], TODAY) == "not yet in force"
    assert status(chunks["techreq-psr_pd:2.4"], dt.date(2027, 3, 12)) == "in force"


def test_rmit_10_31_sub_items_start_later(enriched):
    chunks, _ = enriched
    c = chunks["rmit_pd:10.31"]
    assert c["effective_from"] == "2025-11-28"
    assert status(c, TODAY) == "in force"
    assert [(e["items"], e["from"]) for e in later_parts(c, TODAY)] == [("(a), (c)", "2027-09-30")]
    assert [e["items"] for e in later_parts(chunks["rmit_pd:10.35"], TODAY)] == ["(e)"]
    assert chunks["rmit_pd:10.30"]["effective_exceptions"] == []


def test_rmit_appendix_12_waits_for_nacsa(enriched):
    chunks, _ = enriched
    app12 = [c for c in chunks.values() if c["doc_id"] == "rmit_pd"
             and c["appendix"] == "Appendix 12"]
    assert len(app12) > 100
    assert all(c["effective_from"].startswith("pending: endorsement") for c in app12)
    assert status(app12[0], TODAY) == "not yet in force"
    assert chunks["rmit_pd:Appendix 11"]["effective_from"] == "2025-11-28"


def test_iftf_4_1_points_to_appendix_ii(enriched):
    chunks, _ = enriched
    for n in ("9.3", "9.4", "9.8", "9.11"):
        assert chunks[f"iftf_pd:{n}"]["effective_from"].startswith("pending: live"), n
    for n in ("9.7", "9.12"):
        c = chunks[f"iftf_pd:{n}"]
        assert c["effective_from"] == "2026-06-30"
        assert [(e["items"], e["from"]) for e in c["effective_exceptions"]] == [
            ("(b)", "2028-06-30")]
    assert chunks["iftf_pd:9.1"]["effective_from"] == "2026-06-30"


def test_merchant_acquiring_staggered_for_non_banks(enriched):
    chunks, _ = enriched
    for n, later in (("17.1", "2022-09-15"), ("21.3", "2022-09-15"), ("9.2", "2023-09-15")):
        c = chunks[f"merchant-acq_pd:{n}"]
        assert c["effective_from"] == "2022-03-15"
        assert [(e["who"], e["from"]) for e in c["effective_exceptions"]] == [
            ("non-bank acquirers", later)]
    assert chunks["merchant-acq_pd:22.1"]["effective_exceptions"] == []
    assert chunks["merchant-acq_pd:16.1"]["effective_exceptions"] == []


def test_complaints_12_1_to_12_4_started_first(enriched):
    chunks, _ = enriched
    for n in ("12.1", "12.2", "12.3", "12.4"):
        assert chunks[f"complaints_pd:{n}"]["effective_from"] == "2025-03-28"
    assert chunks["complaints_pd:11.5"]["effective_from"] == "2026-04-01"


def test_tech_requirements_supersedes_older_tech_sections(enriched):
    """Until 12 March 2027 an e-wallet's tech rules are e-Money PD 27-31; then Tech
    Requirements (7.1). Merchant Acquiring 22 has no IT rules and stays."""
    chunks, _ = enriched
    for cid in ("emoney_pd:27.1", "emoney_pd:31.1", "merchant-acq_pd:17.1", "merchant-acq_pd:21.3"):
        c = chunks[cid]
        assert c["effective_until"] == "2027-03-12", cid
        assert status(c, TODAY) == "in force"
        assert status(c, dt.date(2027, 3, 12)) == "superseded"
    for cid in ("emoney_pd:26.1", "emoney_pd:32.1", "merchant-acq_pd:22.1", "pso_pd:18.1"):
        assert chunks[cid]["effective_until"] is None, cid
    pso = chunks["pso_pd:19.1"]["effective_exceptions"]
    assert [(e["who"], e["until"]) for e in pso] == [
        ("operators of a designated payment system", "2027-03-12")]
    assert chunks["techreq-psr_pd:2.4"]["effective_until"] is None


def test_open_finance_is_always_proposed(enriched):
    chunks, _ = enriched
    draft = [c for c in chunks.values() if c["doc_id"] == "open-finance_ed"]
    assert {c["effective_from"] for c in draft} == {"2027-01-01", "2028-01-01"}
    assert {status(c, dt.date(2030, 1, 1)) for c in draft} == {"proposed"}
    assert [e["from"] for e in chunks["open-finance_ed:8.4"]["effective_exceptions"]] == [
        "2028-01-01", "2029-01-01"]


def test_rmit_and_tech_requirements_never_share_a_firm(enriched):
    """Tier-1 firms follow RMiT; of Tech Requirements only 2.2 (2.7, 13.3, Appendix 10) and
    Part A reach them. Tiers 2-4 never get RMiT."""
    chunks, _ = enriched
    rmit_only = {"eligible_emi", "nonbank_acquirer_major", "iri_major", "dps_operator"}
    tr_only = {"standard_emi", "nonbank_acquirer", "msb", "msb_nondigital_fx"}
    for c in chunks.values():
        if c["doc_id"] == "rmit_pd":
            assert not tr_only & set(c["applies_to"]), c["chunk_id"]
        elif c["doc_id"] == "techreq-psr_pd" and not matches_any(
                c, ["Part A", "13.3", "Appendix 10"]):
            assert not rmit_only & set(c["applies_to"]), c["chunk_id"]
    assert "eligible_emi" in chunks["techreq-psr_pd:13.3"]["applies_to"]


def test_rmit_2_2_exclusions(enriched):
    chunks, _ = enriched
    assert "eligible_emi" not in chunks["rmit_pd:16.1"]["applies_to"]
    assert "licensed_bank" in chunks["rmit_pd:16.1"]["applies_to"]
    assert "dps_operator" not in chunks["rmit_pd:12.5"]["applies_to"]
    assert "NCII" in chunks["rmit_pd:13.3"]["applies_note"]


def test_iftf_table_decides_each_paragraph(enriched):
    chunks, _ = enriched
    roles = {n: set(chunks[f"iftf_pd:{n}"]["applies_to"]) for n in ("9.11", "9.2", "8.7", "9.3")}
    assert roles["9.11"] == {"bank_acquirer", "nonbank_acquirer", "nonbank_acquirer_major"}
    assert roles["9.2"] == {"licensed_bank", "dfi", "eligible_emi"}
    assert roles["8.7"] == {"shared_infra_operator", "payment_system_operator"}
    assert "eligible_emi" not in roles["9.3"]  # banking institutions only


def test_complaints_approved_persons_only_12_1_to_12_4(enriched):
    chunks, _ = enriched
    assert "standard_emi" in chunks["complaints_pd:12.1"]["applies_to"]
    assert "standard_emi" not in chunks["complaints_pd:11.5"]["applies_to"]
    assert "eligible_emi" in chunks["complaints_pd:11.5"]["applies_to"]


def test_faq_links_both_ways(enriched):
    chunks, _ = enriched
    assert "techreq-psr_faq:Q4" in chunks["techreq-psr_pd:2.4"]["faq_links"]
    assert chunks["techreq-psr_faq:Q4"]["refers_to"] == ["techreq-psr_pd:2.4"]
    assert {"rmit_pd:17.1", "rmit_pd:17.2"} <= {
        t for c in chunks.values() if c["doc_id"] == "rmit_faq" for t in c["refers_to"]}
    linked = sum(bool(c["refers_to"]) for c in chunks.values() if c["kind"] == "faq")
    assert linked >= 60


def test_out_of_corpus_list(enriched):
    _, related = enriched
    titles = [o["title"] for o in related["out_of_corpus"]]
    assert "Policy Document on Outsourcing" in titles
    assert "Personal Data Protection Act 2010" in titles
    assert sum("Anti-Money Laundering" in t for t in titles) == 1
    assert not any("Risk Management in Technology" in t for t in titles)
    # letters RMiT superseded now live in RMiT, wherever they are cited
    fraud = [link for link in related["links"]
             if "Measures to Combat Electronic Banking Fraud" in link["title"]]
    assert len(fraud) == 3 and {link["in_corpus"] for link in fraud} == {"rmit_pd"}


def test_related_docs_json_is_current(enriched):
    """corpus/related_docs.json is committed (the app needs it without the PDFs), so it must
    match what the code builds now. Regenerate with `uv run python -m bnm_rag.parse`."""
    _, related = enriched
    with open(CORPUS / "related_docs.json", encoding="utf-8") as f:
        assert json.load(f) == related
