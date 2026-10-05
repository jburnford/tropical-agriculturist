# Print every reading of one page: corpus + all repair readings. Usage: show_reading.py TAG PAGE [CHARS]
import sys, re, glob, pathlib
sys.path.insert(0, "/scratch/jic823/tropical")
from apply_repairs import Repairs
from repair_compare import load
tag, page = sys.argv[1], sys.argv[2]; n = int(sys.argv[3]) if len(sys.argv) > 3 else 600
clean = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:n]
print("== old |", clean(load(pathlib.Path("output_v4", tag))[0][int(page)]))
r = Repairs("repair")
for idx in sorted(glob.glob("repair/*/in/*.index.tsv")):
    rnd = idx.split("/")[1]; stem = pathlib.Path(idx).name[:-10]
    if not pathlib.Path(f"repair/{rnd}/out/{stem}/{stem}.md").exists():
        continue
    for i, l in enumerate(open(idx)):
        x = l.rstrip("\n").split("\t")
        if x[0] == tag and x[1] == page:
            d, t, h, tok = r.page(f"{rnd}/{stem}:{i}")
            print(f"== {rnd}/{stem}:{i}{' part'+x[3] if len(x)>3 else ''} tok={tok} |", clean(t))
