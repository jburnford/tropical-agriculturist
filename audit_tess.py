#!/usr/bin/env python3
"""
Corpus-wide Tesseract pass for the Stage 4 audit: every page of every PDF.

The repair list only covered pages that LOOKED suspicious (capped, looping,
faint). A fluent hallucination on a normal-contrast page shows none of those
signs. Tesseract does not invent text, so for every page we record the
words it reads with confidence; audit_compare.py then flags any page whose
corpus text does not contain them.

Pages are rendered at 300 dpi greyscale into node-local scratch and passed to
one tesseract call per 25-page chunk (a list file; the TSV's page_num maps
rows back to pages). One worker per core, OMP_THREAD_LIMIT=1.

Per page writes OUT/<tag>/pNNNN.txt: confident words (conf >= 70, alphabetic,
>= 3 letters) in reading order. Per chunk appends to OUT/_counts/<tag>.tsv:
page, confident words, all words.

With MIRROR=1 in the environment every page is flipped left-right before
OCR: a page whose only legible print is show-through from the reverse of the
sheet reads well mirrored and badly as scanned (stage 4 found such pages above
the contrast cut-off, e.g. vol022 p893).

Usage (in a CPU job): [MIRROR=1] audit_tess.py CHUNKDIR OUT NPROC
"""
import csv, glob, io, os, pathlib, subprocess, sys, tempfile
from multiprocessing import Pool

import pypdfium2 as pdfium
from PIL import ImageOps

SIF = "/scratch/jic823/containers/tesseract.sif"
DPI, STEP, MINCONF = 300, 25, 70


def work(job):
    tag, pdf, start, end, out = job
    done = pathlib.Path(out) / "_counts" / f"{tag}.{start:05d}.tsv"
    if done.exists():
        return tag, start, "cached"
    tmp = tempfile.mkdtemp(dir=os.environ.get("SLURM_TMPDIR", "/tmp"))
    doc = pdfium.PdfDocument(pdf)
    paths = []
    for p in range(start, end):
        f = f"{tmp}/p{p:05d}.png"
        im = doc[p].render(scale=DPI / 72, grayscale=True).to_pil()
        if os.environ.get("MIRROR") == "1":
            im = ImageOps.mirror(im)
        im.save(f)
        paths.append(f)
    doc.close()
    lst = f"{tmp}/list.txt"
    open(lst, "w").write("\n".join(paths) + "\n")
    r = subprocess.run(["apptainer", "exec", SIF, "tesseract", lst, "-", "--psm", "3", "tsv"],
                       capture_output=True, text=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    per = {i: [] for i in range(len(paths))}
    allw = {i: 0 for i in range(len(paths))}
    for w in csv.DictReader(io.StringIO(r.stdout), delimiter="\t", quoting=csv.QUOTE_NONE):
        t = (w.get("text") or "").strip()
        if not t:
            continue
        i = int(w["page_num"]) - 1
        allw[i] += 1
        if float(w["conf"]) >= MINCONF and len(t) >= 3 and t.isalpha():
            per[i].append(t)
    d = pathlib.Path(out) / tag
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, p in enumerate(range(start, end)):
        (d / f"p{p:04d}.txt").write_text(" ".join(per[i]))
        rows.append(f"{p}\t{len(per[i])}\t{allw[i]}\n")
    for f in paths + [lst]:
        os.remove(f)
    os.rmdir(tmp)
    done.write_text("".join(rows))
    return tag, start, "ok" if r.returncode == 0 else f"rc={r.returncode} {r.stderr[:200]}"


if __name__ == "__main__":
    chunkdir, out, nproc = sys.argv[1], sys.argv[2], int(sys.argv[3])
    (pathlib.Path(out) / "_counts").mkdir(parents=True, exist_ok=True)
    jobs = []
    for f in sorted(glob.glob(f"{chunkdir}/chunk_*.tsv")):
        for line in open(f):
            tag, pdf, n = line.rstrip("\n").split("\t")[:3]
            for s in range(0, int(n), STEP):
                jobs.append((tag, pdf, s, min(s + STEP, int(n)), out))
    jobs.sort(key=lambda j: -(j[3] - j[2]))
    print(f"{len(jobs)} chunks", flush=True)
    bad = 0
    with Pool(nproc) as pool:
        for k, (tag, s, st) in enumerate(pool.imap_unordered(work, jobs), 1):
            if st not in ("ok", "cached"):
                bad += 1
                print(f"FAIL {tag} {s} {st}", flush=True)
            if k % 200 == 0:
                print(f"{k}/{len(jobs)}", flush=True)
    print(f"done {len(jobs)} chunks, {bad} failed", flush=True)
