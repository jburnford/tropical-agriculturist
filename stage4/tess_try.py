# Compare Tesseract settings on given leaves: default vs autocontrast+Sauvola. Usage: tess_try.py TAG:PAGE...
import sys, csv, io, subprocess, tempfile
from PIL import Image, ImageOps
SIF = "/scratch/jic823/containers/tesseract.sif"
def run(img, extra):
    with tempfile.NamedTemporaryFile(suffix=".png", dir="/scratch/jic823/tmp") as f:
        img.save(f.name)
        r = subprocess.run(["apptainer", "exec", SIF, "tesseract", f.name, "-", "--psm", "3"] + extra + ["tsv"], capture_output=True, text=True)
    rows = list(csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE))
    return [w["text"] for w in rows if w.get("text") and float(w.get("conf", -1)) >= 70 and len(w["text"]) >= 3 and w["text"].isalpha()]
for a in sys.argv[1:]:
    tag, pg = a.rsplit(":", 1)
    im = Image.open(f"leaves/full/{tag}/p{int(pg):04d}.png").convert("L")
    ac = ImageOps.autocontrast(im, cutoff=(1, 1))
    res = []
    for name, img, extra in [("def", im, []), ("sauv", im, ["-c", "thresholding_method=2"]), ("ac+sauv", ac, ["-c", "thresholding_method=2"])]:
        n = run(img, extra); m = run(ImageOps.mirror(img), extra)
        res.append(f"{name}:{len(n)}/{len(m)}")
    print(tag[:24], pg, " ".join(res), "|", " ".join(run(ac, ["-c", "thresholding_method=2"])[:12]), flush=True)
