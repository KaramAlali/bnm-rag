"""Layout lines → chunks.

One chunk per numbered paragraph (policy documents, the exposure draft, feedback statements),
one per question (FAQs), and one per table row for the two documents laid out as a table.
Sub-items (a), (i) stay with their paragraph; appendix paragraphs carry the appendix number.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from bnm_rag.parse.layout import (
    Line,
    Page,
    Span,
    finish,
    group_lines,
    join_text,
    split_footnotes,
)

SG_PARA = re.compile(r"^(?P<sg>[SG])\s+(?P<num>\d{1,2}(?:\.\d{1,3}){1,3})\.?(?:\s+(?P<rest>.*))?$")
NUM_PARA = re.compile(r"^(?P<num>\d{1,2}(?:\.\d{1,3}){1,3})\.?(?:\s+(?P<rest>.*))?$")
ITEM = re.compile(r"^(?P<num>\d{1,3})\.(?!\d)\s*(?P<rest>.*)$")
SECTION = re.compile(r"^(?P<num>\d{1,2})\.?\s+(?P<title>[A-Z“\"(].*)$")
PART = re.compile(r"^PART\s+(?P<letter>[A-Z])\b[\s:.\-–]*(?P<title>.*)$")
APPENDIX = re.compile(
    r"^(?:APPENDIX|Appendix)\s+(?P<n>\d{1,2}|[IVX]{1,5})\b(?![.\d])[\s:.\-–]*(?P<title>.*)$"
)
SUBITEM = re.compile(r"^\((?:[a-z]{1,2}|[ivx]{1,6}|\d{1,2})\)(\s|$)")
DOTS = re.compile(r"\.{6,}|…{2,}|(?:\. ){5,}")
PARA_REF = re.compile(r"\[Paragraphs?\s+([^\]]+)\]", re.I)
STARTS_SENTENCE = re.compile(r"^[A-Z“\"‘'(\[]")
REPEATED_MARKER = re.compile(r"^([SG])(?:\s+\1)+(?=\s)")  # glyphs stacked in the PDF
FAQ_PART = re.compile(r"^Part [A-Z]\b")
MAX_NUMBER_X = 130  # paragraph numbers sit in the left column; wrapped text starts further right
WRAP_GAP = 4  # points: a heading wrapped onto a second line sits closer than two headings do

# Documents laid out as one big table: (column label, column's left edge in points).
TABLE_LAYOUTS = {
    "ekyc_faq": [("No", 0), ("Q", 100), ("A", 270)],
    "complaints_fs": [("No", 0), ("Area", 75), ("Feedback received", 190), ("BNM's response", 480)],
}
LIST_ITEM = re.compile(r"^(?:[ivx]{1,4}\.|[a-z]\)|•)\s")
ROW_NUMBER = re.compile(r"^(\d{1,2})\.(?:\s|$)")
EMAIL_ITEM = re.compile(r"^\([a-z]\).*@")  # a named officer's address: not indexed


@dataclass(frozen=True)
class LongTable:
    """A table inside a policy document that runs over many pages, read by column position.

    Its continuation pages have no full grid, so ruled-table detection splits rows mid-cell.
    """

    para: str  # the paragraph that introduces the table; rows become "<para> / item <n>"
    header: str  # the header row starts with this text
    columns: tuple[tuple[str, int], ...]  # (label, column's left edge in points)


LONG_TABLES = {
    "mcipd_pd": LongTable(
        "13.2",  # printed inside 13.2; the S in 13.1 is what makes the conditions binding
        "Purposes for or circumstances",
        (("Purpose", 0), ("Disclosed to", 220), ("Conditions", 325)),
    ),
}


@dataclass
class Chunk:
    doc_id: str
    para_no: str
    obligation: str = "none"  # S | G | none
    part: str | None = None
    section: str | None = None
    appendix: str | None = None
    heading_path: list[str] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)
    notes: list[int] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    question_done: bool = True  # FAQ: bold lines after the number belong to the question

    @property
    def text(self) -> str:
        return "\n".join(s for s in self.segments if s)

    def add(self, line: Line, new_segment: bool = False) -> None:
        text = line.text
        if new_segment or not self.segments or line.kind == "table" or SUBITEM.match(text):
            self.segments.append(text)
        else:
            self.segments[-1] = join_text([self.segments[-1], text])
        self.notes.extend(n for n in line.notes if n not in self.notes)
        if line.page not in self.pages:
            self.pages.append(line.page)


def number(num: str) -> tuple[int, ...]:
    return tuple(int(x) for x in num.split("."))


def follows(new: tuple[int, ...], last: tuple[int, ...] | None) -> bool:
    """Is `new` a plausible next paragraph number after `last` (allowing small gaps)?"""
    if last is None:
        return True
    for i in range(min(len(last), len(new))):
        if (
            new[:i] == last[:i]
            and last[i] < new[i] <= last[i] + 3
            and all(v <= 2 for v in new[i + 1 :])
        ):
            return True
    return new[: len(last)] == last and len(new) == len(last) + 1 and new[-1] <= 2


def heading_like(line: Line) -> bool:
    t = line.text
    return (
        line.bold
        and len(t) < 160
        and not t.startswith(("“", '"', "‘"))
        and not t.endswith((",", ";"))
        and not SUBITEM.match(t)
    )


def short(heading: str, limit: int = 60) -> str:
    """A heading for use inside a para_no: cut at a word boundary."""
    heading = heading.rstrip(":")
    if len(heading) <= limit:
        return heading
    return heading[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-–")


def number_span_bold(line: Line) -> bool:
    for s in line.spans:
        if s.text.strip():
            return s.bold
    return False


class Builder:
    """Walks a document's lines in reading order and cuts them into chunks."""

    def __init__(self, doc_id: str, kind: str):
        self.doc_id, self.kind = doc_id, kind
        self.faq = kind == "faq"
        self.started = kind not in ("policy_document", "exposure_draft")
        self.chunks: list[Chunk] = []
        self.cur: Chunk | None = None
        self.part = self.section = self.sub = self.appendix = None
        self.over: str | None = None  # a heading stacked directly above the sub-heading
        self.sub_line: Line | None = None  # the line that set the sub-heading
        self.section_line: Line | None = None  # the line that set the section heading
        self.appendix_title: str | None = None
        self.title_open = False  # appendix heading seen, title lines may follow
        self.last: tuple[int, ...] | None = None
        self.prev: Line | None = None
        self.rejected: list[str] = []
        self.used: set[str] = set()
        self.faq_part: str | None = None  # FAQs split into parts restart their numbering
        self.last_q = 0
        self.q_x = 0.0  # x of the current question number; topic headings sit there too
        self.front: list[Line] = []  # lines before the start (cover, contents, any preface)

    # -- state -------------------------------------------------------------------------------
    def close(self) -> None:
        if self.cur and self.cur.segments:
            self.chunks.append(self.cur)
        self.cur = None

    def heading_path(self) -> list[str]:
        if self.appendix:
            head = self.appendix
            if self.appendix_title:
                head = f"{self.appendix}: {self.appendix_title}"
            return [h for h in (head, self.section, self.over, self.sub) if h]
        return [h for h in (self.part, self.section, self.over, self.sub) if h]

    def qualify(self, para: str) -> str:
        """Make a repeated number unique with the part or sub-heading it restarted under."""
        if para not in self.used:
            return para
        qualified = None
        if self.faq and self.faq_part:
            qualified = f"{self.faq_part} / {para}"
        elif self.appendix and self.sub and para.startswith(f"{self.appendix} / "):
            item = para[len(self.appendix) + 3 :]
            qualified = f"{self.appendix} / {short(self.sub)} / {item}"
        return qualified if qualified and qualified not in self.used else para

    def open(self, para_no: str, obligation: str = "none") -> Chunk:
        self.close()
        self.title_open = False
        para_no = self.qualify(para_no)
        self.used.add(para_no)
        self.cur = Chunk(
            self.doc_id, para_no, obligation, self.part, self.section, self.appendix,
            self.heading_path(),
        )
        return self.cur

    def scope_label(self) -> str:
        """para_no for text that has no number of its own: its section plus any sub-heading."""
        if self.appendix:
            base = self.appendix
        elif self.section:
            base = self.section.split()[0].rstrip(".")
        else:
            base = "intro"
        sub = self.sub or (self.section if self.appendix else None)
        if sub and (len(sub) <= 60 or base in self.used):
            return f"{base} / {short(sub)}"
        return base

    # -- line handling -----------------------------------------------------------------------
    def is_continuation(self, line: Line) -> bool:
        """A line glued to the one before it (no gap, sentence not finished) is not a heading."""
        p = self.prev
        if not (self.cur and p and p.page == line.page):
            return False
        return line.y0 - p.y1 < 4 and not p.text.rstrip().endswith((".", ":", ";"))

    def start_allowed(self, line: Line) -> bool:
        t = line.text
        if PART.match(t) and line.bold and t.startswith("PART A"):
            return True
        m = SG_PARA.match(t) or NUM_PARA.match(t)
        if m and number(m["num"]) == (1, 1):
            return True
        m = SECTION.match(t)
        return bool(m and line.bold and m["num"] == "1")

    def feed(self, line: Line) -> None:
        line.text = t = REPEATED_MARKER.sub(r"\1", line.text)
        if DOTS.search(t) or t.upper() == "APPENDICES":
            return
        if not self.started:
            if not self.start_allowed(line):
                self.front.append(line)
                return
            self.started = True
        self.handle(line)
        self.prev = line

    def handle(self, line: Line) -> None:
        t = line.text
        if line.kind == "table":
            (self.cur or self.open(self.scope_label())).add(line)
            return

        m = APPENDIX.match(t)
        if m and (line.bold or t.startswith("APPENDIX")) and len(t) < 160:
            self.close()
            self.appendix = f"Appendix {m['n']}"
            self.appendix_title = m["title"].strip() or None
            self.title_open = True
            self.part = self.section = self.sub = None
            self.over = None
            self.last = None
            return

        m = PART.match(t)
        if m and line.bold:
            self.close()
            if self.appendix:
                self.sub = t
                self.over = None
            else:
                self.part, self.section, self.sub = t, None, None
                self.over = None
            return

        m = SG_PARA.match(t)
        if m:
            self.start_paragraph(m["num"], m["rest"], line, m["sg"])
            return

        if self.faq:
            m = ITEM.match(t)
            n = int(m["num"]) if m else 0
            if m and number_span_bold(line) and (self.last_q < n <= self.last_q + 3 or n == 1):
                self.last_q, self.q_x = n, line.x0
                self.open(f"Q{n}")
                self.cur.question_done = False
                question = f"Q: {(m['rest'] or '').strip()}"
                self.cur.add(Line(line.page, line.spans, question, line.notes))
                return
            if self.cur and not self.cur.question_done:
                if line.bold:
                    self.cur.add(line)
                    return
                self.cur.question_done = True
                answer = Line(line.page, line.spans, f"A: {t}", line.notes)
                self.cur.add(answer, new_segment=True)
                return

        m = None if self.faq else NUM_PARA.match(t)
        if m and not self.is_continuation(line):
            num = number(m["num"])
            rest = m["rest"] or ""
            if line.bold and number_span_bold(line) and len(t) < 120:
                self.close()
                self.sub = t  # a numbered sub-heading, e.g. "13.2 Security Perimeters"
                self.over = None
                return
            if (
                line.x0 < MAX_NUMBER_X
                and (not rest or STARTS_SENTENCE.match(rest))
                and follows(num, self.last)
            ):
                self.start_paragraph(m["num"], rest, line)
                return
            self.rejected.append(f"p{line.page}: {t[:80]}")

        m = ITEM.match(t)
        if m and self.appendix and not number_span_bold(line) and line.x0 < MAX_NUMBER_X:
            num = (int(m["num"]),)
            if follows(num, self.last) or num == (1,):
                self.last = num
                para = f"{self.appendix} / {m['num']}"
                self.open(para).add(Line(line.page, line.spans, m["rest"] or "", line.notes))
                return

        m = SECTION.match(t)
        if m and line.bold and len(t) < 120 and not self.is_continuation(line):
            self.close()
            self.section, self.sub = t, None
            self.over = None
            self.section_line = line
            if not self.appendix:
                self.last = (int(m["num"]), 0)
            return

        if heading_like(line) and not self.is_continuation(line):
            if self.faq and self.cur and line.x0 > self.q_x + 10:
                self.cur.add(line)  # bold text inside an answer, e.g. "Scenario 1:"
                return
            p = self.prev
            under_title = p and p.page == line.page and line.y0 - p.y1 < 8
            if self.title_open and not self.cur and under_title:
                self.appendix_title = join_text([self.appendix_title or "", t]).strip()
                return
            self.close()
            self.title_open = False
            gap = line.y0 - p.y1 if under_title else None
            wrapped = gap is not None and (gap < WRAP_GAP or t[:1].islower())
            if wrapped and p is self.section_line:
                self.section = join_text([self.section or "", t])
                self.section_line = line
                return
            if wrapped and p is self.sub_line:
                self.sub = join_text([self.sub or "", t])
            else:
                self.over = self.sub if p is self.sub_line else None  # a group heading above
                self.sub = t
            self.sub_line = line
            if self.faq and FAQ_PART.match(t):
                self.faq_part = FAQ_PART.match(t).group(0)
            if self.appendix:
                self.last = None  # appendix parts often restart their numbering
            return

        (self.cur or self.open(self.scope_label())).add(line)

    def start_paragraph(self, num: str, rest: str | None, line: Line, sg: str | None = None):
        self.last = number(num)
        para = f"{self.appendix} / {num}" if self.appendix else num
        chunk = self.open(para, sg or "none")
        chunk.add(Line(line.page, line.spans, (rest or "").strip(), line.notes))


