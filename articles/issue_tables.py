#!/usr/bin/env python3
"""Find printed 'Number | Month | Pages' tables (issue -> folio range) in bound documents."""
import re, pathlib, sys, html
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pages import split_pages
ROOT = pathlib.Path.home() / "tropical/output_v6"
MON = "january february march april may june july august september october november december".split()
ROW = re.compile(r"<tr>\s*<td[^>]*>\s*(\d{1,2}|[IVX]{1,4})\.?\s*</td>\s*<td[^>]*>\s*([A-Za-z]+)\.?\s*</td>\s*<td[^>]*>\s*(\d{1,4})\s*[-—–]+\s*(\d{1,4})\s*\.?</td>", re.I)
def tables(doc):
    md = next((ROOT / doc).glob("*/*.md"))
    ps, _ = split_pages(md.read_text(encoding="utf-8", errors="replace"))
    out = []
    for i, p in enumerate(ps):
        rows = [(m.group(1), m.group(2).lower()[:3], int(m.group(3)), int(m.group(4))) for m in ROW.finditer(p)]
        rows = [r for r in rows if r[1] in [x[:3] for x in MON]]
        if len(rows) >= 4:
            out.append((i, [(MON[[x[:3] for x in MON].index(r[1])][:3], r[2], r[3]) for r in rows]))
    return out
if __name__ == "__main__":
    for d in sorted(ROOT.glob("vol*")):
        if "_iss" in d.name or "tropical-agriculturist-19" in d.name: continue
        t = tables(d.name)
        if t: print(f"{d.name[:36]:36}", "; ".join(f"p{i}:" + ",".join(f"{m}{a}-{b}" for m, a, b in rows) for i, rows in t))
