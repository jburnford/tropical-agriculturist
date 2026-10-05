#!/usr/bin/env python3
"""
Segment Chandra markdown into article-level records.

Design note, learned the hard way: **heading level does not identify an
article.** It varies by volume, not merely by era -- vol043 (1915) puts article
titles at `##`, vol003 (1883) puts 499 of them at `####`, and vol085 (1935)
uses `##` for both a department name (EDITORIAL) and a mid-article subsection
(FURNACE). Any rule of the form "## starts an article" is wrong somewhere.

So this does not try to decide article-vs-subsection from the level. It emits
*every* heading as a segment carrying its level, its parent chain and its text,
and then labels each one with a heuristic `kind`. Downstream (the knowledge
graph) can filter on kind or word count; nothing is discarded, and a wrong
guess is recoverable because the hierarchy is preserved.

Page numbers are not available: Chandra concatenates pages with no boundary
marker in .md, .html or metadata.json, so provenance is (file, char_offset).
"""
import json, re, sys, pathlib, argparse

HEAD = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
# Department / standing-section names that recur as headings across the run.
DEPARTMENTS = {
    'EDITORIAL', 'ORIGINAL ARTICLES', 'DEPARTMENTAL AND OTHER NOTES',
    'MEETINGS, CONFERENCES, &C.', 'RETURNS', 'CORRESPONDENCE',
    'REVIEWS', 'NOTES AND COMMENTS', 'MARKET RATES', 'TO CORRESPONDENTS',
}

def clean(s):
    s = re.sub(r'[*_`]', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def segment(md_path):
    text = md_path.read_text(encoding='utf-8', errors='replace')
    lines = text.split('\n')

    heads, offset = [], 0
    for i, line in enumerate(lines):
        m = HEAD.match(line)
        if m:
            heads.append({'line': i, 'level': len(m.group(1)),
                          'title': clean(m.group(2)), 'offset': offset})
        offset += len(line) + 1

    segs = []
    for n, h in enumerate(heads):
        start = h['line'] + 1
        end = heads[n + 1]['line'] if n + 1 < len(heads) else len(lines)
        body = '\n'.join(lines[start:end]).strip()
        words = len(body.split())

        parents = []
        for prev in reversed(heads[:n]):
            if prev['level'] < h['level'] and (not parents or prev['level'] < parents[-1][0]):
                parents.append((prev['level'], prev['title']))
            if prev['level'] == 1:
                break
        parents.reverse()

        title_u = h['title'].upper().rstrip('.')
        if title_u in DEPARTMENTS:
            kind = 'department'
        elif words < 40:
            kind = 'heading_only'      # a label, or a TOC entry, or a stub
        elif words < 250:
            kind = 'note'              # the journal's short compiled items
        else:
            kind = 'article'

        segs.append({
            'seq': n, 'level': h['level'], 'title': h['title'],
            'parents': [p[1] for p in parents],
            'kind': kind, 'words': words, 'chars': len(body),
            'char_offset': h['offset'], 'text': body,
        })
    return segs

def doc_meta(tag):
    m = re.match(r'vol(\d+)', tag)
    vol = int(m.group(1)) if m else None
    iss = (re.search(r'_iss(\d+)_', tag) or [None, None])[1] if '_iss' in tag else None
    dm = re.search(r'agriculturist-(\d{4})-(\d{2})', tag)
    if dm and 1881 <= int(dm.group(1)) <= 1945:
        year, month = int(dm.group(1)), int(dm.group(2))
    else:
        ym = re.search(r'-(\d{4})-\d+-\d+$', tag)
        year = int(ym.group(1)) if ym else (1880 + vol if vol else None)
        month = None
    return {'volume': vol, 'issue': iss, 'year': year, 'month': month}

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('docs', nargs='+')
    ap.add_argument('--outdir', default='/home/jic823/tropical/parse/out')
    ap.add_argument('--listing', action='store_true')
    a = ap.parse_args()

    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    root = pathlib.Path('/home/jic823/tropical/output')

    for d in a.docs:
        md = next(root.glob(f'{d}*/*/*.md'), None)
        if not md:
            print(f'!! no markdown for {d}'); continue
        tag = md.stem
        segs = segment(md)
        meta = doc_meta(tag)
        rec = {'document': tag, **meta, 'segments': segs}
        (out / f'{tag}.json').write_text(json.dumps(rec, indent=1))

        kinds = {}
        for s in segs: kinds[s['kind']] = kinds.get(s['kind'], 0) + 1
        print(f"\n=== {tag}")
        print(f"    vol {meta['volume']} {meta['year']}"
              + (f"-{meta['month']:02d}" if meta['month'] else '')
              + (f" iss{meta['issue']}" if meta['issue'] else '')
              + f"  |  {len(segs)} segments  {kinds}")
        if a.listing:
            for s in segs:
                if s['kind'] in ('article', 'note'):
                    ind = '  ' * (s['level'] - 1)
                    print(f"    {s['words']:>5}w  {ind}{s['title'][:78]}")