def doc_footnotes(pages: list[Page]) -> dict[int, str]:
    notes: dict[int, str] = {}
    last = None
    for page in pages:
        for n, text in sorted(page.footnotes.items()):
            if n == 0:
                if last is not None:
                    notes[last] = join_text([notes[last], text])
                continue
            notes[n] = text
            last = n
    return notes


def finalize(doc_id: str, chunks: list[Chunk], notes: dict[int, str]) -> list[dict]:
    seen: Counter[str] = Counter()
    out = []
    for c in chunks:
        seen[c.para_no] += 1
        chunk_id = f"{doc_id}:{c.para_no}" + (f"#{seen[c.para_no]}" if seen[c.para_no] > 1 else "")
        text = c.text
        out.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "para_no": c.para_no,
                "obligation": c.obligation,
                "part": c.part,
                "section": c.section,
                "appendix": c.appendix,
                "heading_path": c.heading_path,
                "text": text,
                "footnotes": [{"n": n, "text": notes.get(n, "")} for n in c.notes],
                "page_start": min(c.pages),
                "page_end": max(c.pages),
                "para_refs": PARA_REF.findall(text),
            }
        )
    return out


def chunk_lines(doc_id: str, kind: str, pages: list[Page]) -> tuple[list[dict], list[str]]:
    builder = Builder(doc_id, kind)
    table = LONG_TABLES.get(doc_id)
    region: list[Line] | None = None  # a long table's lines, until the next paragraph
    for page in pages:
        for line in page.lines:
            if table and region is None and line.text.startswith(table.header):
                builder.close()
                region = []
                continue  # the header row
            if region is not None:
                t = line.text
                if line.x0 < MAX_NUMBER_X - 60 and (SG_PARA.match(t) or NUM_PARA.match(t)):
                    builder.chunks.extend(long_table_chunks(builder, table, region))
                    region, table = None, None
                else:
                    region.append(line)
                    continue
            builder.feed(line)
    builder.close()
    preface = preface_chunk(doc_id, pages, builder.front)
    chunks = ([preface] if preface else []) + builder.chunks
    return finalize(doc_id, chunks, doc_footnotes(pages)), builder.rejected


