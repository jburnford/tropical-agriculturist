#!/usr/bin/env python3
"""Per-document survey of output_v6: pages, index/contents pages, heading levels, title-page 'Vol.' lines."""
import re, sys, pathlib, collections
ROOT = pathlib.Path.home() / "tropical/output_v6"
MARK = re.compile(r'\n\n(\d+)-{40,}\n\n')

def pages(md):
    t = md.read_text(encoding='utf-8', errors='replace')
    parts = MARK.split(t)
    ps = [parts[0]] + parts[2::2]
    nums = [int(x) for x in parts[1::2]]
    assert nums == list(range(1, len(ps))), md
    return ps

for d in sorted(ROOT.glob('vol*')):
    md = next(d.glob('*/*.md'))
    ps = pages(md)
    idx = [i for i, p in enumerate(ps) if re.search(r'^#*\s*(GENERAL\s+)?(INDEX|CONTENTS)\b', p, re.M | re.I)]
    hl = collections.Counter(len(m.group(1)) for p in ps for m in re.finditer(r'^(#{1,6}) ', p, re.M))
    print(f"{d.name[:48]:48} {len(ps):5} idx={idx[:8]}{'…' if len(idx)>8 else ''} h={dict(sorted(hl.items()))}")
