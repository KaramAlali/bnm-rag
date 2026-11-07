"""Step 2 metadata rules that run anywhere (no PDFs needed)."""

import datetime as dt

import pytest

from bnm_rag.metadata import applicability
from bnm_rag.metadata.applicability import parent_doc, tech_requirements_tier
from bnm_rag.metadata.dates import (
    add_one_year,
    document_default,
    iso_date,
    load_exceptions,
    parse_date,
)
from bnm_rag.metadata.links import ref_numbers
from bnm_rag.metadata.related import current_version, normalise, parse_item
from bnm_rag.metadata.select import matches, matches_any, para_key
from bnm_rag.metadata.status import later_parts, status
from bnm_rag.parse.document import sources

DOC_IDS = {s["file"].removesuffix(".pdf") for s in sources()}
TODAY = dt.date(2026, 11, 7)


def para(para_no, text="", appendix=None, part="PART B POLICY REQUIREMENTS", doc_id="x_pd"):
    return {"chunk_id": f"{doc_id}:{para_no}", "doc_id": doc_id, "para_no": para_no,
            "appendix": appendix, "part": part, "text": text}


# --- dates -----------------------------------------------------------------------------------

def test_parse_date():
    assert parse_date("comes into effect on 28 November 2025 except") == dt.date(2025, 11, 28)
    assert parse_date("issued 23 Aug 2022") == dt.date(2022, 8, 23)
    with pytest.raises(ValueError):
        parse_date("one (1) year after")


def test_iso_date_from_sources_csv():
    assert iso_date("2026-09-25 (re-issue)") == dt.date(2026, 9, 25)
    assert iso_date("2026-09 (file date)") is None
    assert add_one_year(dt.date(2024, 2, 29)) == dt.date(2025, 2, 28)


@pytest.mark.parametrize(("text", "issued", "expected"), [
    # Tech Requirements: computed from the issue date (report finding 3)
    ("This policy document comes into effect one (1) year after the date of its issuance.",
     dt.date(2026, 3, 12), dt.date(2027, 3, 12)),
    ("This policy document comes into effect on 28 November 2025 except where otherwise "
     "stated explicitly in this policy document.", None, dt.date(2025, 11, 28)),
    # Complaints Handling: the default is the first date, 12.1-12.4 are an exception
    ("This Policy Document comes into effect on 1 April 2026, except for paragraphs 12.1 to "
     "12.4, which shall come into immediate effect on 28 March 2025.", None, dt.date(2026, 4, 1)),
    ("This Policy Document comes into effect on\n1 January 2027, subject to the transition "
     "arrangements set out in paragraph 9.", None, dt.date(2027, 1, 1)),
])
def test_document_default_from_paragraph_4_1(text, issued, expected):
    chunks = [para("1.1", "Intro", part="PART A OVERVIEW"),
              para("4.1", text, part="PART A OVERVIEW")]
    assert document_default(chunks, issued) == expected


def test_every_exception_names_a_known_document_and_a_quote():
    for e in load_exceptions():
        assert e["doc_id"] in DOC_IDS
        assert e["paras"] and e["source"] and e["quote"]
        start = e["from"]
        assert isinstance(start, dt.date) or str(start).startswith("pending: ")


# --- status (computed, never stored) ------------------------------------------------------

def rule(kind="policy_document", start="2025-11-28", exceptions=()):
    return {"kind": kind, "effective_from": start, "effective_exceptions": list(exceptions)}


def test_status_is_computed_against_the_day():
    assert status(rule(start="2027-03-12"), TODAY) == "not yet in force"
    assert status(rule(start="2027-03-12"), dt.date(2027, 3, 12)) == "in force"
    assert status(rule(start="pending: Nexus go-live"), dt.date(2099, 1, 1)) == "not yet in force"


def test_exposure_draft_is_proposed_whatever_date_it_states():
    draft = rule(kind="exposure_draft", start="2027-01-01")
    assert status(draft, dt.date(2030, 1, 1)) == "proposed"


