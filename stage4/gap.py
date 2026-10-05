# Pages in the audit's blind spot: Tesseract 3-14 content words, corpus >= 50 words, no stage4 marker, contrast < 35.
import sys, re, pathlib, collections
sys.path.insert(0, "/scratch/jic823/tropical")
from audit_compare import text_words, content, recall
MARK = re.compile(r"^\d+-{48}\s*$", re.M)
con = {}
for l in open("stage4/ink.tsv"):
    x = l.split("\t")
    if x[0] != "tag": con[(x[0], int(x[1]))] = int(x[5])
n = collections.Counter(); out = []
for d in sorted(pathlib.Path("output_v5").glob("vol*")):
    pages = MARK.split(next(d.rglob("*.md")).read_text(errors="replace"))
    for p, txt in enumerate(pages):
        if "stage4:" in txt: continue
        tw = content(pathlib.Path("stage4/audit", d.name, f"p{p:04d}.txt").read_text().lower().split())
        xw = text_words(txt)
        if 3 <= len(tw) < 15 and len(xw) >= 50:
            c = con[(d.name, p)]
            b = "c<20" if c < 20 else "c20-34" if c < 35 else "c>=35"
            n[b] += 1
            if c < 35: out.append(f"{d.name}\t{p}\t{c}\t{len(tw)}\t{len(xw)}\t{recall(tw, xw):.2f}")
print(dict(n))
open("stage4/gap.tsv", "w").write("\n".join(out) + "\n")