def preface_chunk(doc_id: str, pages: list[Page], front: list[Line]) -> Chunk | None:
    """Text before Part A that is neither the cover nor the table of contents.

    Only the exposure draft has one: what the draft proposes and the feedback deadline.
    """
    toc = {p.number for p in pages if any(DOTS.search(ln.text) for ln in p.lines)}
    lines = [ln for ln in front if ln.page > 1 and ln.page not in toc]
    lines = [ln for ln in lines if not EMAIL_ITEM.match(ln.text)]
    if not lines:
        return None
    chunk = Chunk(doc_id, "preface")
    prev = None
    for ln in lines:
        gap = prev is None or ln.page != prev.page or ln.y0 - prev.y1 > 8
        chunk.add(ln, new_segment=gap)
        prev = ln
    return chunk


def long_table_chunks(builder: Builder, table: LongTable, lines: list[Line]) -> list[Chunk]:
    """One chunk per row. A row starts at an item number ("3.") in the first column and may
    continue over several pages; each cell's sub-items and bullets keep their own lines."""
    spans = [(ln.page, s) for ln in lines for s in ln.spans]
    first_col_end = table.columns[1][1]
    starts: list[tuple[int, float, int]] = []  # (page, y, item number)
    for page, s in sorted(spans, key=lambda ps: (ps[0], ps[1].y0)):
        m = ROW_NUMBER.match(s.text.strip())
        last = starts[-1][2] if starts else 0
        if m and s.x0 < first_col_end and last < int(m[1]) <= last + 3:
            starts.append((page, s.y0 - 5, int(m[1])))  # 5 pt: raised footnote markers
    cells: dict[int, dict[int, list[tuple[int, Span]]]] = {n: {} for *_, n in starts}
    for page, s in spans:
        row = [n for p, y, n in starts if (p, y) <= (page, s.y0)]
        if row:
            col = max(i for i, (_, x) in enumerate(table.columns) if s.x0 >= x - 3)
            cells[row[-1]].setdefault(col, []).append((page, s))

    chunks = []
    for n, row in cells.items():
        para_no = f"{table.para} / item {n}"
        builder.used.add(para_no)
        chunk = Chunk(builder.doc_id, para_no, "none", builder.part, builder.section,
                      builder.appendix, builder.heading_path())
        for col, cell in sorted(row.items()):
            first = True
            for page in sorted({p for p, _ in cell}):
                for ln in group_lines([s for p, s in cell if p == page], page):
                    finish(ln)
                    if first:
                        text = ROW_NUMBER.sub("", ln.text) if col == 0 else ln.text
                        ln.text = f"{table.columns[col][0]}: {text}"
                    chunk.add(ln, new_segment=first or bool(LIST_ITEM.match(ln.text)))
                    first = False
        chunks.append(chunk)
    return chunks


