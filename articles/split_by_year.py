#!/usr/bin/env python3
"""Split articles.jsonl into by_year/articles_YYYY.jsonl.gz (GitHub's 100 MB file limit; the viewer
loads one year at a time) and write by_year/index.json: years -> issue units -> counts.
Usage: split_by_year.py [articles.jsonl] [by_year/]"""
import gzip, json, sys, pathlib, collections
src = sys.argv[1] if len(sys.argv) > 1 else "articles.jsonl"
out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "by_year"); out.mkdir(exist_ok=True)
files = {}; index = collections.defaultdict(lambda: collections.defaultdict(lambda: {"articles": 0, "canonical": 0, "words": 0, "pages": set()}))
for line in open(src, encoding="utf-8"):
    r = json.loads(line); y = r["issue"][:4]
    if y not in files:
        files[y] = gzip.open(out / f"articles_{y}.jsonl.gz", "wt", encoding="utf-8", compresslevel=6)
    files[y].write(line if line.endswith("\n") else line + "\n")
    u = index[y][f"{r['volume']}|{r['issue']}|{r['doc']}"]
    u["articles"] += 1; u["canonical"] += bool(r["canonical"]); u["words"] += r["words"] if r["canonical"] else 0
    u["pages"].update(p["page"] for p in r["pages"]); u["volume"] = r["volume"]; u["issue"] = r["issue"]; u["doc"] = r["doc"]; u["ia_id"] = r["ia_id"]
for f in files.values(): f.close()
idx = {y: sorted(({**u, "pages": len(u["pages"]), "unit": k} for k, u in units.items()), key=lambda u: (u["volume"], u["issue"], u["doc"]))
       for y, units in sorted(index.items())}
json.dump(idx, open(out / "index.json", "w"), ensure_ascii=False)
print(f"{len(files)} years, {sum(len(v) for v in idx.values())} issue units -> {out}/", file=sys.stderr)
