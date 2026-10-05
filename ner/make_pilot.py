#!/usr/bin/env python3
"""Pilot sample: N canonical articles (kind=article, >= 60 words), stratified evenly over decades,
within each decade stratified over length bands (short <300 w, medium <1500, long). Seeded."""
import gzip, json, random, sys, pathlib, collections
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
random.seed(20261005)
BY = pathlib.Path(__file__).resolve().parent.parent / "articles/by_year"
pool = collections.defaultdict(list)
for f in sorted(BY.glob("articles_*.jsonl.gz")):
    for l in gzip.open(f, "rt", encoding="utf-8"):
        r = json.loads(l)
        if r["canonical"] and r["kind"] == "article" and r["words"] >= 60 and r["part"] == "main":
            band = "S" if r["words"] < 300 else "M" if r["words"] < 1500 else "L"
            pool[(r["issue"][:3] + "0s", band)].append(r)
decades = sorted({k[0] for k in pool}); per = N // len(decades)
out = open("pilot_articles.jsonl", "w"); picked = collections.Counter()
for d in decades:
    for band, share in (("S", 0.3), ("M", 0.4), ("L", 0.3)):
        k = round(per * share)
        xs = random.sample(pool[(d, band)], min(k, len(pool[(d, band)])))
        for r in xs:
            out.write(json.dumps(r, ensure_ascii=False) + "\n"); picked[(d, band)] += 1
print(dict(picked), "total", sum(picked.values()), file=sys.stderr)
