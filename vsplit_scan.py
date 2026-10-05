#!/usr/bin/env python3
"""
Run vsplit.gutter over a page list and draw contact sheets of the cuts.

Usage: vsplit_scan.py DECISIONS_TSV LEAFDIR OUTDIR [ACTION]
  DECISIONS_TSV  stage4 decisions (tag, page, ..., action); rows with
                 action == ACTION (default ACCEPT_TABLE) are scanned
Writes OUTDIR/gutters.tsv (tag page x y0 xfrac y0frac, or "-" for none) and
OUTDIR/sheet_NN.png: 20 thumbnails per sheet, cuts in red, labelled.
"""
import csv, pathlib, sys
from multiprocessing import Pool

from PIL import Image, ImageDraw

import vsplit

TW, TH = 300, 430


def one(args):
    tag, page, leafdir = args
    f = pathlib.Path(leafdir) / tag / f"p{int(page):04d}.png"
    if not f.exists():
        return tag, page, None, None
    im = Image.open(f).convert("RGB")
    g = vsplit.gutter(im)
    th = im.convert("L").convert("RGB")
    if g:
        x, y0 = g
        d = ImageDraw.Draw(th)
        d.line((0, y0, im.width, y0), fill=(255, 0, 0), width=14)
        d.line((x, y0, x, im.height), fill=(255, 0, 0), width=14)
    th = th.resize((TW, TH))
    return tag, page, g, (im.width, im.height, th.tobytes())


def main(dec, leafdir, outdir, action="ACCEPT_TABLE"):
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    rows = [(r["tag"], r["page"], leafdir) for r in csv.DictReader(open(dec), delimiter="\t")
            if r["action"] == action]
    with Pool(4) as p:
        res = p.map(one, rows)
    with open(out / "gutters.tsv", "w") as fh:
        for tag, page, g, info in res:
            if info is None:
                fh.write(f"{tag}\t{page}\tNOLEAF\n"); continue
            w, h, _ = info
            fh.write(f"{tag}\t{page}\t" + (f"{g[0]}\t{g[1]}\t{g[0]/w:.2f}\t{g[1]/h:.2f}" if g else "-") + "\n")
    thumbs = [(t, p, g, Image.frombytes("RGB", (TW, TH), i[2])) for t, p, g, i in res if i]
    for k in range(0, len(thumbs), 20):
        sheet = Image.new("RGB", (5 * TW, 4 * (TH + 18)), "white")
        d = ImageDraw.Draw(sheet)
        for j, (t, p, g, im) in enumerate(thumbs[k:k + 20]):
            cx, cy = (j % 5) * TW, (j // 5) * (TH + 18)
            sheet.paste(im, (cx, cy + 18))
            d.text((cx + 3, cy + 3), f"{t[:14]} p{p} {'SPLIT' if g else '-'}", fill=(0, 0, 0))
        sheet.save(out / f"sheet_{k // 20 + 1:02d}.png")
    n = sum(1 for _, _, g, i in res if g)
    print(f"{len(res)} pages, {n} with a gutter, {sum(1 for r in res if r[3] is None)} without a leaf")


if __name__ == "__main__":
    main(*sys.argv[1:])
