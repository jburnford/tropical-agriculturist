#!/usr/bin/env python3
"""
Full-resolution "leaf" images for items IA holds without scandata/jp2 mapping.

These PDFs (Digital Library of India dli.ernet.*, tdl.*, two 1934-35 issues)
are not IA's mixed-raster derivatives: each page embeds the scan itself at
300-600 dpi. Chandra renders them at ~192 dpi; rendering at the embedded
resolution (short side capped at MAX_SHORT px) recovers what a leaf fetch
gives for the other items.

Usage: render_leaves.py FETCH_LOG... --chunks CHUNKDIR --out LEAFDIR
  reads rows with status NO_SCANDATA from fetch_leaves.py logs
"""
import argparse, glob, pathlib

import pypdfium2 as pdfium
import pypdfium2.raw as R

MAX_SHORT = 2400

ap = argparse.ArgumentParser()
ap.add_argument("logs", nargs="+"); ap.add_argument("--chunks"); ap.add_argument("--out")
a = ap.parse_args()
pdfs = {}
for f in glob.glob(f"{a.chunks}/chunk_*.tsv"):
    for l in open(f):
        t, p = l.split("\t")[:2]; pdfs[t] = p
want = {}
for f in a.logs:
    for l in open(f):
        x = l.rstrip("\n").split("\t")
        if len(x) > 3 and x[3] == "NO_SCANDATA":
            want.setdefault(x[0], set()).add(int(x[1]))
print("tag\tpage\tstatus\tdpi\tsize")
for tag in sorted(want):
    doc = pdfium.PdfDocument(pdfs[tag])
    for p in sorted(want[tag]):
        pg = doc[p]
        imgs = [o.get_metadata() for o in pg.get_objects(filter=[R.FPDF_PAGEOBJ_IMAGE])]
        dpi = max((m.horizontal_dpi for m in imgs), default=0)
        if dpi < 250:
            print(f"{tag}\t{p}\tLOW_RES\t{dpi:.0f}\t"); continue
        short_pt = min(pg.get_width(), pg.get_height())
        dpi = min(dpi, MAX_SHORT / short_pt * 72)
        im = pg.render(scale=dpi / 72).to_pil().convert("RGB")
        dest = pathlib.Path(a.out) / tag / f"p{p:04d}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest)
        print(f"{tag}\t{p}\tRENDERED\t{dpi:.0f}\t{im.size[0]}x{im.size[1]}", flush=True)
    doc.close()
