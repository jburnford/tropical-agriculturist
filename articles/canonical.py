#!/usr/bin/env python3
"""
Choose one copy per issue where the corpus holds two (e.g. a DLI half-volume and the
separate monthly PDFs; vol046 lbg = vol056 monthlies). Jim, 2026-10-04: keep the
better-quality copy.

Quality per (doc, volume, issue), from pages in parts main/supplement:
  bad   = pages withheld or untranscribed in stage 4 (kind faint / untranscribed)
  words = transcribed words
  folio = share of text pages with a trusted folio (read/inferred/corrected)
Choice: completeness first (a copy with < 90% of the fuller copy's words is missing pages --
vol070 holds only the July 1928 cover); then fewest bad pages; then folio share; then words.
Issues held once are canonical trivially.

Writes canonical.tsv: volume, issue, doc, canonical(1/0), bad, words, folio_share, n_copies
"""
import csv, collections

pages = {(r["doc"], r["page"]): r for r in csv.DictReader(open("pages.tsv"), delimiter="\t")}
words = collections.Counter()
for l in open("skeleton.jsonl"):
    pass
stat = collections.defaultdict(lambda: collections.Counter())
for r in csv.DictReader(open("page_issue.tsv"), delimiter="\t"):
    if not r["issue"] or "/" in r["issue"] and int(r["volume"]) < 98:   # volume-level leftovers aren't issues
        continue
    p = pages[(r["doc"], r["page"])]
    k = (r["volume"], r["issue"], r["doc"])
    if r["part"] in ("main", "supplement"):
        s = stat[k]
        s["pages"] += 1
        s["text"] += p["kind"] == "text"
        s["folio"] += p["folio_status"] in ("read", "inferred", "corrected")
        s["words"] += (int(p["char_end"]) - int(p["char_start"])) // 6     # ~ words; same scale for both copies
    elif r["part"] in ("faint", "untranscribed"):
        stat[k]["bad"] += 1
byissue = collections.defaultdict(list)
for (v, i, d), s in stat.items():
    byissue[(v, i)].append((d, s))
w = csv.writer(open("canonical.tsv", "w"), delimiter="\t", lineterminator="\n")
w.writerow(["volume", "issue", "doc", "canonical", "bad", "words", "folio_share", "n_copies"])
dup = 0
for (v, i), docs in sorted(byissue.items(), key=lambda x: (int(x[0][0]), x[0][1])):
    full = max(s["words"] for _, s in docs)
    key = lambda ds: (ds[1]["words"] < 0.9 * full, ds[1]["bad"], -round(ds[1]["folio"] / max(1, ds[1]["text"]), 2), -ds[1]["words"])
    docs.sort(key=key)
    dup += len(docs) > 1
    for k, (d, s) in enumerate(docs):
        w.writerow([v, i, d, int(k == 0), s["bad"], s["words"], f"{s['folio'] / max(1, s['text']):.2f}", len(docs)])
print(f"{len(byissue)} issues, {dup} held in more than one copy")
