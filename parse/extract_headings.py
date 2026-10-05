#!/usr/bin/env python3
"""
Dump every heading in the corpus with enough local context to classify it.

64,004 headings across 254 documents. The classifier has to decide, for each
one, whether it starts a new article or continues the previous one -- which
cannot be read off the heading level, because the level's meaning varies by
volume (vol043 puts article titles at ##, vol003 puts 499 of them at ####,
vol085 uses ## for both a department and a mid-article subsection).

What does carry signal is the *sequence*: ABSTRACT / INTRODUCTION / CLIMATE
following a long title are obviously its subsections, and the model can see
that if it is given consecutive headings together. So headings are emitted in
document order and classified in ordered batches, not independently.
"""
import json, re, pathlib, argparse

HEAD = re.compile(r'^(#{1,6})\s+(\S.*?)\s*$')

def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'[*_`]', '', s)).strip()

def headings(md):
    lines = md.read_text(encoding='utf-8', errors='replace').split('\n')
    hs, off = [], 0
    for i, l in enumerate(lines):
        m = HEAD.match(l)
        if m:
            hs.append({'line': i, 'level': len(m.group(1)),
                       'title': clean(m.group(2)), 'offset': off})
        off += len(l) + 1
    out = []
    for n, h in enumerate(hs):
        start = h['line'] + 1
        end = hs[n + 1]['line'] if n + 1 < len(hs) else len(lines)
        body = '\n'.join(lines[start:end]).strip()
        # strip HTML so the snippet is readable prose, not table markup
        prose = re.sub(r'<[^>]+>', ' ', body)
        prose = re.sub(r'\s+', ' ', prose).strip()
        out.append({'seq': n, 'level': h['level'], 'title': h['title'],
                    'words': len(body.split()), 'char_offset': h['offset'],
                    'snippet': ' '.join(prose.split()[:35])})
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/home/jic823/tropical/output')
    ap.add_argument('--out',  default='/home/jic823/tropical/parse/headings.jsonl')
    a = ap.parse_args()

    root = pathlib.Path(a.root)
    n_doc = n_head = 0
    with open(a.out, 'w') as fh:
        for md in sorted(root.rglob('*.md')):
            hs = headings(md)
            if not hs: continue
            fh.write(json.dumps({'document': md.stem, 'headings': hs}) + '\n')
            n_doc += 1; n_head += len(hs)
    print(f"{n_doc} documents, {n_head:,} headings -> {a.out}")
