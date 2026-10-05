#!/usr/bin/env python3
"""
Entries from the printed subject INDEX of each bound volume: (entry, folio) pairs.

Index rows are "Ant and Man .. .. | 313", "Apples .. .. | 24, 103", continuation rows
"—, Remedies for" (head word of the previous entry implied), cross references
"[See Insecticides]" (dropped), and "[Sup.]" for Supplement pages (kept as a flag:
the Supplement has its own pagination). One output row per (entry, folio).

Writes gold_index.tsv: doc, index_page, volume, entry, folio, supplement
"""
import csv, html, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pages import split_pages
ROOT = pathlib.Path.home() / "tropical/output_v6"
TROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG = re.compile(r"<[^>]+>")
NUMS = re.compile(r"(\d{1,4}(?:\s*(?:,|&|and)\s*\d{1,4})*)\s*\.?\s*$")


def rows_of(p):
    """Yield entry strings with their page lists from one index page (tables or plain lines)."""
    cells = []
    for tr in TROW.findall(p):
        cs = [re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", c))).strip() for c in CELL.findall(tr)]
        cs = [c for c in cs if c]
        # pair "entry" cells with following page cells; a cell may also carry both.
        k = 0
        while k < len(cs):
            c = cs[k]
            if k + 1 < len(cs) and re.fullmatch(r"[\d,\s&and]+", cs[k + 1]) and not re.fullmatch(r"[\d,\s&and]+", c):
                cells.append(c + " " + cs[k + 1]); k += 2
            else:
                cells.append(c); k += 1
    if not cells:                                   # plain-text indexes
        cells = [l.strip() for l in TAG.sub(" ", p).split("\n") if l.strip()]
    return cells


def main():
    vol_of = {(r["doc"], int(r["page"])): (r["volume"], r["part"]) for r in csv.DictReader(open("page_issue.tsv"), delimiter="\t")}
    w = csv.writer(open("gold_index.tsv", "w"), delimiter="\t", lineterminator="\n")
    w.writerow(["doc", "index_page", "volume", "entry", "folio", "supplement"])
    n = 0
    for d in sorted(ROOT.glob("vol*")):
        md = next(d.glob("*/*.md"))
        ps, _ = split_pages(md.read_text(encoding="utf-8", errors="replace"))
        for i, p in enumerate(ps):
            vol, part = vol_of[(d.name, i)]
            if part != "index":
                continue
            head = ""
            for c in rows_of(p):
                c = re.sub(r"\[See[^\]]*\]", "", c, flags=re.I).strip()
                sup = bool(re.search(r"\[Sup", c, re.I))
                c = re.sub(r"\[Sup[^\]]*\]?", "", c, flags=re.I)
                m = NUMS.search(c)
                if not m:
                    continue
                entry = re.sub(r"(\s*\.){2,}|\s*…+", " ", c[:m.start()]).strip(" .,")
                if not re.search(r"[A-Za-z]{3}", entry):
                    continue
                if re.match(r"^[—–-]+", entry):          # "—, Remedies for" continues the last head word
                    entry = head + " " + entry.lstrip("—–- ,")
                else:
                    head = entry.split(",")[0]
                for f in re.findall(r"\d{1,4}", m.group(1)):
                    if 1 <= int(f) <= 1500:
                        w.writerow([d.name, i, vol, entry, int(f), int(sup)]); n += 1
    print(n, "rows", file=sys.stderr)


if __name__ == "__main__":
    main()
