# For FAINT pages whose corpus reading contains an image: agreement old vs J, with the first words of each.
import sys, csv, pathlib
sys.path.insert(0, "/scratch/jic823/tropical")
from repair_decide import words, agree, load
from apply_repairs import Repairs
rep = Repairs("repair"); cache = {}
for r in csv.DictReader(open(sys.argv[1]), delimiter="\t"):
    if r["action"] != "FAINT":
        continue
    t, p = r["tag"], int(r["page"])
    if t not in cache: cache[t] = load(pathlib.Path("output_v4", t))[0]
    old = cache[t][p]
    if "![" not in old: continue
    jsrc = None
    for idx in pathlib.Path("repair/r2J/in").glob("J_*.index.tsv"):
        for i, l in enumerate(open(idx)):
            x = l.split("\t")
            if x[0] == t and x[1] == str(p): jsrc = f"r2J/{idx.name[:-10]}:{i}"
    if not jsrc: continue
    jt = rep.page(jsrc)[1]
    a = agree(words(old), words(jt))
    print(f"{a:.2f}\t{t[:22]}\t{p}\t{len(words(old))}w\t{' '.join(words(old)[:10])}\t|\t{' '.join(words(jt)[:10])}")
