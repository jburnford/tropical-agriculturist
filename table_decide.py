#!/usr/bin/env python3
"""
Decisions for the table pages (repair/tables/list.tsv), from table_eval.py output.

Chandra summarises dense tables instead of transcribing them ("Table with 3
columns: Item Name, Quality, and Quotation. Includes items like Bees Wax,
Cinchona Bark ..."). Read in strips of the full-resolution leaf (H halves,
T thirds) it transcribes them: in the 12-page pilot, Tesseract-word recall
went 0.03-0.16 -> 0.91-0.95 on every summarised page.

A strip reading replaces the corpus page (ACCEPT_TABLE) iff
  - the corpus reading is a summary, or its recall < 0.50;
  - the strip reading does not loop and has no summary phrasing;
  - its recall >= 0.70 and >= corpus recall + 0.15.
or (second tier) its recall >= 0.50 and >= corpus recall + 0.25: on the dense
bound-in Produce Sales Lists Tesseract's own reading is noisy and caps recall
near 0.65. Checked vol021 p1175 (0.13 -> 0.65) against the leaf: the corpus
text had dropped every estate name and the whole right-hand column; the strip
reading has both, line for line (with the two columns interleaved by row).
The better of H and T by recall is used (ties: T, which splits finer).
Pages that do not qualify are left as they are and listed (TABLE_UNFIXED).

Usage: table_decide.py EVAL_TSV > decisions_tables.tsv   (repair_decide.py columns)
"""
import collections, csv, sys

rows = collections.defaultdict(list)
for r in csv.DictReader(open(sys.argv[1]), delimiter="\t"):
    rows[(r["tag"], r["page"])].append(r)

print("tag\tpage\treason\taction\tsource\twords\tnote")
for (t, p), rr in sorted(rows.items()):
    old = next(r for r in rr if r["variant"] == "old")
    orc = float(old["recall"])
    why = "table-summary" if old["summary"] == "1" else "audit-missing"
    cands = [r for r in rr if r["variant"] != "old" and r["loop"] == "0" and r["summary"] == "0"]
    cands.sort(key=lambda r: (-float(r["recall"]), 0 if "/T_" in r["variant"] else 1))
    note = " ".join(f"{r['variant'].split('/')[0]}:{r['recall']}{'L' if r['loop'] == '1' else ''}"
                    f"{'S' if r['summary'] == '1' else ''}" for r in rr)
    best = cands[0] if cands else None
    br = float(best["recall"]) if best else 0.0
    if (old["summary"] == "1" or orc < 0.50) and best and (
            (br >= 0.70 and br >= orc + 0.15) or (br >= 0.50 and br >= orc + 0.25)):
        print(f"{t}\t{p}\t{why}\tACCEPT_TABLE\t{best['src']}\t{best['words']}\t{note}")
    else:
        print(f"{t}\t{p}\t{why}\tTABLE_UNFIXED\t\t{old['words']}\t{note}")
