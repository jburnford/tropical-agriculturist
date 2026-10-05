#!/usr/bin/env python3
"""
Fetch full-resolution page images from the Internet Archive for selected pages.

The PDFs we OCR are IA's mixed-raster derivatives: a sharp ~350 dpi foreground
mask over a ~117 dpi JPEG-2000 background. IA's segmenter puts faint print in
the *background*, so on faded pages and show-through versos the PDF has
blurred the text away (vol012 p15, vol022 p979). The item's
<id>_jp2.zip holds the processed full-resolution page images, in which that
text is legible (and show-through is visibly mirror-reversed).

PDF page i -> scan leaf: the i-th <page> in <id>_scandata.xml whose
addToAccessFormats is not "false". The mapping is only trusted when the
access-leaf count equals the PDF's page count, and every fetched leaf is
checked against the PDF render of the same page (thumbnail correlation >=
MIN_CORR); a leaf that does not match is reported and not written.

Usage: fetch_leaves.py PAGE_LIST TAG_IDENT CHUNKDIR OUTDIR
  PAGE_LIST rows: tag, page (0-based), ...
Writes OUTDIR/<tag>/p<NNNN>.png and prints one status row per page.
"""
import csv, glob, io, pathlib, subprocess, sys, time, urllib.parse
import xml.etree.ElementTree as ET

import pypdfium2 as pdfium
from PIL import Image, ImageOps

MIN_CORR = 0.80
DL = "https://archive.org/download/{id}/{f}"


def curl(url, tries=4):
    for k in range(tries):
        r = subprocess.run(["curl", "-sSfL", "-m", "120", url], capture_output=True)
        if r.returncode == 0 and r.stdout:
            return r.stdout
        time.sleep(3 * (k + 1))
    raise RuntimeError(f"fetch failed: {url}: {r.stderr.decode()[:200]}")


def access_leaves(ident, cache):
    f = cache / f"{ident}_scandata.xml"
    if not f.exists():
        f.write_bytes(curl(DL.format(id=urllib.parse.quote(ident), f=f"{ident}_scandata.xml")))
    leaves = []
    for p in ET.parse(f).getroot().iter("page"):
        a = p.findtext("addToAccessFormats")
        if a is None or a.strip().lower() != "false":
            leaves.append(int(p.get("leafNum")))
    return leaves


def thumb(im):
    return ImageOps.autocontrast(im.convert("L").resize((64, 96)))


def corr(a, b):
    xa, xb = list(a.tobytes()), list(b.tobytes())   # mode L: one byte per pixel
    n = len(xa); ma, mb = sum(xa) / n, sum(xb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(xa, xb))
    va = sum((x - ma) ** 2 for x in xa) ** .5; vb = sum((y - mb) ** 2 for y in xb) ** .5
    return cov / (va * vb) if va and vb else 0.0


def main(page_list, tag_ident, chunkdir, outdir):
    ident = dict(l.rstrip("\n").split("\t") for l in open(tag_ident))
    pdf, npages = {}, {}
    for f in glob.glob(f"{chunkdir}/chunk_*.tsv"):
        for l in open(f):
            t, p, n = l.rstrip("\n").split("\t")[:3]
            pdf[t], npages[t] = p, int(n)
    want = {}
    for row in csv.reader(open(page_list), delimiter="\t"):
        want.setdefault(row[0], set()).add(int(row[1]))
    out = pathlib.Path(outdir); cache = out / "_scandata"; cache.mkdir(parents=True, exist_ok=True)
    print("tag\tpage\tleaf\tstatus\tcorr\tsize")
    for tag in sorted(want):
        idn = ident[tag]
        try:
            leaves = access_leaves(idn, cache)
        except Exception as e:
            for p in sorted(want[tag]): print(f"{tag}\t{p}\t\tNO_SCANDATA\t\t{e}")
            continue
        if len(leaves) != npages[tag]:
            for p in sorted(want[tag]):
                print(f"{tag}\t{p}\t\tCOUNT_MISMATCH\t\taccess={len(leaves)} pdf={npages[tag]}")
            continue
        doc = pdfium.PdfDocument(pdf[tag])
        for p in sorted(want[tag]):
            dest = out / tag / f"p{p:04d}.png"
            if dest.exists():
                print(f"{tag}\t{p}\t{leaves[p]}\tCACHED\t\t"); continue
            leaf = leaves[p]
            member = f"{idn}_jp2/{idn}_{leaf:04d}.jp2"
            try:
                data = curl(DL.format(id=urllib.parse.quote(idn),
                                      f=urllib.parse.quote(f"{idn}_jp2.zip") + "/" + urllib.parse.quote(member, safe="")))
                im = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception as e:
                print(f"{tag}\t{p}\t{leaf}\tFETCH_FAIL\t\t{str(e)[:120]}"); continue
            ref = doc[p].render(scale=0.5).to_pil()
            c = corr(thumb(im), thumb(ref))
            if c < MIN_CORR:
                print(f"{tag}\t{p}\t{leaf}\tMISMATCH\t{c:.2f}\t{im.size}"); continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            im.save(dest)
            print(f"{tag}\t{p}\t{leaf}\tOK\t{c:.2f}\t{im.size[0]}x{im.size[1]}", flush=True)
        doc.close()


if __name__ == "__main__":
    main(*sys.argv[1:5])
