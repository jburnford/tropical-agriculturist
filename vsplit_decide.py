#!/usr/bin/env python3
"""
Swap column-split (V) readings into the Stage 4 decisions for side-by-side
table pages, from vsplit_eval.py output.

A V reading replaces the page's current source iff
  - it does not loop and has no summary phrasing;
  - it keeps the content: Tesseract-word recall >= current recall - 0.03;
  - only with --structure: it keeps the table structure, in-table word
    share >= current - 0.05 (some Market Rates pieces come back as loose
    text, item names listed apart from their prices: order fixed, row
    linkage lost). Off by default: the corpus is for reading and search,
    not structured price extraction (Jim, 2026-10-04), so correct reading
    order outweighs the name<->price link;
  - its reading order is no worse: switch <= max(0.05, current switch)
    (V reads the left table then the right one by construction; in the
    13-page pilot every page went to 0.00-0.02, from up to 0.42, with recall
    unchanged).
Pages that fail keep their current decision, and are listed on stderr.

Usage: vsplit_decide.py [--structure] DECISIONS EVAL_TSV > decisions_v6.tsv
  DECISIONS  stage4/decisions_complete.tsv (rows passed through unchanged
             unless replaced; the action stays ACCEPT_TABLE, source and note
             change)
"""
import csv, math, sys

STRUCTURE = "--structure" in sys.argv
dec, ev = [a for a in sys.argv[1:] if a != "--structure"][:2]
reads = {}
for r in csv.DictReader(open(ev), delimiter="\t"):
    reads.setdefault((r["tag"], r["page"]), {})["v5" if r["variant"] == "v5" else "V"] = r

take, kept = {}, []
for k, rr in reads.items():
    cur, v = rr.get("v5"), rr.get("V")
    if not (cur and v):
        kept.append((k, "missing reading")); continue
    rc, rv = float(cur["recall"]), float(v["recall"])
    sc, sv = float(cur["switch"]), float(v["switch"])
    why = []
    if v["loop"] == "1" or v["summary"] == "1":
        why.append("loop/summary")
    if rv < rc - 0.03:
        why.append(f"recall {rc:.2f}->{rv:.2f}")
    ic, iv = float(cur["intab"]), float(v["intab"])
    if STRUCTURE and iv < ic - 0.05:
        why.append(f"in-table {ic:.2f}->{iv:.2f}")
    if not math.isnan(sv) and sv > max(0.05, sc if not math.isnan(sc) else 0):
        why.append(f"switch {sc:.2f}->{sv:.2f}")
    if why:
        kept.append((k, "; ".join(why)))
    else:
        take[k] = (v["src"].split(":", 1)[0] + ":" + v["src"].split(":", 1)[1],
                   v["words"], f"vsplit: recall {rc:.2f}->{rv:.2f} switch {sc:.2f}->{sv:.2f}")

rows = list(csv.reader(open(dec), delimiter="\t"))
w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
w.writerow(rows[0])
n = 0
for r in rows[1:]:
    k = (r[0], r[1])
    if k in take and r[3] == "ACCEPT_TABLE":
        src, words, note = take[k]
        r = r[:4] + [src, words, note + " | was " + r[4]]
        n += 1
    w.writerow(r)
print(f"# {n} pages switched to V, {len(kept)} kept", file=sys.stderr)
for k, why in sorted(kept):
    print(f"# kept {k[0]} p{k[1]}: {why}", file=sys.stderr)