# -- documents laid out as a table ---------------------------------------------------------------
def chunk_table(doc_id: str, pages: list[Page], columns: list[tuple[str, int]]) -> list[dict]:
    """Split by column position; a number in the first column starts a new row.

    The table ends at an appendix heading or at text that runs across the first column
    (a closing note); what follows becomes chunks of its own.
    """
    intro: list[tuple[int, Span]] = []
    tail: list[tuple[int, Span]] = []
    rows: list[dict] = []
    heading, in_table, ended, last = None, False, False, 0
    notes: dict[int, str] = {}
    for page in pages:
        header = next((s for s in page.spans if s.text.strip() in ("No", "No.") and s.bold), None)
        if header:
            in_table = True
        body, foot = table_footnotes(page, columns[1][1])
        notes.update(foot)
        for s in sorted(body, key=lambda s: (round(s.cy), s.x0)):
            if ended:
                tail.append((page.number, s))
                continue
            if not in_table or (header and s.y1 <= header.y0):
                intro.append((page.number, s))
                continue
            if header and abs(s.cy - header.cy) < 4:
                continue  # the column labels
            col = max(i for i, (_, x) in enumerate(columns) if s.x0 >= x - 3)
            text = s.text.strip()
            if col == 0:
                m = re.fullmatch(r"(\d{1,3})\s*\.?", text)
                if m and s.size >= 9 and last < int(m[1]) <= last + 3:
                    last = int(m[1])
                    rows.append({"no": m[1], "heading": heading, "cells": {}})
                elif APPENDIX.match(text) or (not s.bold and s.x1 > columns[1][1]):
                    ended = True
                    tail.append((page.number, s))
                elif s.bold:
                    heading = text
                continue
            if rows:
                rows[-1]["cells"].setdefault(col, []).append((page.number, s))

    chunks = []
    if intro:
        chunks.append(table_chunk(doc_id, "intro", None, [("", intro)], notes, sep="\n"))
    faq = doc_id.endswith("_faq")
    for row in rows:
        if not row["cells"]:
            continue
        cells = [(columns[c][0], spans) for c, spans in sorted(row["cells"].items())]
        para = f"Q{row['no']}" if faq else row["no"]
        chunks.append(table_chunk(doc_id, para, row["heading"], cells, notes))
    for para, title, spans in split_tail(tail):
        chunks.append(table_chunk(doc_id, para, title, [("", spans)], notes, sep="\n"))
    return chunks


