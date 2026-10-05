#!/usr/bin/env python3
"""Find issue mastheads: a page whose opening carries Vol. <roman> + No. <n> (+ month year)."""
import csv, re, pathlib, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pages import split_pages, DATE, iso
ROOT = pathlib.Path.home() / "tropical/output_v6"
VOL = re.compile(r"\bVOL(?:UME)?\.?\s*([LXVIC]{1,8})\b\.?", re.I)
NO = re.compile(r"\bNO\.?\s*(\d{1,2}|[IVX]{1,4})\b\.?", re.I)
ROM = dict(I=1, V=5, X=10, L=50, C=100)
def rom(s):
    s = s.upper(); v = 0
    for a, b in zip(s, s[1:] + " "):
        v += -ROM[a] if b != " " and ROM.get(b, 0) > ROM[a] else ROM[a]
    return v
def scan(doc):
    md = next((ROOT / doc).glob("*/*.md"))
    pages, _ = split_pages(md.read_text(encoding="utf-8", errors="replace"))
    out = []
    for i, p in enumerate(pages):
        head = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", p[:700])
        # A citation ("(From the Indian Agriculturist, Vol. XXXV., No. 6, June, 1910.)") is not a masthead.
        head = "\n".join(l for l in head.split("\n") if not re.search(r"\bFrom\b|^\s*\(|\(\s*\*?[A-Z].{0,60}Vol", l))
        v, n = VOL.search(head), NO.search(head)
        if v and n:
            d = DATE.search(head[n.start() - 120 if n.start() > 120 else 0:n.end() + 120])
            no = n.group(1); no = int(no) if no.isdigit() else rom(no)
            out.append((i, rom(v.group(1)), no, iso(d) if d else ""))
    return out
if __name__ == "__main__":
    docs = sys.argv[1:] or sorted(x.name for x in ROOT.glob("vol*"))
    for doc in docs:
        hits = scan(doc)
        print(f"{doc[:40]:40} {len(hits):3} " + " ".join(f"p{i}:v{v}n{n}{('@'+d) if d else ''}" for i, v, n, d in hits[:14]))
