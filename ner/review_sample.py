#!/usr/bin/env python3
"""Dump a stratified sample of articles WITH their extracted mentions as readable text files for review.
Usage: review_sample.py --from 1881 --to 1913 --n 40 --seed 1 --out review/sample_A
Writes out/NNN_<id>.txt (article text, then a mentions table) and out/index.tsv. Also --ids FILE to
dump specific article ids, and --types to list only some types."""
import argparse, gzip, json, pathlib, random, re, collections
ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="y0", type=int, default=1881); ap.add_argument("--to", dest="y1", type=int, default=1945)
ap.add_argument("--n", type=int, default=40); ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--out", required=True); ap.add_argument("--ids"); ap.add_argument("--min-words", type=int, default=60)
ap.add_argument("--max-words", type=int, default=4000)
a = ap.parse_args(); random.seed(a.seed)
here = pathlib.Path(__file__).resolve().parent
ments = {}
for l in open(here / "mentions.jsonl"):
    r = json.loads(l); ments[r["id"]] = r
want = None
if a.ids: want = {l.strip() for l in open(a.ids) if l.strip()}
pool = collections.defaultdict(list); chosen = []
for f in sorted((here.parent / "articles/by_year").glob("articles_*.jsonl.gz")):
    y = int(re.search(r"articles_(\d{4})", f.name).group(1))
    if not (a.y0 <= y <= a.y1): continue
    for l in gzip.open(f, "rt", encoding="utf-8"):
        r = json.loads(l)
        if want is not None:
            if r["id"] in want: chosen.append(r)
            continue
        if r["canonical"] and r["kind"] == "article" and a.min_words <= r["words"] <= a.max_words and r["id"] in ments:
            band = "S" if r["words"] < 300 else "M" if r["words"] < 1500 else "L"
            pool[(y // 10 * 10, band)].append(r)
if want is None:
    keys = sorted(pool); per = max(1, a.n // len(keys))
    for k in keys: chosen += random.sample(pool[k], min(per, len(pool[k])))
    chosen = chosen[:a.n] if len(chosen) > a.n else chosen
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
idx = open(out / "index.tsv", "w"); idx.write("file\tid\tissue\twords\tmentions\ttitle\n")
for i, r in enumerate(sorted(chosen, key=lambda r: r["issue"]), 1):
    m = ments.get(r["id"], {"mentions": []})
    fn = out / f"{i:03d}_{re.sub(r'[^A-Za-z0-9]+', '_', r['id'])[:60]}.txt"
    with open(fn, "w") as f:
        f.write(f"ID: {r['id']}\nISSUE: {r['issue']}  VOL: {r['volume']}  SECTION: {r['section']}\nTITLE: {r['title']}\nBYLINE: {r['byline']}\n"
                f"WORDS: {r['words']}  PAGES: {[p['folio'] or 'n'+str(p['page']) for p in r['pages']]}\nIA: {r['pages'][0]['viewer_url']}\n\n")
        f.write("=== TEXT ===\n" + r["text"] + "\n\n")
        f.write(f"=== MENTIONS ({len(m['mentions'])}) ===\n")
        f.write("type\ttext\tnorm\trole\n")
        for x in sorted(m["mentions"], key=lambda x: (x["type"], x["text"].lower())):
            f.write(f"{x['type']}\t{x['text']}\t{x['norm']}\t{x['role']}\n")
    idx.write(f"{fn.name}\t{r['id']}\t{r['issue']}\t{r['words']}\t{len(m['mentions'])}\t{r['title'][:60]}\n")
print(f"wrote {len(chosen)} articles to {out}/")
