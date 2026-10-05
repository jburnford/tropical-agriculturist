#!/usr/bin/env python3
"""
Score heading classification against the printed TOC of the 1942-45 quarterlies.

This is the only ground truth in the corpus, and it is an *upper bound*: these
issues are the most structured part of the run, so accuracy here says little
about the 1917-41 monthlies where headings are least reliable.

TOC and body titles do not agree verbatim -- the TOC prints "The Montane
Grasslands (Patnas) of Ceylon-An Ecological Study with reference to
Afforestation-I" where the body heading reads "AN ECOLOGICAL STUDY WITH
REFERENCE TO AFFORESTATION-I". So a miss may be a classifier error or merely a
matcher error, and the two are reported separately rather than blended.
"""
import json, re, sys, pathlib, difflib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from toc import parse_toc

ROOT = pathlib.Path('/home/jic823/tropical/output')

def norm(s):
    s = re.sub(r'[^a-z0-9 ]', ' ', s.lower())
    return ' '.join(s.split())

def best(target, cands):
    t = norm(target)
    if not t: return 0.0, None
    bs, bc = 0.0, None
    for c in cands:
        n = norm(c)
        if not n: continue
        r = difflib.SequenceMatcher(None, t, n).ratio()
        # substring containment scores highly: body headings are often a
        # fragment of the fuller TOC title
        if n in t or t in n:
            r = max(r, 0.90)
        if r > bs: bs, bc = r, c
    return bs, bc

labels = {json.loads(l)['document']: json.loads(l) for l in open('labels_val.jsonl')}

tot_toc = tot_hit = tot_near = 0
rows = []
for doc, rec in sorted(labels.items()):
    md = next(ROOT.glob(f'{doc}*/*/*.md'), None)
    if not md: continue
    toc = parse_toc(md.read_text(encoding='utf-8', errors='replace'))
    if len(toc) < 3: continue           # no usable TOC (bound vols, monthlies)
    arts = [h['title'] for h in rec['headings'] if h['label'] == 'ARTICLE']
    hit = near = 0
    misses = []
    for e in toc:
        s, c = best(e['title'], arts)
        if s >= 0.75: hit += 1
        elif s >= 0.45: near += 1; misses.append((e['title'][:44], c, round(s,2)))
        else: misses.append((e['title'][:44], c, round(s,2)))
    tot_toc += len(toc); tot_hit += hit; tot_near += near
    rows.append((doc, len(toc), len(arts), hit, near, misses))

print(f"{'document':<50} {'TOC':>4} {'ART':>4} {'hit':>4} {'near':>5}")
for doc, nt, na, h, n, _ in rows:
    print(f"  {doc[:48]:<48} {nt:>4} {na:>4} {h:>4} {n:>5}")
print()
print(f"TOC entries matched by an ARTICLE heading: {tot_hit}/{tot_toc} "
      f"({100*tot_hit/max(tot_toc,1):.0f}%)  +{tot_near} near-matches "
      f"({100*(tot_hit+tot_near)/max(tot_toc,1):.0f}% incl. near)")
print()
print("=== unmatched TOC entries (classifier miss OR matcher miss) ===")
shown = 0
for doc, *_ , misses in rows:
    for m in misses:
        if shown < 14:
            print(f"  {m[2]:<5} {m[0]:<44} -> best body heading: {str(m[1])[:40]}")
            shown += 1
