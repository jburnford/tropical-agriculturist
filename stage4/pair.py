# Print old vs new text snippets for selected compare rows (by stem:idx).
import sys, re, pathlib, json, csv
sys.path.insert(0,"/scratch/jic823/tropical")
from repair_compare import load
R={ (r["stem"],r["idx"]):r for r in csv.DictReader(open(sys.argv[1]+"/compare.tsv"),delimiter="\t")}
for key in sys.argv[2:]:
    stem,idx=key.split(":"); r=R[(stem,idx)]
    old=load(pathlib.Path("output_v4",r["tag"]))[0][int(r["page"])]
    new=load(pathlib.Path(sys.argv[1],"out",stem))[0][int(idx)]
    f=lambda t: re.sub(r"\s+"," ",re.sub(r"!\[[^\]]*\]\([^)]*\)","[IMG]",t))[:260]
    print(f"== {r['tag'][:12]} p{r['page']} agree={r['agree']}\n  OLD: {f(old)}\n  NEW: {f(new)}")
