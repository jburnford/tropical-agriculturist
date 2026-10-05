#!/usr/bin/env python3
"""Build a canonical volume-level inventory of The Tropical Agriculturist.

Reconciles Internet Archive holdings against local copies on the E: drive.
"""
import json, re, csv, collections

ROMAN = {'i':1,'v':5,'x':10,'l':50,'c':100,'d':500,'m':1000}

def roman_to_int(s):
    s = s.lower()
    if not s or any(ch not in ROMAN for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total

def volume_of(doc):
    """Best-effort volume number for an IA item."""
    ident, title = doc['identifier'], str(doc.get('title') or '')
    vol = doc.get('volume')

    # 1. explicit numeric volume metadata
    if vol is not None:
        m = re.search(r'(\d+)', str(vol))
        if m and str(vol).strip().isdigit():
            return int(m.group(1))
        m = re.search(r'v\.?\s*(\d+)', str(vol), re.I)
        if m:
            return int(m.group(1))

    # 2. per-issue identifiers: tropical-agriculturist_1915-06_44_6
    m = re.match(r'tropical-agriculturist_[a-z0-9-]+?_(\d{2,3})(?:_|$)', ident)
    if m:
        return int(m.group(1))

    # 3. roman numerals in title: "Vol-xli", "Vol LXIII"
    m = re.search(r'vol[\s.-]*([ivxlcdm]+)\b', title, re.I)
    if m:
        return roman_to_int(m.group(1))

    # 4. Cornell-style: tropicalagricult{vol}{year}ceyl / tropicalagricul{vol}{yyyy}ceyl
    m = re.match(r'tropicalagricul(\d{2})(\d{4})ceyl', ident)
    if m:
        return int(m.group(1))
    m = re.match(r'tropicalagricult(\d{1,2})(\d{2})ceyl$', ident)
    if m:
        return int(m.group(1))

    # 5. lbg.630.5.tag.v.37 / tropicalagricult0054unse
    m = re.search(r'tag\.v\.(\d+)', ident)
    if m:
        return int(m.group(1))
    m = re.search(r'tropicalagricult(\d{4})unse', ident)
    if m:
        return int(m.group(1))
    return None

def family(ident):
    if ident.startswith('tdl.'):                       return 'tdl'
    if ident.startswith('tropical-agriculturist_'):    return 'per-issue'
    if ident.startswith('lbg.'):                       return 'lbg'
    if ident.startswith(('dli.ernet', 'in.ernet.dli')):return 'dli'
    if ident.startswith('tropicalagricul'):            return 'cornell'
    return 'other'

def is_index(doc):
    return 'index' in doc['identifier'].lower() or 'index' in str(doc.get('title') or '').lower()

docs = json.load(open('ia_all.json'))
rows = []
for d in docs:
    rows.append({
        'identifier': d['identifier'],
        'family':     family(d['identifier']),
        'volume':     volume_of(d),
        'year':       d.get('year'),
        'imagecount': d.get('imagecount'),
        'is_index':   is_index(d),
        'title':      str(d.get('title') or '')[:120],
    })

with open('ia_items.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

nov = [r for r in rows if r['volume'] is None]
print(f'IA items: {len(rows)};  volume resolved: {len(rows)-len(nov)};  unresolved: {len(nov)}')
print('\nUnresolved sample:')
for r in nov[:12]:
    print('  ', r['identifier'][:60], '|', r['year'], '|', r['title'][:50])

vols = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    if r['volume'] and not r['is_index']:
        vols[r['volume']][r['family']] += 1
print(f'\nDistinct volumes on IA (excl. index-only): {len(vols)}')
print('Volume range:', min(vols), '-', max(vols))
