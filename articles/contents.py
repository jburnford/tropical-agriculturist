#!/usr/bin/env python3
"""
Gold article list from printed per-issue contents tables (1928-1945 covers, quarterlies).

A contents page opens with the issue masthead ("VOL. XCIII PERADENIYA, AUGUST, 1939
No. 2") followed by department headings (## ORIGINAL ARTICLE) and tables whose rows
pair a title cell (often "Title by Author, quals .. .. .") with a start-page cell.
The issue is taken from the contents page's own masthead, not from page_issue.tsv,
because covers are sometimes bound together away from their issues (vol096 p487-497).

Writes gold_contents.tsv: doc, contents_page, volume, issue, department, title, author, folio.
"""
import csv, html, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pages import split_pages, DATE, iso
from mastheads import VOL, rom

ROOT = pathlib.Path.home() / "tropical/output_v6"
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
HEAD = re.compile(r"^#{1,4}\s+(.+)$", re.M)
BY = re.compile(r",?\s*\bby\s+((?:the\s+Hon'?ble\s+)?(?:(?:Mr|Dr|Sir|Prof)\.?\s+)*(?:[A-Z][a-z]*\.?\s*|(?:de|van|von|la)\s+)*[A-Z][\w'-]+,.*|(?:the\s+Hon'?ble\s+)?(?:[A-Z]\.\s*)+[A-Z][\w'-]+.*)$")
TAG = re.compile(r"<[^>]+>")


def clean(s):
    s = html.unescape(TAG.sub("", s))
    s = re.sub(r"(\s*\.){2,}\s*$|\s*\.\s*\.\s*\.?\s*$", "", s.strip())
    return re.sub(r"\s+", " ", s).strip(" .")


def parse_page(p):
    """[(department, title, author, folio)] from one contents page, in reading order."""
    out, dept = [], ""
    pos = 0
    # Walk headings and tables in document order.
    tokens = sorted([(m.start(), "h", m.group(1)) for m in HEAD.finditer(p)] +
                    [(m.start(), "r", m.group(1)) for m in TROW.finditer(p)])
    for _, kind, val in tokens:
        if kind == "h":
            h = clean(val)
            if not re.search(r"Tropical Agriculturist|^VOL\b|PERADENIYA", h, re.I):
                dept = h
            continue
        cells = [clean(c) for c in CELL.findall(val)]
        for k in range(len(cells) - 1):             # rows may hold two title/page pairs
            t, f = cells[k], cells[k + 1]
            if re.fullmatch(r"\d{1,3}", f) and re.search(r"[A-Za-z]{3}", t) and not re.fullmatch(r"\d{1,3}", t):
                m = BY.search(t)
                title, author = (t[:m.start()].strip(" ,"), m.group(1).strip()) if m else (t, "")
                out.append((dept, title, author, int(f)))
    return out


def main():
    w = csv.writer(open("gold_contents.tsv", "w"), delimiter="\t", lineterminator="\n")
    w.writerow(["doc", "contents_page", "volume", "issue", "department", "title", "author", "folio"])
    for d in sorted(ROOT.glob("vol*")):
        md = next(d.glob("*/*.md"))
        ps, _ = split_pages(md.read_text(encoding="utf-8", errors="replace"))
        for i, p in enumerate(ps):
            top = TAG.sub(" ", p[:600])
            v, dt = VOL.search(top), DATE.search(top)
            if not (v and dt and re.search(r"Editorial|Page", p[:4000])) or re.search(r"\bINDEX\b", p[:1500]):
                continue
            rows = parse_page(p)
            if len(rows) < 3:
                continue
            folios = [r[3] for r in rows]
            # Contents run in page order; a table of something else (returns, prices) does not.
            if sum(b >= a for a, b in zip(folios, folios[1:])) < 0.8 * (len(folios) - 1):
                continue
            for dept, title, author, f in rows:
                w.writerow([d.name, i, rom(v.group(1)), iso(dt)[:7], dept, title, author, f])


if __name__ == "__main__":
    main()
