#!/usr/bin/env python3
"""
Tesseract as an independent witness on the full-resolution leaves.

Every Chandra reading of a faint page can repeat the same fluent
hallucination (J, K and the half-leaf Q all read "1860 1861 ... 1919" off
one show-through verso), and Chandra also *de-mirrors* show-through into
clean text. Tesseract does neither: it does not invent fluent text, and it
reads mirror-reversed print as junk. So for each leaf it is run twice:

  norm  the leaf as scanned
  mirr  the leaf flipped left-right

and the count of confident real words is compared. A page whose only print
is show-through yields words when mirrored and almost none when not; a
page with its own print yields words the right way round.

Per leaf, one row:
  tag page norm_words mirr_words norm_conf mirr_conf
where *_words = words with confidence >= 70, >= 3 letters, alphabetic.
The norm text (confident words, reading order) is written to
OUT/text/<tag>/pNNNN.txt for agreement checks against Chandra.

Usage: tess_witness.py LEAFDIR OUT NPROC
"""
import csv, io, pathlib, subprocess, sys, tempfile
from multiprocessing import Pool

from PIL import Image, ImageOps

SIF = "/scratch/jic823/containers/tesseract.sif"
MINCONF = 70


def tess(img):
    with tempfile.NamedTemporaryFile(suffix=".png", dir="/scratch/jic823/tmp") as f:
        img.save(f.name)
        r = subprocess.run(["apptainer", "exec", SIF, "tesseract", f.name, "-", "--psm", "3", "tsv"],
                           capture_output=True, text=True)
    rows = list(csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE))
    good = [w for w in rows if w.get("text") and float(w.get("conf", -1)) >= MINCONF
            and len(w["text"]) >= 3 and w["text"].isalpha()]
    conf = [float(w["conf"]) for w in rows if w.get("text", "").strip() and float(w.get("conf", -1)) >= 0]
    return good, (sum(conf) / len(conf) if conf else 0.0)


def one(path):
    tag, page = path.parent.name, int(path.stem[1:])
    im = Image.open(path).convert("L")
    gn, cn = tess(im)
    gm, cm = tess(ImageOps.mirror(im))
    return tag, page, gn, gm, cn, cm


if __name__ == "__main__":
    leafdir, out, nproc = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), int(sys.argv[3])
    files = sorted(leafdir.glob("*/p*.png"))
    (out / "text").mkdir(parents=True, exist_ok=True)
    with open(out / "tess.tsv", "w") as f, Pool(nproc) as pool:
        f.write("tag\tpage\tnorm_words\tmirr_words\tnorm_conf\tmirr_conf\n")
        for tag, page, gn, gm, cn, cm in pool.imap_unordered(one, files):
            f.write(f"{tag}\t{page}\t{len(gn)}\t{len(gm)}\t{cn:.1f}\t{cm:.1f}\n"); f.flush()
            d = out / "text" / tag; d.mkdir(exist_ok=True)
            (d / f"p{page:04d}.txt").write_text(" ".join(w["text"] for w in gn))