def test_faqs_have_no_status():
    assert status(rule(kind="faq", start=None), TODAY) is None
    assert status(rule(kind="feedback_statement", start=None), TODAY) is None


def test_later_parts_lists_sub_items_not_yet_in_force():
    c = rule(exceptions=[{"from": "2027-09-30", "items": "(a), (c)", "who": None,
                          "source": "10.31"}])
    assert status(c, TODAY) == "in force"
    assert [e["items"] for e in later_parts(c, TODAY)] == ["(a), (c)"]
    assert later_parts(c, dt.date(2027, 9, 30)) == []


# --- selectors -------------------------------------------------------------------------------

def test_para_key():
    assert para_key("13.2 / item 8") == (13, 2)
    assert para_key("Q4") is None
    assert para_key(None) is None


def test_selectors():
    assert matches(para("17.1"), "17.1-21.3")
    assert matches(para("19.4"), "17.1-21.3")
    assert matches(para("21.3"), "17.1-21.3")
    assert not matches(para("21.4"), "17.1-21.3")
    assert not matches(para("9.10"), "9.1-9.3")  # numeric, not string, order
    assert matches(para("16.3"), "16")
    assert not matches(para("1.6"), "16")
    assert matches(para("13.2 / item 8"), "13.2")
    appendix = para("Appendix 10 / 1", appendix="Appendix 10")
    assert matches(appendix, "Appendix 10")
    assert not matches(appendix, "1")  # appendices restart their numbering
    assert matches(para("2.4", part="PART A OVERVIEW"), "Part A")
    assert not matches(para("2.4", part="PART C SPECIFIC"), "Part A")
    assert not matches_any(para("2.4", part="PART A OVERVIEW"), ["all"], ["Part A"])


# --- applicability ---------------------------------------------------------------------------

def test_applicability_yaml_is_consistent():
    data = applicability.load()
    applicability.check(data)
    policy_ids = {s["file"].removesuffix(".pdf") for s in sources()
                  if s["kind"] in ("policy_document", "exposure_draft")}
    assert set(data["documents"]) == policy_ids


def test_faqs_and_feedback_statements_have_a_parent():
    policy = {"rmit_pd", "techreq-psr_pd", "emoney_pd", "complaints_pd", "open-finance_ed"}
    assert parent_doc("rmit_faq", policy) == "rmit_pd"
    assert parent_doc("techreq-psr_faq", policy) == "techreq-psr_pd"
    assert parent_doc("emoney_fs", policy) == "emoney_pd"
    assert parent_doc("complaints_fs", policy) == "complaints_pd"
    assert parent_doc("rmit_pd", policy) is None


def test_rmit_vs_tech_requirements_split():
    chunks = [para("10.31"), para("2.4", part="PART A OVERVIEW"), para("13.3"),
              para("16.1"), para("Appendix 10 / 1", appendix="Appendix 10")]
    tr = {c["para_no"]: c for c in chunks}
    for c in chunks:
        c["kind"] = "policy_document"
        c["doc_id"] = "techreq-psr_pd"
    doc = applicability.load()["documents"]["techreq-psr_pd"]
    order = list(applicability.load()["roles"])
    roles = {n: set(applicability.chunk_roles(c, doc, order)[0]) for n, c in tr.items()}
    # Tier-1 (RMiT) firms: only 2.2's list (2.7, 13.3, Appendix 10) plus Part A
    assert "eligible_emi" not in roles["10.31"]
    assert {"eligible_emi", "dps_operator"} <= roles["13.3"]
    assert "eligible_emi" in roles["2.4"]
    assert "standard_emi" in roles["10.31"]
    # Tier-4: paragraph 16 only, and 16 is only for Tier-4
    assert roles["16.1"] == {"msb_nondigital_fx"}
    assert "msb_nondigital_fx" not in roles["10.31"]
    # Appendix 10: merchant acquirers only, RMiT or not (2.6(d), footnote 7)
    assert roles["Appendix 10 / 1"] == {"nonbank_acquirer", "nonbank_acquirer_major"}


