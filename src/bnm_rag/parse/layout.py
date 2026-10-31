"""PDF layout: text spans → visual lines per page.

Running headers and footers are dropped, footnotes are split off the page body (their markers
are stripped from the text and kept as numbers), and ruled tables become one line per row.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

BOLD, SUPERSCRIPT = 16, 1
NOTE_MARKER = re.compile(r"^[\d,\s]+$")
PAGE_NUMBER = re.compile(r"^(page\s*)?\d+(\s*of\s*\d+)?$", re.I)
SPACES = re.compile(r"\s+")
BULLET = re.compile(r"(^|\s)\ufffd(?=\s)")  # a glyph with no Unicode mapping


@dataclass
class Span:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    size: float
    bold: bool
    sup: bool

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Line:
    page: int
    spans: list[Span]
    text: str = ""
    notes: list[int] = field(default_factory=list)
    kind: str = "body"  # body | table

    @property
    def x0(self) -> float:
        return min(s.x0 for s in self.spans)

    @property
    def y0(self) -> float:
        return min(s.y0 for s in self.spans)

    @property
    def y1(self) -> float:
        return max(s.y1 for s in self.spans)

    @property
    def size(self) -> float:
        """Font size carrying the most characters."""
        weight: dict[float, int] = defaultdict(int)
        for s in self.spans:
            weight[round(s.size, 1)] += len(s.text.strip())
        return max(weight, key=weight.get)

    @property
    def bold(self) -> bool:
        body = [s for s in self.spans if not s.sup and s.text.strip()]
        return bool(body) and all(s.bold for s in body)


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line]
    footnotes: dict[int, str]
    spans: list[Span] = field(default_factory=list)  # body spans, headers and footers removed


def clean(text: str) -> str:
    text = BULLET.sub("\\1\u2022", text.replace("\xa0", " "))  # standing alone: a bullet
    text = text.replace("\ufffd", "'")  # inside a word: an apostrophe
    return SPACES.sub(" ", text).strip()


def page_spans(page: pymupdf.Page) -> list[Span]:
    """Every non-empty span, in the page's visual (de-rotated) coordinates."""
    matrix = page.rotation_matrix
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                if not s["text"].strip():
                    continue
                r = pymupdf.Rect(s["bbox"]) * matrix
                r.normalize()
                spans.append(
                    Span(r.x0, r.y0, r.x1, r.y1, s["text"], s["size"],
                         bool(s["flags"] & BOLD), bool(s["flags"] & SUPERSCRIPT))
                )
    return spans


def group_lines(spans: list[Span], page_no: int) -> list[Line]:
    """Spans that share a vertical band form one line (catches detached S/G markers)."""
    lines: list[Line] = []
    for s in sorted(spans, key=lambda s: (s.cy, s.x0)):
        for line in reversed(lines[-6:]):
            core = [t for t in line.spans if not t.sup] or line.spans
            y0, y1 = min(t.y0 for t in core), max(t.y1 for t in core)
            overlap = min(y1, s.y1) - max(y0, s.y0)
            if overlap > 0.5 * min(y1 - y0, s.y1 - s.y0):
                line.spans.append(s)
                break
        else:
            lines.append(Line(page_no, [s]))
    for line in lines:
        line.spans.sort(key=lambda s: s.x0)
    return sorted(lines, key=lambda ln: (round(ln.y0), ln.x0))


def is_marker(span: Span, line_size: float, first: bool) -> bool:
    """A footnote reference in body text: a raised or small run of digits."""
    if first or not NOTE_MARKER.match(span.text.strip()):
        return False
    return span.sup or span.size < 0.8 * line_size


def render(spans: list[Span], line_size: float, notes: list[int]) -> str:
    out, prev = "", None
    for i, s in enumerate(spans):
        if is_marker(s, line_size, first=i == 0):
            notes.extend(int(n) for n in re.findall(r"\d+", s.text))
            prev = s
            continue
        ordinal = s.sup and not s.text.strip().isdigit()  # "1st": keep "st" attached
        if prev is not None and s.x0 - prev.x1 > 1.0 and not out.endswith(" ") and not ordinal:
            out += " "
        out += s.text
        prev = s
    return clean(out)


def finish(line: Line) -> Line:
    line.notes = []
    line.text = render(line.spans, line.size, line.notes)
    return line


def header_keys(pages: list[list[Line]], heights: list[float]) -> set[str]:
    """Normalised texts that repeat in the top or bottom band of many pages."""
    seen: dict[str, set[int]] = defaultdict(set)
    for lines, h in zip(pages, heights, strict=True):
        for ln in lines:
            if ln.y1 < 0.11 * h or ln.y0 > 0.9 * h:
                seen[band_key(ln)].add(ln.page)
    need = max(2, 0.3 * len(pages))
    return {k for k, p in seen.items() if len(p) >= need and len(k) >= 4}


def band_key(line: Line) -> str:
    text = "".join(s.text for s in line.spans).lower()
    return re.sub(r"\s+", "", re.sub(r"\d+", "#", text))


