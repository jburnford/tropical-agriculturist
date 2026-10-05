#!/usr/bin/env python3
"""
Per-page image statistics for every page in the chunk files.

Faded pages are where Chandra hallucinates (vol023 p1001: a full two-column
page read as "20/10/1888 ..." x40). This measures how much the scan itself
says is on the page, independent of the OCR:

  p5, p50, p95   grey-level percentiles (0 black .. 255 white)
  contrast       p50 - p5: paper minus darkest ink. Low = faded or blank.
  ink            fraction of pixels darker than (p50 - 40): rough text area.

Usage: scan_ink.py CHUNKDIR NPROC > ink.tsv
"""
import glob, sys
from multiprocessing import Pool

import pypdfium2 as pdfium


def one_doc(args):
    tag, pdf = args
    rows = []
    doc = pdfium.PdfDocument(pdf)
    for i in range(len(doc)):
        im = doc[i].render(scale=0.5).to_pil().convert("L")
        w, h = im.size
        im = im.crop((w // 20, h // 20, w - w // 20, h - h // 20))  # drop scan borders and edge shadows
        hist = im.histogram()
        n = sum(hist)
        cum, pct = 0, {}
        for v, c in enumerate(hist):
            cum += c
            for q in (5, 50, 95):
                if q not in pct and cum >= n * q / 100:
                    pct[q] = v
        p5, p50, p95 = pct[5], pct[50], pct[95]
        ink = sum(hist[:max(p50 - 40, 0)]) / n
        rows.append(f"{tag}\t{i}\t{p5:.0f}\t{p50:.0f}\t{p95:.0f}\t{p50 - p5:.0f}\t{ink:.4f}")
    doc.close()
    return rows


if __name__ == "__main__":
    docs = []
    for f in sorted(glob.glob(f"{sys.argv[1]}/chunk_*.tsv")):
        for line in open(f):
            tag, pdf = line.split("\t")[:2]
            docs.append((tag, pdf))
    print("tag\tpage\tp5\tp50\tp95\tcontrast\tink")
    with Pool(int(sys.argv[2])) as pool:
        for rows in pool.imap_unordered(one_doc, docs):
            print("\n".join(rows), flush=True)
