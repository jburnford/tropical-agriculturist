#!/usr/bin/env python3
"""
Score article-start labels against the printed subject INDEX (bound volumes, 1881-1927).

The index is not a list of articles: it also lists subjects inside articles. So:
  recall    -- of index entries that match a skeleton candidate on the entry's own
               page (i.e. entries that are printed as headings there), the share whose
               candidate is labelled ARTICLE (or a SECTION with its own text);
  confirmed -- of predicted article starts on a foliated page, the share for which
               some index entry of the same volume names that page and matches the title.
Neither is an absolute accuracy; both compare labellings on the same issues.
Index entries are often inverted ("Cotton Crop, The Indian"), so a match is word-set
overlap >= 60% of the shorter side's content words. Supplement entries are skipped
(own pagination).

Usage: eval_index.py LABELS.jsonl
"""
import csv, json, sys, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from eval_contents import words, own_text, is_start


def overlap(a, b):
    A, B = set(words(a)), set(words(b))
    if not A or not B:
        return False
    return len(A & B) / min(len(A), len(B)) >= 0.6 and len(A & B) >= 1


def main(path):
    units = {json.loads(l)["unit"]: json.loads(l) for l in open("skeleton.jsonl")}
    idx = collections.defaultdict(list)
    for r in csv.DictReader(open("gold_index.tsv"), delimiter="\t"):
        if r["supplement"] == "0":
            idx[(r["volume"], r["folio"])].append(r["entry"])
    T = collections.Counter()
    for l in open(path):
        j = json.loads(l); U = units[j["unit"]]
        lab = {int(k): v for k, v in j["labels"].items()}
        cands = U["cands"]
        is_art = lambda c: is_start(cands, lab, c["id"])
        t = collections.Counter()
        byfolio = collections.defaultdict(list)
        for c in cands:
            if c["folio"] and c["part"] == "main":
                byfolio[c["folio"]].append(c)
        for f, cs in byfolio.items():
            for e in idx.get((U["volume"], f), []):
                m = [c for c in cs if overlap(e, c["text"])]
                if m:
                    t["entries"] += 1; t["recalled"] += any(is_art(c) for c in m)
        for c in cands:
            if c["folio"] and c["part"] == "main" and is_art(c) and lab.get(c["id"]) != "CONT":
                t["pred"] += 1
                t["confirmed"] += any(overlap(e, c["text"]) for e in idx.get((U["volume"], c["folio"]), []))
        if t["entries"] or t["pred"]:
            print(f"{j['unit'][:60]:60} index-headings {t['entries']:3} recalled {t['recalled']:3}  pred {t['pred']:3} confirmed {t['confirmed']:3}")
        T.update(t)
    print(f"\nrecall {T['recalled']}/{T['entries']} = {T['recalled']/max(1,T['entries']):.1%}   "
          f"confirmed {T['confirmed']}/{T['pred']} = {T['confirmed']/max(1,T['pred']):.1%}")


if __name__ == "__main__":
    main(sys.argv[1])