def split_footnotes(lines: list[Line], height: float) -> tuple[list[Line], dict[int, str]]:
    """Footnotes sit at the page bottom: a small number, then smaller-than-body text."""
    start = None
    for i, ln in enumerate(lines):
        first = ln.spans[0]
        if (
            ln.y0 > 0.45 * height
            and first.size <= 8.5
            and first.text.strip()[:1].isdigit()
            and ln.size <= 10.5
        ):
            start = i
            break
    if start is None:
        return lines, {}
    # Unnumbered small lines just above the first footnote continue the previous page's note.
    while (
        start > 0
        and lines[start - 1].size <= 10.5
        and lines[start - 1].y0 > 0.6 * height
        and lines[start].y0 - lines[start - 1].y1 < 6
    ):
        start -= 1
    body, notes, current = lines[:start], {}, None
    for ln in lines[start:]:
        if ln.size > 10.5:
            body.append(ln)
            continue
        first = ln.spans[0]
        text = clean("".join(s.text for s in ln.spans))
        m = re.match(r"^(\d{1,3})\s*(.*)$", text)
        if m and first.size <= 8.5:
            current = int(m.group(1))
            notes[current] = m.group(2)
        elif current is not None:
            notes[current] = clean(notes[current] + " " + text)
        else:
            notes.setdefault(0, "")  # continuation from the previous page
            notes[0] = clean(notes[0] + " " + text)
    return body, notes


def has_grid(page: pymupdf.Page) -> bool:
    """At least two horizontal and two vertical rules: the minimum for a ruled table."""
    h = v = 0
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                a, b = item[1], item[2]
                w, ht = abs(a.x - b.x), abs(a.y - b.y)
            elif item[0] == "re":
                w, ht = item[1].width, item[1].height
            else:
                continue
            h += ht < 2 and w > 20
            v += w < 2 and ht > 10
    return h >= 2 and v >= 2


def table_rows(page: pymupdf.Page, spans: list[Span], page_no: int) -> tuple[list[Line], set[int]]:
    """Ruled tables: one line per row, cells joined with " | ". Returns rows and used spans."""
    rows, used = [], set()
    if page.rotation or not has_grid(page):  # find_tables is slow; skip pages without rulings
        return rows, used
    for table in page.find_tables().tables:
        if table.row_count < 2 or table.col_count < 2:
            continue
        tb = pymupdf.Rect(table.bbox)
        inside = [i for i, s in enumerate(spans) if tb.contains(pymupdf.Point(s.x0 + 1, s.cy))]
        for row in table.rows:
            cells = [pymupdf.Rect(c) for c in row.cells if c]
            parts, row_spans, notes = [], [], []
            for cell in sorted(cells, key=lambda c: c.x0):
                ids = [i for i in inside if i not in used
                       and cell.contains(pymupdf.Point(spans[i].x0 + 1, spans[i].cy))]
                used.update(ids)
                cell_spans = [spans[i] for i in ids]
                if not cell_spans:
                    continue
                cell_lines = [finish(ln) for ln in group_lines(cell_spans, page_no)]
                for ln in cell_lines:
                    notes.extend(ln.notes)
                parts.append(join_text([ln.text for ln in cell_lines]))
                row_spans.extend(cell_spans)
            if parts:
                line = Line(page_no, row_spans)
                line.text, line.notes, line.kind = " | ".join(parts), notes, "table"
                rows.append(line)
        used.update(inside)
    return rows, used


def join_text(parts: list[str]) -> str:
    """Join wrapped lines: keep hyphenated words whole, otherwise one space."""
    out = ""
    for p in parts:
        if not p:
            continue
        if out.endswith("-") and out[-2:-1].isalnum() and p[:1].isalnum():
            out += p
        else:
            out = f"{out} {p}" if out else p
    return out


def read_pdf(
    path: Path, tables: bool = True, skip: dict[int, list[pymupdf.Rect]] | None = None
) -> list[Page]:
    """skip: page number → regions whose text is dropped (figures transcribed by hand)."""
    doc = pymupdf.open(path)
    raw: list[tuple[pymupdf.Page, list[Span], list[Line], list[Line]]] = []
    for page in doc:
        no = page.number + 1
        spans = page_spans(page)
        regions = (skip or {}).get(no, [])
        spans = [s for s in spans if not any(r.contains(pymupdf.Point(s.x0 + 1, s.cy))
                                             for r in regions)]
        rows, used = table_rows(page, spans, no) if tables else ([], set())
        free = [s for i, s in enumerate(spans) if i not in used]
        raw.append((page, spans, group_lines(free, no), rows))

    heights = [p.rect.height for p, *_ in raw]
    drop = header_keys([lines for _, _, lines, _ in raw], heights)
    pages = []
    for (page, _, lines, rows), h in zip(raw, heights, strict=True):
        kept = []
        for ln in lines:
            in_band = ln.y1 < 0.11 * h or ln.y0 > 0.9 * h
            text = clean("".join(s.text for s in ln.spans))
            if in_band and (band_key(ln) in drop or PAGE_NUMBER.match(text)):
                continue
            kept.append(ln)
        spans = [s for ln in kept for s in ln.spans]
        body, notes = split_footnotes(kept, h)
        body = [finish(ln) for ln in body] + rows
        body.sort(key=lambda ln: (round(ln.y0), ln.x0))
        lines = [ln for ln in body if ln.text]
        pages.append(Page(page.number + 1, page.rect.width, h, lines, notes, spans))
    return pages
