#!/usr/bin/env python3
"""
Pack pages that need re-reading into multi-page PDFs for one batched Chandra run.

Chandra processes a directory of images one file at a time (batch of 1), so
2,000 loose PNGs would run serially. A multi-page PDF goes through its normal
batched path instead.

Every image is embedded at 192 dpi. Its short side is >= 1024 px, so
Chandra's own render of the packed PDF (dpi = max(192, 1024 px on the short
side), chandra/input.py) comes back at 192 dpi -- i.e. exactly these pixels.

Variants (the letter prefixes the PDF name; repair_decide.py reads it):
  O   PDF page render, untouched            -- capped pages, higher token cap
  E   PDF page render, autocontrast          -- faded pages
  J   full-resolution IA leaf (fetch_leaves.py), untouched
  K   full-resolution leaf, autocontrast     -- second reading of a leaf
  M   full-resolution leaf, mirrored left-right: a show-through page reads as
      the reverse side of its sheet, so M text matching a neighbour page
      shows the page itself is blank
  H   full-resolution leaf (else PDF render) cut into top and bottom halves at
      the emptiest row near the middle -- for pages that still loop at 32k.
      Two PDF pages per input page; index column 4 = part 1/2.
  Q   as H, but the halves of the autocontrast leaf -- a second, independent
      half-page reading for faint dense tables
  T   full-resolution leaf (else PDF render) cut into three horizontal strips
      at the emptiest rows near 1/3 and 2/3 -- for dense tables Chandra
      summarises ("Table with 4 columns ... Includes categories like ...")
      instead of transcribing. Index column 4 = part 1/2/3.
  V   full-resolution leaf of a SIDE-BY-SIDE table page (Produce Sales List,
      Market Rates, Ceylon Rainfall: two copies of one table printed next to
      each other) cut at the division found by tsplit.py from Tesseract word
      boxes: full-width top strip (title, running head) if any, then the left
      column in two halves, then the right column in two halves. Read whole,
      Chandra pairs an unrelated left and right record on every row. Needs
      env VSPLIT = TSV of tag, page, x, y0 (pixels of the leaf); pages
      without a row are skipped. Index column 4 = part 1..5.

Usage: build_repair_pdfs.py REPAIR_LIST OUTDIR VARIANT [PAGES_PER_PDF] [LEAFDIR]
  REPAIR_LIST rows: tag, page (0-based), pdf, reason
Writes OUTDIR/<VARIANT>_NNN.pdf and OUTDIR/<VARIANT>_NNN.index.tsv
(index row i = PDF page i: tag, page, reason[, part]).
"""
import os, pathlib, sys

import pypdfium2 as pdfium
from PIL import Image, ImageOps

IMAGE_DPI, MIN_DIM = 192, 1024          # chandra settings.IMAGE_DPI / MIN_PDF_IMAGE_DIM


def render(pdf, page):
    doc = pdfium.PdfDocument(pdf)
    p = doc[page]
    dpi = max(MIN_DIM / min(p.get_width(), p.get_height()) * 72, IMAGE_DPI)
    im = p.render(scale=dpi / 72).to_pil().convert("RGB")
    doc.close()
    return im


