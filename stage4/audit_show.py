# Show corpus text vs Tesseract words for audit rows. Usage: audit_show.py CORPUS AUDIT TAG:PAGE...
import sys, re, pathlib
sys.path.insert(0, "/scratch/jic823/tropical")
from repair_compare import load
corpus, audit = sys.argv[1], sys.argv[2]
for a in sys.argv[3:]:
    t, p = a.rsplit(":", 1); p = int(p)
    txt = load(pathlib.Path(corpus, t))[0][p]
    tw = pathlib.Path(audit, t, f"p{p:04d}.txt").read_text()
    c = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))
    print(f"#### {t[:30]} p{p}\n  TEXT: {c(txt)[:330]}\n  TESS: {tw[:330]}")
