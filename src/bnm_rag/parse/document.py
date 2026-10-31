"""One source PDF → its chunks, with the document's metadata from corpus/sources.csv."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pymupdf
import yaml

from bnm_rag.parse.chunk import PARA_REF, TABLE_LAYOUTS, chunk_lines, chunk_table
from bnm_rag.parse.layout import read_pdf

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus"


def sources() -> list[dict]:
    with open(CORPUS / "sources.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def figures(doc_id: str) -> list[dict]:
    """Hand transcriptions of figures the parser cannot read (corpus/curated/figures.yaml)."""
    with open(CORPUS / "curated" / "figures.yaml", encoding="utf-8") as f:
        return [fig for fig in yaml.safe_load(f) if fig["doc_id"] == doc_id]


def parse_document(src: dict) -> tuple[list[dict], list[str]]:
    """Returns the chunks and any paragraph numbers the parser chose not to start on."""
    path = CORPUS / "raw" / src["file"]
    doc_id = Path(src["file"]).stem
    figs = figures(doc_id)
    skip: dict[int, list[pymupdf.Rect]] = {}
    for fig in figs:
        if "region" in fig:
            skip.setdefault(fig["page"], []).append(pymupdf.Rect(fig["region"]))
    if doc_id in TABLE_LAYOUTS:
        pages = read_pdf(path, tables=False, skip=skip)
        chunks, rejected = chunk_table(doc_id, pages, TABLE_LAYOUTS[doc_id]), []
    else:
        chunks, rejected = chunk_lines(doc_id, src["kind"], read_pdf(path, skip=skip))
    chunks = add_figures(doc_id, chunks, figs)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    for c in chunks:
        c.update(
            kind=src["kind"],
            title=src["document"],
            reference=src["reference"] or None,
            source_url=src["source_url"],
            file_sha256=digest,
        )
    return chunks, rejected


def add_figures(doc_id: str, chunks: list[dict], figs: list[dict]) -> list[dict]:
    """Append each transcription to the chunk with its para_no, or insert it as a new chunk
    after the last chunk that starts on or before its page."""
    for c in chunks:
        c["figure"] = False
    for fig in figs:
        text = fig["text"].strip()
        same = [c for c in chunks if c["para_no"] == fig["para_no"]]
        if same:
            c = same[0]
            c["text"] = f"{c['text']}\n{text}" if c["text"] else text
            c["page_start"] = min(c["page_start"], fig["page"])
            c["page_end"] = max(c["page_end"], fig["page"])
        else:
            c = {
                "chunk_id": f"{doc_id}:{fig['para_no']}",
                "doc_id": doc_id,
                "para_no": fig["para_no"],
                "obligation": "none",
                "part": None,
                "section": None,
                "appendix": fig.get("appendix"),
                "heading_path": fig.get("heading_path", []),
                "text": text,
                "footnotes": [],
                "page_start": fig["page"],
                "page_end": fig["page"],
            }
            at = sum(1 for other in chunks if other["page_start"] <= fig["page"])
            chunks.insert(at, c)
        c["para_refs"] = PARA_REF.findall(c["text"])
        c["figure"] = True
    return chunks
