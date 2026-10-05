#!/usr/bin/env python3
"""Rank entities per type by frequency across the corpus (key = normalised name, case-folded; falls
back to the surface text). Writes review/ranked/<TYPE>.tsv: rank, key, mentions, articles, decades,
first_year, last_year, surface_forms (top 5), roles (top 3), example_article. Also <TYPE>_tail_sample.tsv:
400 random singletons (1 mention) and 200 random doubletons, with their article and a text snippet."""
import json, re, random, collections, pathlib, gzip
random.seed(7)
here = pathlib.Path(__file__).resolve().parent
year = {}
for f in (here.parent / "articles/by_year").glob("articles_*.jsonl.gz"):
    y = int(re.search(r"(\d{4})", f.name).group(1))
    for l in gzip.open(f, "rt", encoding="utf-8"):
        r = json.loads(l); year[r["id"]] = y
def key(m):
    k = (m["norm"] or m["text"]).strip().strip("*_ ").lower()
    k = re.sub(r"\s+", " ", k)
    return k or m["text"].lower()
agg = collections.defaultdict(lambda: collections.defaultdict(lambda: {"n": 0, "arts": set(), "years": [], "surf": collections.Counter(), "roles": collections.Counter()}))
for l in open(here / "mentions.jsonl"):
    r = json.loads(l); y = year.get(r["id"], 0)
    for m in r["mentions"]:
        e = agg[m["type"]][key(m)]
        e["n"] += 1; e["arts"].add(r["id"]); e["years"].append(y); e["surf"][m["text"]] += 1
        if m["role"]: e["roles"][m["role"][:60]] += 1
out = here / "review/ranked"; out.mkdir(parents=True, exist_ok=True)
summary = []
for t, ents in agg.items():
    rows = sorted(ents.items(), key=lambda x: (-x[1]["n"], x[0]))
    with open(out / f"{t}.tsv", "w") as f:
        f.write("rank\tkey\tmentions\tarticles\tdecades\tfirst\tlast\tsurface_forms\troles\texample_article\n")
        for i, (k, e) in enumerate(rows, 1):
            ys = [y for y in e["years"] if y]
            decs = sorted({y // 10 * 10 for y in ys})
            f.write(f"{i}\t{k}\t{e['n']}\t{len(e['arts'])}\t{','.join(str(d)[2:] for d in decs)}\t{min(ys) if ys else ''}\t{max(ys) if ys else ''}\t"
                    f"{' | '.join(s for s, _ in e['surf'].most_common(5))}\t{' | '.join(s for s, _ in e['roles'].most_common(3))}\t{sorted(e['arts'])[0]}\n")
    singles = [k for k, e in rows if e["n"] == 1]; doubles = [k for k, e in rows if e["n"] == 2]
    with open(out / f"{t}_tail_sample.tsv", "w") as f:
        f.write("mentions\tkey\tsurface\trole\tarticle\n")
        for k in random.sample(singles, min(400, len(singles))) + random.sample(doubles, min(200, len(doubles))):
            e = ents[k]; f.write(f"{e['n']}\t{k}\t{next(iter(e['surf']))}\t{next(iter(e['roles']), '')}\t{sorted(e['arts'])[0]}\n")
    n = sum(e["n"] for _, e in rows); n1 = len(singles)
    top100 = sum(e["n"] for _, e in rows[:100])
    summary.append((t, n, len(rows), n1, top100))
with open(out / "SUMMARY.tsv", "w") as f:
    f.write("type\tmentions\tdistinct\tsingletons\tsingleton_share_of_distinct\ttop100_share_of_mentions\n")
    for t, n, d, n1, top in sorted(summary, key=lambda x: -x[1]):
        f.write(f"{t}\t{n}\t{d}\t{n1}\t{n1/d:.1%}\t{top/n:.1%}\n")
print(open(out / "SUMMARY.tsv").read())
