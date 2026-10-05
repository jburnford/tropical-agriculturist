#!/usr/bin/env python3
"""
Validate one Chandra output directory. Exit 0 = PASS, 1 = FAIL.

Written because two corpus runs went out without the flags that make the
output usable, and nothing in the pipeline could tell. Each check here fails
if its flag was missing:

  * page markers   -- --paginate_output writes "N" + 48 dashes between pages.
                      Without it there are none. Must be exactly 1..pages-1.
  * folio coverage -- --include-headers-footers keeps the running head and the
                      folio. Without it almost no page begins or ends with a
                      page number. Must be >= FOLIO_MIN of pages.
  * token cap      -- pages whose token_count reached --max-output-tokens were
                      cut off mid-page. Reported, not failed: a few may be
                      genuine repetition loops.

Usage: check_doc.py DEST EXPECTED_PAGES MAX_OUTPUT_TOKENS
Prints one tab-separated line: status tag pages markers folio_frac capped reason
"""
import json, pathlib, re, sys

FOLIO_MIN = 0.50
MARK = re.compile(r"^(\d+)-{48}\s*$", re.M)
# A 1-4 digit number at the very start or end of a line, allowing the
# markdown/typographic wrapping Chandra puts round running heads:
#   "124[MARCH, 1919."   "MARCH, 1919.]125"   "## 468 THE TROPICAL ..."   "62"
LEAD = re.compile(r"^[#*\s\[|]*(\d{1,4})(?!\d)(?![.,]\d)")
TRAIL = re.compile(r"(?:(?<![\d.,])|(?<=[A-Za-z][.,]))(\d{1,4})[\]|*\s]*$")
BRACKET = re.compile(r"(?:(?<![\d.,])|(?<=[A-Za-z][.,]))(\d{1,4})\.?\s*\[|\]\s*(\d{1,4})(?![\d.,]\d)")
YEAR = range(1800, 1951)


def has_folio(lines):
    for ln in lines:
        for rx in (LEAD, TRAIL, BRACKET):
            for m in rx.finditer(ln):
                v = int(next(g for g in m.groups() if g))
                if v not in YEAR:
                    return True
    return False


def main(dest, expected, max_out):
    dest = pathlib.Path(dest)
    tag = dest.name
    out = lambda st, n=0, mk=0, ff=0.0, cap=0, why="": (
        print(f"{st}\t{tag}\t{n}\t{mk}\t{ff:.2f}\t{cap}\t{why}"), 0 if st == "PASS" else 1)[1]

    mds = list(dest.rglob("*.md"))
    metas = list(dest.rglob("*_metadata.json"))
    if len(mds) != 1 or len(metas) != 1:
        return out("FAIL", why=f"expected 1 md + 1 metadata, found {len(mds)} + {len(metas)}")
    text = mds[0].read_text(errors="replace")
    meta = json.load(open(metas[0]))
    n = int(meta["num_pages"])
    capped = sum(int(p["token_count"]) >= max_out for p in meta["pages"])

    if n != expected:
        return out("FAIL", n, cap=capped, why=f"num_pages {n} != expected {expected}")

    marks = [int(x) for x in MARK.findall(text)]
    if marks != list(range(1, n)):
        return out("FAIL", n, len(marks), cap=capped,
                   why=f"page markers {len(marks)} != {n - 1} (is --paginate_output set?)")

    pages = MARK.split(text)[::2]          # split keeps the captured numbers; drop them
    body = [[l for l in p.splitlines() if l.strip()] for p in pages]
    body = [b for b in body if b]          # blank pages (plates, versos) carry no folio
    with_folio = sum(has_folio(b[:3] + b[-3:]) for b in body)
    frac = with_folio / max(len(body), 1)
    if frac < FOLIO_MIN:
        return out("FAIL", n, len(marks), frac, capped,
                   f"folio on {frac:.0%} of pages < {FOLIO_MIN:.0%} (is --include-headers-footers set?)")

    return out("PASS", n, len(marks), frac, capped)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
