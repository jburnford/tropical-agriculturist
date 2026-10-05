#!/usr/bin/env python3
"""heads.py TAGPREFIX [n]: first and last non-empty line of n evenly spaced pages."""
import re, sys, pathlib
ROOT = pathlib.Path.home() / "tropical/output_v6"
MARK = re.compile(r'\n\n(\d+)-{40,}\n\n')
d = next(ROOT.glob(sys.argv[1] + '*'))
t = next(d.glob('*/*.md')).read_text(encoding='utf-8', errors='replace')
parts = MARK.split(t); ps = [parts[0]] + parts[2::2]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
print('==', d.name, len(ps))
for i in range(len(ps)//(n+1), len(ps), max(1, len(ps)//(n+1))):
    ls = [l for l in ps[i].split('\n') if l.strip()]
    if ls: print(f"  p{i:<4} TOP {ls[0][:70]!r:74} BOT {ls[-1][-50:]!r}")