@pytest.mark.parametrize(("roles", "value", "volume", "tier", "follows"), [
    ({"eligible_emi"}, 800e6, 5_000_000, 1, "rmit_pd"),
    ({"dps_operator"}, None, None, 1, "rmit_pd"),
    ({"msb_nondigital_fx"}, 2e9, 9_000_000, 4, "techreq-psr_pd"),
    # the "done" question: an e-wallet with RM800m a year, if it is a standard EMI
    ({"standard_emi"}, 800e6, 5_000_000, 3, "techreq-psr_pd"),
    ({"standard_emi"}, 1.5e9, 7_000_000, 3, "techreq-psr_pd"),  # at the threshold: Tier-3
    ({"standard_emi"}, 2e9, 3_000_000, 2, "techreq-psr_pd"),  # value alone exceeds
    ({"msb"}, 1e9, 8_000_000, 2, "techreq-psr_pd"),  # volume alone exceeds
    ({"standard_emi"}, 800e6, None, None, "techreq-psr_pd"),  # can't tell 2 from 3
])
def test_tech_requirements_tier(roles, value, volume, tier, follows):
    got = tech_requirements_tier(roles, value, volume)
    assert (got["tier"], got["follows"]) == (tier, follows)


# --- FAQ links and related documents ---------------------------------------------------------

def test_faq_reference_numbers():
    assert ref_numbers("10.31") == ["10.31"]
    assert ref_numbers("17.1 and 17.2") == ["17.1", "17.2"]
    assert ref_numbers("6.2 (d), Paragraph 6.5 (a)") == ["6.2", "6.5"]


def test_parse_related_items():
    got = parse_item("Policy Document on Corporate Governance issued on 3 August 2016 "
                     "(BNM/RH/PD 029-9);")
    assert got == {"title": "Policy Document on Corporate Governance", "issued": "2016-08-03",
                   "reference": "BNM/RH/PD 029-9", "paragraphs": None}
    got = parse_item("Paragraphs 30 to 34 of the Policy Document on Governance, Risk "
                     "Management, and Operations for Money Services Business (MSB);")
    assert got["paragraphs"] == "30 to 34"
    assert got["title"].startswith("Policy Document on Governance")
    got = parse_item("Paragraph 33 – Specific requirements for acquirers in policy document on "
                     "Credit Card issued on 2 July 2019;")
    assert (got["paragraphs"], got["title"]) == ("33", "Policy Document on Credit Card")
    assert parse_item("Notification on X issued 23 Aug 2022;")["issued"] == "2022-08-23"


def test_same_document_under_different_names():
    assert normalise("Outsourcing") == normalise("Policy document on Outsourcing")
    assert normalise("Dear CEOs Letter on Specifications on Countermeasures to Combat E-Money "
                     "Fraud") == normalise("Specifications on Countermeasures to Combat E-Money "
                                           "Fraud")
    aml_2020 = ("Policy Document on Anti-Money Laundering, Counter Financing of Terrorism and "
                "Targeted Financial Sanctions for Financial Institutions (AML/CFT and TFS for FIs)")
    aml_2024 = ("Anti-Money Laundering, Countering Financing of Terrorism, Countering "
                "Proliferation Financing and Targeted Financial Sanctions for Financial "
                "Institutions (AML/CFT/CPF and TFS for FIs) policy document")
    assert normalise(aml_2020) == normalise(aml_2024)
    # two different documents that differ only by a descriptive bracket
    assert normalise("Policy Document on Corporate Governance") != normalise(
        "Policy Document on Corporate Governance (applicable to prescribed development "
        "financial institutions)")


def test_current_version_in_corpus():
    assert current_version("Risk Management in Technology (RMiT)") == "rmit_pd"
    ictf = "Policy Document on Interoperable Credit Transfer Framework"  # replaced by the IFTF
    assert current_version(ictf) == "iftf_pd"
    assert current_version("Guideline on Complaints Handling") == "complaints_pd"
    assert current_version("Specifications on Countermeasures to Combat E-Money Fraud") is None
    assert current_version("Policy Document on Outsourcing") is None
