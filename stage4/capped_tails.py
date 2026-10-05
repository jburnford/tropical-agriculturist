import csv,re,pathlib
MARK=re.compile(r"^\d+-{48}\s*$",re.M)
r=[x for x in csv.DictReader(open("stage4/pages.tsv"),delimiter="\t") if int(x["tok"])>=16000]
I={(x["tag"],x["page"]):x for x in csv.DictReader(open("stage4/ink.tsv"),delimiter="\t")}
cache={}
for x in r:
    t=x["tag"]
    if t not in cache: cache[t]=MARK.split(next(pathlib.Path("output_v4",t).rglob("*.md")).read_text())
    pg=cache[t][int(x["page"])]
    tail=pg.rstrip()[-120:].replace("\n"," / ")
    print(t[:14],x["page"],"c=%s"%I[(t,x["page"])]["contrast"],"chars=%s rep=%s |"%(x["chars"],x["top_line_rep"]),tail)
