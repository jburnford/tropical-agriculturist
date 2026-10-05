#!/usr/bin/env python3
"""Parse the printed table of contents from the 1942-45 quarterlies.

The TOC survives OCR as HTML tables under department headings, each row being
"Title by Author .. .. page". That gives title, author and department directly
from the journal -- real ground truth, not inference -- for the one era where
heading levels are least trustworthy.
"""
import re, sys, pathlib, html

root = pathlib.Path('/home/jic823/tropical/output')

def parse_toc(md_text):
    # The TOC is the run of <table> blocks before the first body section.
    head = md_text[:12000]
    entries, dept = [], None
    for m in re.finditer(r'^## (.+?)$|<table.*?</table>', head, re.S | re.M):
        if m.group(1):
            dept = m.group(1).strip()
            continue
        for row in re.findall(r'<tr>(.*?)</tr>', m.group(0), re.S):
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)
            if len(cells) < 2: continue
            title = html.unescape(re.sub(r'<[^>]+>', '', cells[0])).strip()
            page  = html.unescape(re.sub(r'<[^>]+>', '', cells[-1])).strip()
            title = re.sub(r'[\s.]*\.\.[\s.]*$', '', title).strip()
            # A page value is 1-3 digits, optionally a range. Anything with a
            # thousands separator is a body statistic, not a folio -- that is
            # how the cattle-population tables leaked into the vol098 TOC.
            pm = re.match(r'^(\d{1,3})(?:\s*[-\u2014]\s*\d{1,3})?$', page)
            if not title or not pm: continue
            page_n = int(pm.group(1))
            author = None
            # "by" only introduces an author when what follows looks like a
            # person: an initial, a title, or a degree. Otherwise it is prose --
            # "Diseases of Cattle Transmitted by Ticks" is not authored by Ticks.
            am = re.search(r',?\s*[Bb]y\s+(.+)$', title)
            if am:
                cand = am.group(1).strip()
                if re.search(r'\b[A-Z]\.|\b(?:Dr|Mr|Mrs|Prof|Ph\.D|B\.Sc|M\.A|B\.A|D\.I\.C)\b', cand):
                    author = cand
                    title = title[:am.start()].strip().rstrip(',')
            entries.append({'department': dept, 'title': title,
                            'author': author, 'start_page': page_n})
    ordered, last = [], 0
    for e in entries:
        if e['start_page'] < last: break
        ordered.append(e); last = e['start_page']
    return ordered

if __name__ == '__main__':
    for d in sys.argv[1:]:
        md = next(root.glob(f'{d}*/*/*.md'), None)
        if not md: print(f'!! {d}'); continue
        e = parse_toc(md.read_text(encoding='utf-8', errors='replace'))
        print(f"\n=== {md.stem}  ({len(e)} TOC entries)")
        for x in e:
            au = f"  [{x['author'][:46]}]" if x['author'] else ''
            print(f"  p{x['start_page']:>4}  {(x["department"] or "-")[:22]:<22} {x['title'][:60]}{au}")
