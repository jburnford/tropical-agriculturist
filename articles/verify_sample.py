#!/usr/bin/env python3
"""Fetch IA images for a stratified sample of pages.tsv rows; montage the top strip of each, labelled with our folio."""
import csv, random, subprocess, io, sys, pathlib
from PIL import Image, ImageDraw
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
r = [x for x in csv.DictReader(open('pages.tsv'), delimiter='\t') if x['kind'] == 'text']
fam = lambda x: ('cornell' if 'ceyl' in x['ia_id'] or 'colo' in x['ia_id'] else 'lbg' if x['ia_id'].startswith('lbg') else
                 'dli' if 'dli' in x['ia_id'] else 'tdl' if x['ia_id'].startswith('tdl') else 'unse' if 'unse' in x['ia_id'] else 'issue')
pick = []
for st, k in [('corrected', 5), ('inferred', 5), ('read', 4), ('unplaced', 2)]:
    pick += random.sample([x for x in r if x['folio_status'] == st], k)
for f in ['lbg', 'dli', 'tdl', 'unse', 'issue']:
    pool = [x for x in r if fam(x) == f and x['folio_status'] == 'read']
    pick += random.sample(pool, 1) if pool else []
    print(f, len(pool), file=sys.stderr)
strips = []
for x in pick:
    url = f"https://archive.org/download/{x['ia_id']}/page/n{x['page']}_w800.jpg"
    b = subprocess.run(['curl', '-sSfL', '-m', '60', url], capture_output=True).stdout
    im = Image.open(io.BytesIO(b)).convert('L')
    top = im.crop((0, 0, im.width, int(im.height * 0.09))).resize((800, int(800 / im.width * im.height * 0.09)))
    lab = Image.new('L', (800, 22), 255)
    ImageDraw.Draw(lab).text((4, 4), f"{x['doc'][:30]} n{x['page']}  OURS folio={x['folio']} [{x['folio_status']}] raw={x['folio_raw']} date={x['date']}", fill=0)
    strips += [lab, top]
    print(x['doc'][:30], x['page'], x['folio_status'], x['folio'], x['folio_raw'], fam(x), file=sys.stderr)
H = sum(s.height for s in strips); M = Image.new('L', (800, H), 255); y = 0
for s in strips: M.paste(s, (0, y)); y += s.height
M.save(sys.argv[2] if len(sys.argv) > 2 else 'verify/montage.png')