def split_tail(tail: list[tuple[int, Span]]) -> list[tuple[str, str | None, list]]:
    """After the table: a closing note, then any appendices, each with its own heading."""
    groups: list[tuple[str, str | None, list]] = []
    for page_no, s in tail:
        m = APPENDIX.match(s.text.strip())
        if m and s.bold:
            groups.append((f"Appendix {m['n']}", s.text.strip(), []))
        elif not groups:
            groups.append(("closing", None, []))
        groups[-1][2].append((page_no, s))
    return [g for g in groups if g[2]]


def table_footnotes(page: Page, first_col_end: float) -> tuple[list[Span], dict[int, str]]:
    """Footnotes start at a small number in the first column near the page bottom."""
    starts = [
        s.y0
        for s in page.spans
        if s.size < 8
        and s.text.strip()[:1].isdigit()
        and s.x0 < first_col_end
        and s.y0 > 0.6 * page.height
    ]
    if not starts:
        return page.spans, {}
    top = min(starts) - 1
    body = [s for s in page.spans if s.y0 < top]
    lines = group_lines([s for s in page.spans if s.y0 >= top], page.number)
    return body, split_footnotes(lines, page.height)[1]


def table_chunk(doc_id, para_no, heading, cells, doc_notes: dict[int, str], sep=" ") -> dict:
    """cells: [(label, [(page, span), ...]), ...] → one chunk, a "label: text" line per cell."""
    segments, pages, notes = [], set(), []
    for label, spans in cells:
        texts = []
        for page_no in sorted({p for p, _ in spans}):
            page_spans = [s for p, s in spans if p == page_no]
            lines = [finish(ln) for ln in group_lines(page_spans, page_no)]
            texts.extend(ln.text for ln in lines)
            notes.extend(n for ln in lines for n in ln.notes)
            pages.add(page_no)
        body = "\n".join(texts) if sep == "\n" else join_text(texts)
        segments.append(f"{label}: {body}" if label else body)
    text = "\n".join(segments)
    return {
        "chunk_id": f"{doc_id}:{para_no}",
        "doc_id": doc_id,
        "para_no": para_no,
        "obligation": "none",
        "part": None,
        "section": None,
        "appendix": None,
        "heading_path": [heading] if heading else [],
        "text": text,
        "footnotes": [{"n": n, "text": doc_notes.get(n, "")} for n in dict.fromkeys(notes)],
        "page_start": min(pages),
        "page_end": max(pages),
        "para_refs": PARA_REF.findall(text),
    }
