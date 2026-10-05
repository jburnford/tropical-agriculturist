# Table-repair list: summary-phrased pages + audit MISSING pages, minus pages stage 4 already changed.
# Usage: table_list.py SUMM_TSV MISSING_TSV DECISIONS > list.tsv
import csv, glob, sys
marked = set()
for r in csv.DictReader(open(sys.argv[3]), delimiter="\t"):
    if r["action"] not in ("KEEP_BLANK", "KEEP_MINOR", "KEEP_FIGURE") and not (r["action"] == "ACCEPT" and r["source"] == "old"):
        marked.add((r["tag"], r["page"]))
pdfs = {}
for f in glob.glob("chunks/chunk_*.tsv"):
    for l in open(f):
        t, p = l.split("\t")[:2]; pdfs[t] = p
summ = set(tuple(l.rstrip("\n").split("\t")) for l in open(sys.argv[1]))
miss = set(tuple(l.rstrip("\n").split("\t")) for l in open(sys.argv[2]))
for t, p in sorted(summ | miss):
    if (t, p) not in marked:
        why = "table-summary" if (t, p) in summ else "audit-missing"
        print(f"{t}\t{p}\t{pdfs[t]}\t{why}")
