#!/usr/bin/env python3
"""Reconcile Internet Archive holdings of The Tropical Agriculturist.

Reads ia_meta.jsonl (full IA metadata, one item per line) and emits:

  ta_items.csv      every IA item, with volume/issue/year resolved and the
                    best available PDF identified
  ta_manifest.csv   the de-duplicated download set: one preferred source per
                    volume (or per issue, where only issue scans exist)
  coverage.txt      human-readable coverage and gap report

Source preference, best first:
  1. volume-level scan from a library digitisation (cornell / lbg / dli)
  2. volume-level "unse" scan
  3. per-issue scans (tropical-agriculturist_*), all issues of the volume
  4. tdl (Tamil Digital Library) per-issue scans

Rationale: a single volume-level PDF is one OCR job with continuous
pagination; stitching six issue PDFs back into a volume is error-prone and
the issue scans are often missing wrappers and advertisements.
"""
import json, re, csv, collections, sys

ROMAN = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}


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


def family(ident):
    if ident.startswith('tdl.'):                        return 'tdl'
    if ident.startswith('tropical-agriculturist_'):     return 'per-issue'
    if ident.startswith('lbg.'):                        return 'lbg'
    if ident.startswith(('dli.ernet', 'in.ernet.dli')): return 'dli'
    if ident.startswith('tropicalagricul'):             return 'cornell'
    return 'other'


# volume-level families produce one PDF covering a whole volume (or half-year)
VOLUME_LEVEL = {'cornell', 'lbg', 'dli'}
RANK = {'cornell': 0, 'lbg': 1, 'dli': 2, 'other': 3, 'per-issue': 4, 'tdl': 5}


def resolve(rec):
    """Return (volume, issue) for an IA item, either may be None."""
    ident = rec['identifier']
    title = str(rec.get('title') or '')
    vol = rec.get('volume')
    issue = None

    # --- volume from explicit metadata ---
    v = None
    if vol is not None:
        vs = str(vol).strip()
        if vs.isdigit():
            v = int(vs)
        else:
            m = re.search(r'v\.?\s*(\d+)', vs, re.I)
            if m:
                v = int(m.group(1))

    # --- per-issue identifier: tropical-agriculturist_1915-06_44_6 ---
    if v is None:
        m = re.match(r'tropical-agriculturist_[a-z0-9-]+?_(\d{2,3})(?:_(\d+))?$', ident)
        if m:
            v = int(m.group(1))
            if m.group(2):
                issue = int(m.group(2))
    else:
        m = re.match(r'tropical-agriculturist_[a-z0-9-]+?_\d{2,3}_(\d+)$', ident)
        if m:
            issue = int(m.group(1))

    # --- roman numeral in title: "Vol-xli", "Vol LXIII" ---
    if v is None:
        m = re.search(r'vol[\s.\-_]*([ivxlcdm]+)\b', title, re.I)
        if m:
            v = roman_to_int(m.group(1))

    # --- Cornell-style identifiers ---
    if v is None:
        m = re.match(r'tropicalagricul(\d{2})(\d{4})ceyl', ident)
        if m:
            v = int(m.group(1))
    if v is None:
        m = re.match(r'tropicalagricult(\d{1,2})(\d{2})ceyl$', ident)
        if m:
            v = int(m.group(1))

    # --- lbg.630.5.tag.v.37 / tropicalagricult0054unse ---
    if v is None:
        m = re.search(r'tag\.v\.(\d+)', ident)
        if m:
            v = int(m.group(1))
    if v is None:
        m = re.search(r'tropicalagricult(\d{4})unse', ident)
        if m:
            v = int(m.group(1))

    # --- TDL: vol/issue live in the FILENAME, not the metadata ---
    if v is None or issue is None:
        for f in rec.get('files', []):
            m = re.search(r'_Vol[_\s]*(\d+)(?:[_\s]*no[_\s]*(\d+))?', f['name'], re.I)
            if m:
                if v is None:
                    v = int(m.group(1))
                if issue is None and m.group(2):
                    issue = int(m.group(2))
                break

    return v, issue


def best_pdf(rec):
    """Pick the most suitable PDF file for OCR. Prefer colour/greyscale text
    PDF over the bitonal _bw variant; prefer the largest if ambiguous."""
    pdfs = [f for f in rec.get('files', [])
            if f['name'].lower().endswith('.pdf') and f['size'] > 1_000_000]
    if not pdfs:
        return None
    def key(f):
        bw = f['name'].lower().endswith('_bw.pdf')
        return (bw, -f['size'])
    return sorted(pdfs, key=key)[0]


