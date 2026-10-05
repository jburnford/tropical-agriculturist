#!/usr/bin/env python3
"""pg.py TAGPREFIX PAGE[-PAGE] [chars]: print pages of a doc from output_v6."""
import re, sys, pathlib
ROOT = pathlib.Path.home() / "tropical/output_v6"
MARK = re.compile(r'\n\n(\d+)-{40,}\n\n')
d = next(ROOT.glob(sys.argv[1] + '*'))
t = next(d.glob('*/*.md')).read_text(encoding='utf-8', errors='replace')
parts = MARK.split(t); ps = [parts[0]] + parts[2::2]
a, _, b = sys.argv[2].partition('-'); a = int(a); b = int(b or a)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
for i in range(a, b + 1):
    print(f"===== {d.name} p{i}/{len(ps)}"); print(ps[i][:n])
