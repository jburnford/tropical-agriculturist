# Build the repair list: every page that is capped, ends in a repeat, or is faded (contrast<20) with OCR text.
import csv, glob
P={(x["tag"],x["page"]):x for x in csv.DictReader(open("stage4/pages.tsv"),delimiter="\t")}
for x in csv.DictReader(open("stage4/ink.tsv"),delimiter="\t"): P[(x["tag"],x["page"])].update(x)
pdfs={}
for f in glob.glob("chunks/chunk_*.tsv"):
    for l in open(f):
        t,p=l.split("\t")[:2]; pdfs[t]=p
out=open("stage4/repair_list.tsv","w"); n={}
for (t,p),x in sorted(P.items()):
    why=[]
    if int(x["tok"])>=16000: why.append("capped")
    if x["end_repeat"]=="1": why.append("repeat")
    if int(x["contrast"])<20 and int(x["chars"])>0: why.append("faded")
    if why:
        r="+".join(why); n[r]=n.get(r,0)+1
        out.write(f"{t}\t{p}\t{pdfs[t]}\t{r}\n")
print(n, sum(n.values()))