def strips(im, n):
    """Cut into n strips, each cut at the lightest horizontal band within
    +-15% of the height around k/n."""
    g = im.convert("L").resize((200, im.height // 4))
    h = g.height
    rows = [sum(g.crop((0, y, 200, y + 1)).tobytes()) for y in range(h)]
    win, cuts = 3, [0]
    for k in range(1, n):
        lo, hi = int(h * (k / n - .15)), int(h * (k / n + .15))
        best = max(range(lo, hi - win), key=lambda y: sum(rows[y:y + win]))
        cuts.append((best + win // 2) * 4)
    cuts.append(im.height)
    return [im.crop((0, a, im.width, b)) for a, b in zip(cuts, cuts[1:])]


def halves(im):
    return strips(im, 2)


def fit(im):
    if min(im.size) < MIN_DIM:          # keep Chandra from rescaling the packed page
        s = MIN_DIM / min(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.Resampling.LANCZOS)
    return im


_VSPLIT = None


def vsplit_geometry(tag, page):
    global _VSPLIT
    if _VSPLIT is None:
        _VSPLIT = {}
        for l in open(os.environ["VSPLIT"]):
            t, p, x, y0 = l.rstrip("\n").split("\t")[:4]
            _VSPLIT[(t, int(p))] = (int(x), int(y0))
    return _VSPLIT.get((tag, int(page)))


def pad(im):
    """Pad a thin full-width strip with white up to MIN_DIM tall, instead of
    fit()'s upscaling: a 280 px title strip would otherwise become ~8,500 px
    wide at 3.7x, over Chandra's pixel budget."""
    if im.height >= MIN_DIM:
        return im
    out = Image.new("RGB", (im.width, MIN_DIM), "white")
    out.paste(im, (0, 0))
    return out


def side_by_side(im, x, y0):
    out = []
    if y0 > im.height * 0.02:
        out.append(pad(im.crop((0, 0, im.width, y0))))
    for a, b in ((0, x), (x, im.width)):
        out += halves(im.crop((a, y0, b, im.height)))
    return out


def images_for(variant, tag, page, pdf, leafdir):
    leaf = leafdir / tag / f"p{int(page):04d}.png" if leafdir else None
    if variant == "V":
        g = vsplit_geometry(tag, page)
        if not (g and leaf and leaf.exists()):
            return None
        return [fit(x) for x in side_by_side(Image.open(leaf).convert("RGB"), *g)]
    if variant in "JKM":
        if not (leaf and leaf.exists()):
            return None
        im = Image.open(leaf).convert("RGB")
        if variant == "K":
            im = ImageOps.autocontrast(im.convert("L"), cutoff=(1, 1)).convert("RGB")
        if variant == "M":
            im = ImageOps.mirror(im)
        return [im]
    if variant == "T":
        im = Image.open(leaf).convert("RGB") if leaf and leaf.exists() else render(pdf, int(page))
        return [fit(x) for x in strips(im, 3)]
    if variant in "HQ":
        im = Image.open(leaf).convert("RGB") if leaf and leaf.exists() else render(pdf, int(page))
        if variant == "Q":
            im = ImageOps.autocontrast(im.convert("L"), cutoff=(1, 1)).convert("RGB")
        return [fit(h) for h in halves(im)]
    im = render(pdf, int(page))
    if variant == "E":
        im = ImageOps.autocontrast(im.convert("L"), cutoff=(1, 1)).convert("RGB")
    return [im]


def main(listfile, outdir, variant, per=250, leafdir=None):
    rows = [l.rstrip("\n").split("\t")[:4] for l in open(listfile) if l.strip()]
    outdir = pathlib.Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    leafdir = pathlib.Path(leafdir) if leafdir else None
    k, skipped = 0, 0
    while rows:
        stem = outdir / f"{variant}_{k + 1:03d}"
        imgs, index = [], []
        while rows and len(imgs) < per:
            tag, page, pdf, why = rows.pop(0)
            got = images_for(variant, tag, page, pdf, leafdir)
            if got is None:
                skipped += 1; continue
            for part, im in enumerate(got, 1):
                imgs.append(im)
                index.append(f"{tag}\t{page}\t{why}" + (f"\t{part}" if len(got) > 1 else ""))
        if not imgs:
            break
        imgs[0].save(f"{stem}.pdf", save_all=True, append_images=imgs[1:],
                     resolution=IMAGE_DPI, quality=95)
        open(f"{stem}.index.tsv", "w").write("\n".join(index) + "\n")
        print(f"{stem}.pdf {len(imgs)} pages")
        k += 1
    if skipped:
        print(f"skipped {skipped} rows with no leaf image")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], int(a[3]) if len(a) > 3 else 250, a[4] if len(a) > 4 else None)
