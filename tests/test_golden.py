"""The golden set (evals/golden.yaml) is well formed and points at real chunks."""

import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

from bnm_rag.metadata import applicability
from bnm_rag.parse.document import CORPUS

GOLDEN = Path(__file__).resolve().parents[1] / "evals" / "golden.yaml"
FIELDS = {"id", "question", "lang", "firm", "coverage", "expected", "also_ok", "must_say",
          "must_not_say", "tags", "reviewed"}
TAGS = {"done", "draft", "rmit-vs-tr", "date", "threshold", "faq", "applicability",
        "out-of-corpus", "malay", "superseded"}


@pytest.fixture(scope="module")
def golden() -> dict:
    with open(GOLDEN, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_format(golden):
    assert isinstance(golden["as_of"], dt.date)
    qs = golden["questions"]
    assert len(qs) >= 40
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids))
    roles = set(applicability.load()["roles"])
    for q in qs:
        assert set(q) >= FIELDS, q["id"]
        assert set(q) <= FIELDS | {"pointer"}, q["id"]
        assert q["lang"] in ("en", "ms"), q["id"]
        assert set(q["firm"]) <= roles, q["id"]
        assert set(q["tags"]) <= TAGS, q["id"]
        assert q["must_say"], q["id"]
        assert q["coverage"] in ("answered", "partial", "not_covered"), q["id"]
        if q["coverage"] == "not_covered":
            assert not q["expected"] and q.get("pointer"), q["id"]
        else:
            assert q["expected"], q["id"]
        if q["coverage"] == "partial":
            assert q.get("pointer"), q["id"]


def test_the_plan_s_cases_are_all_there(golden):
    tags = [t for q in golden["questions"] for t in q["tags"]]
    assert tags.count("done") == 4
    for tag in ("draft", "rmit-vs-tr", "out-of-corpus", "date", "threshold", "faq", "superseded"):
        assert tags.count(tag) >= 2, tag
    assert tags.count("malay") >= 3


def test_every_chunk_id_exists(golden):
    path = CORPUS / "chunks.jsonl"
    if not path.exists():
        pytest.skip("run `uv run python -m bnm_rag.parse` first")
    with open(path, encoding="utf-8") as f:
        ids = {json.loads(line)["chunk_id"] for line in f}
    for q in golden["questions"]:
        missing = [c for c in q["expected"] + q["also_ok"] if c not in ids]
        assert not missing, (q["id"], missing)
