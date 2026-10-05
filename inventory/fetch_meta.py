#!/usr/bin/env python3
import urllib.parse
"""Fetch IA metadata for every Tropical Agriculturist item.

Writes one JSON line per item to ia_meta.jsonl. Resumable: items already
present in the output file are skipped. Concurrency is kept low to stay
polite to archive.org.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import urllib.request

OUT = 'ia_meta.jsonl'
idents = [d['identifier'] for d in json.load(open('ia_all.json'))]

done = set()
if os.path.exists(OUT):
    with open(OUT) as fh:
        for line in fh:
            try:
                done.add(json.loads(line)['identifier'])
            except Exception:
                pass
todo = [i for i in idents if i not in done]
print(f'{len(done)} already fetched, {len(todo)} to go', flush=True)

def fetch(ident):
    url = 'https://archive.org/metadata/' + urllib.parse.quote(ident)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                d = json.load(r)
            md = d.get('metadata', {}) or {}
            return {
                'identifier': ident,
                'title':   md.get('title'),
                'volume':  md.get('volume'),
                'year':    md.get('year'),
                'date':    md.get('date'),
                'language':md.get('language'),
                'collection': md.get('collection'),
                'imagecount': md.get('imagecount'),
                'sponsor': md.get('sponsor'),
                'contributor': md.get('contributor'),
                'scanningcenter': md.get('scanningcenter'),
                'files': [
                    {'name': f['name'], 'format': f.get('format'), 'size': int(f.get('size', 0) or 0)}
                    for f in d.get('files', [])
                ],
            }
        except Exception as e:
            if attempt == 3:
                return {'identifier': ident, 'error': str(e)}
            time.sleep(2 * (attempt + 1))

with open(OUT, 'a') as fh, ThreadPoolExecutor(max_workers=5) as ex:
    for n, rec in enumerate(ex.map(fetch, todo), 1):
        fh.write(json.dumps(rec) + '\n')
        if n % 25 == 0:
            fh.flush()
            print(f'  {n}/{len(todo)}', flush=True)
print('done', flush=True)