def main():
    recs = []
    with open('ia_meta.jsonl') as fh:
        for line in fh:
            r = json.loads(line)
            if 'error' in r:
                print('  ! metadata error:', r['identifier'], file=sys.stderr)
                continue
            recs.append(r)

    rows = []
    for r in recs:
        ident = r['identifier']
        title = str(r.get('title') or '')
        # The Nature review article is not an issue of the journal.
        if ident.startswith('paper-doi'):
            continue
        v, iss = resolve(r)
        pdf = best_pdf(r)
        is_index = 'index' in ident.lower() or re.search(r'\bindex\b', title, re.I) is not None
        rows.append({
            'identifier': ident,
            'family':     family(ident),
            'volume':     v,
            'issue':      iss,
            'year':       r.get('year') or (str(r.get('date') or '')[:4] or None),
            'is_index':   int(bool(is_index)),
            'imagecount': r.get('imagecount'),
            'pdf_name':   pdf['name'] if pdf else '',
            'pdf_mb':     round(pdf['size'] / 1048576, 1) if pdf else 0,
            'title':      title[:150],
        })

    rows.sort(key=lambda x: (x['volume'] or 9999, x['issue'] or 0, x['identifier']))
    with open('ta_items.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---- build the de-duplicated download manifest ----
    content = [r for r in rows if not r['is_index'] and r['pdf_name']]
    by_vol = collections.defaultdict(list)
    for r in content:
        by_vol[r['volume']].append(r)

    manifest, notes = [], []
    for v in sorted(k for k in by_vol if k is not None):
        cands = by_vol[v]
        vol_level = [c for c in cands if c['family'] in VOLUME_LEVEL and c['issue'] is None]
        if vol_level:
            vol_level.sort(key=lambda c: (RANK[c['family']], -(c['imagecount'] or 0)))
            # Some volumes are split across two physical scans (half-years).
            # Keep every distinct volume-level scan of the best family.
            best_fam = vol_level[0]['family']
            chosen = [c for c in vol_level if c['family'] == best_fam]
            for c in chosen:
                manifest.append({**c, 'reason': f'volume-level scan ({best_fam})'})
            alts = len(cands) - len(chosen)
            if alts:
                notes.append(f'vol {v}: chose {len(chosen)} {best_fam} scan(s), {alts} alternative copies available')
        else:
            issues = [c for c in cands if c['family'] == 'per-issue']
            pool = issues or cands
            fam = 'per-issue' if issues else pool[0]['family']
            for c in sorted(pool, key=lambda c: (c['issue'] or 0)):
                manifest.append({**c, 'reason': f'no volume-level scan; {fam} issue'})
            notes.append(f'vol {v}: assembled from {len(pool)} {fam} item(s)')

    unresolved = [r for r in content if r['volume'] is None]
    for r in unresolved:
        manifest.append({**r, 'reason': 'volume unresolved - needs manual check'})

    with open('ta_manifest.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(manifest[0]))
        w.writeheader()
        w.writerows(manifest)

    # ---- coverage report ----
    vols = sorted(k for k in by_vol if k is not None)
    out = []
    out.append('The Tropical Agriculturist - Internet Archive coverage')
    out.append('=' * 60)
    out.append(f'IA items examined         : {len(rows)}')
    out.append(f'  content items with PDF  : {len(content)}')
    out.append(f'  index-only items        : {sum(r["is_index"] for r in rows)}')
    out.append(f'  volume unresolved       : {len(unresolved)}')
    out.append('')
    out.append(f'Distinct volumes present  : {len(vols)}  (vol {min(vols)} - vol {max(vols)})')
    missing = [v for v in range(min(vols), max(vols) + 1) if v not in by_vol]
    out.append(f'Missing volumes in range  : {len(missing)}')
    if missing:
        out.append('  ' + ', '.join(map(str, missing)))
    out.append('')
    total_mb = sum(m['pdf_mb'] for m in manifest)
    out.append(f'Download set              : {len(manifest)} PDFs, {total_mb/1024:.1f} GB')
    out.append(f'Total pages (imagecount)  : {sum(int(m["imagecount"] or 0) for m in manifest):,}')
    out.append('')
    out.append('Per-volume detail')
    out.append('-' * 60)
    for v in vols:
        picked = [m for m in manifest if m['volume'] == v]
        fams = collections.Counter(c['family'] for c in by_vol[v])
        pages = sum(int(p['imagecount'] or 0) for p in picked)
        out.append(f'  vol {v:>3}  {len(picked):>2} file(s)  {pages:>5} pp  '
                   f'[{picked[0]["family"] if picked else "-"}]  '
                   f'available: {dict(fams)}')
    out.append('')
    out.append('Notes')
    out.append('-' * 60)
    out.extend('  ' + n for n in notes)

    open('coverage.txt', 'w').write('\n'.join(out) + '\n')
    print('\n'.join(out[:40]))
    print(f'\nWrote ta_items.csv ({len(rows)}), ta_manifest.csv ({len(manifest)}), coverage.txt')


if __name__ == '__main__':
    main()
