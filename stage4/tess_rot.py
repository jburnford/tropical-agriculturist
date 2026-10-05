# Tesseract confident-word counts for a leaf rotated 180 degrees. Usage: tess_rot.py DECISIONS > rot.tsv  (SHOWTHROUGH rows only)
import sys, csv
sys.path.insert(0, "/scratch/jic823/tropical")
from tess_witness import tess
from PIL import Image
print("tag\tpage\trot_words")
for r in csv.DictReader(open(sys.argv[1]), delimiter="\t"):
    if r["action"] == "SHOWTHROUGH":
        im = Image.open(f"leaves/full/{r['tag']}/p{int(r['page']):04d}.png").convert("L").rotate(180)
        print(f"{r['tag']}\t{r['page']}\t{len(tess(im)[0])}", flush=True)
