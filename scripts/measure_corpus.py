"""Measure the raw BNM PDFs: size, text layer, S/G paragraphs, tables, dates.

Usage: python scripts/measure_corpus.py   (from the repo root)
Writes corpus/text/<name>.txt (pdftotext -layout) and corpus/measurements.json.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT = ROOT / "corpus/raw", ROOT / "corpus/text"
TXT.mkdir(parents=True, exist_ok=True)

SG = re.compile(r"^\s{0,12}([SG])\s{1,6}(\d{1,2}\.\d{1,3})\b", re.M)
NUM = re.compile(r"^\s{0,12}(?:[SG]\s{1,6})?(\d{1,2}\.\d{1,3})\s", re.M)
REF = re.compile(r"BNM/RH/[A-Z]{2,3}\s*\d{3}-\d{1,3}")
TABLE = re.compile(r"^\s*Table\s+\d+", re.M | re.I)
APPX = re.compile(r"^\s*APPENDI(?:X|CES)\s+[0-9IVX]+", re.M | re.I)
DATE = re.compile(r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
                  r"September|October|November|December)\s+20\d\d\b")
MALAY = re.compile(r"\b(?:dan|yang|untuk|dengan|tidak|kepada|hendaklah)\b", re.I)
QUESTION = re.compile(r"^\s*(?:Q?\d{1,3}[.)]|Question\s+\d+)\s+\S.*\?\s*$", re.M)

def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))

rows = []
for pdf in sorted(RAW.glob("*.pdf")):
    n = pages(pdf)
    txt = TXT / (pdf.stem + ".txt")
    subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
    text = txt.read_text(encoding="utf-8", errors="replace")
    per_page = text.split("\f")[:n]
    low = [i + 1 for i, p in enumerate(per_page) if len(p.strip()) < 150]
    sg = SG.findall(text)
    words = len(text.split())
    rows.append({
        "file": pdf.name, "pages": n, "chars": len(text), "words": words,
        "est_tokens": round(len(text) / 4),
        "near_empty_pages": low,
        "s_paras": sum(1 for k, _ in sg if k == "S"),
        "g_paras": sum(1 for k, _ in sg if k == "G"),
        "numbered_paras": len(set(NUM.findall(text))),
        "tables": len(TABLE.findall(text)),
        "appendix_headings": len(set(m.group(0).strip().upper() for m in APPX.finditer(text))),
        "refs": sorted(set(REF.findall(text))),
        "dates_mentioned": len(DATE.findall(text)),
        "malay_word_ratio": round(len(MALAY.findall(text)) / max(words, 1), 4),
        "faq_questions": len(QUESTION.findall(text)),
    })

(ROOT / "corpus/measurements.json").write_text(json.dumps(rows, indent=2))
cols = ["file", "pages", "chars", "est_tokens", "s_paras", "g_paras", "numbered_paras",
        "tables", "appendix_headings", "faq_questions", "malay_word_ratio"]
print("\t".join(cols))
for r in rows:
    print("\t".join(str(r[c]) for c in cols))
tot = {c: sum(r[c] for r in rows) for c in ["pages", "chars", "est_tokens", "s_paras", "g_paras"]}
print("TOTAL", tot)
for r in rows:
    if r["near_empty_pages"] or r["refs"]:
        print(r["file"], "refs:", r["refs"], "near-empty pages:", r["near_empty_pages"])
