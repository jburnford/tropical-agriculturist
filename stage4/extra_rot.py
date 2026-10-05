# For audit EXTRA pages: Tesseract on the PDF render at 90/180/270 degrees; best rotation's
# confident content words vs corpus text (recall). Usage: extra_rot.py CORPUS AUDIT_TSV NPROC > out.tsv
import csv, glob, io, pathlib, re, subprocess, sys, tempfile
from multiprocessing import Pool
sys.path.insert(0, "/scratch/jic823/tropical")
from audit_compare import text_words, recall, content
from repair_compare import load
import pypdfium2 as pdfium

SIF = "/scratch/jic823/containers/tesseract.sif"
pdfs = {}
for f in glob.glob("chunks/chunk_*.tsv"):
    for l in open(f):
        t, p = l.split("\t")[:2]; pdfs[t] = p


def tess(img):
    with tempfile.NamedTemporaryFile(suffix=".png", dir="/scratch/jic823/tmp") as f:
        img.save(f.name)
        r = subprocess.run(["apptainer", "exec", SIF, "tesseract", f.name, "-", "--psm", "3", "tsv"],
                           capture_output=True, text=True)
    rows = csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE)
    return [w["text"].lower() for w in rows if w.get("text") and float(w.get("conf", -1)) >= 70
            and len(w["text"]) >= 3 and w["text"].isalpha()]


def one(job):
    corpus, t, p = job
    doc = pdfium.PdfDocument(pdfs[t]); im = doc[p].render(scale=300 / 72, grayscale=True).to_pil(); doc.close()
    txt = load(pathlib.Path(corpus, t))[0][p]
    xw = text_words(txt)
    best = (0, 0, 0.0)
    for ang in (90, 180, 270):
        tw = content(tess(im.rotate(ang, expand=True)))
        r = recall(tw, xw) if tw else 0.0
        if len(tw) > best[1]:
            best = (ang, len(tw), r)
    return f"{t}\t{p}\t{best[0]}\t{best[1]}\t{best[2]:.2f}\t{int('![' in txt)}\t{len(xw)}"


if __name__ == "__main__":
    corpus, aud, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    jobs = [(corpus, r["tag"], int(r["page"])) for r in csv.DictReader(open(aud), delimiter="\t")
            if r["flag"] == "EXTRA" and not r["stage4"]]
    print("tag\tpage\tbest_angle\trot_words\trot_recall\thas_image\ttext_words")
    with Pool(n) as pool:
        for row in pool.imap_unordered(one, jobs):
            print(row, flush=True)
