# Stage 4 review list: every page whose text was withheld, emptied, or is still known-incomplete.
import csv, sys
A = {(r["tag"], r["page"]): r for r in csv.DictReader(open("stage4/audit_output_v5.tsv"), delimiter="\t")}
print("tag\tpage\tpdf_page_1based\tstatus\tdetail")
for r in csv.DictReader(open("stage4/decisions_complete.tsv"), delimiter="\t"):
    k = (r["tag"], r["page"]); a = A.get(k)
    st = None
    if r["action"] in ("FAINT", "UNRESOLVED", "SHOWTHROUGH"):
        st = r["action"]
    elif r["action"] == "TABLE_UNFIXED" and a and a["flag"] == "MISSING":
        st = "TABLE_INCOMPLETE"
    elif r["action"].startswith("ACCEPT") and a and a["flag"] == "MISSING":
        st = "ACCEPTED_BUT_AUDIT_MISSING"
    if st:
        det = (r["note"] or "").replace("\t", " ")[:200]
        if a: det = f"audit recall {a['recall']} ({a['tess']} tess words); " + det
        print(f"{r['tag']}\t{r['page']}\t{int(r['page']) + 1}\t{st}\t{det}")
