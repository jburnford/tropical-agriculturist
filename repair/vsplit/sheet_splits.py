#!/usr/bin/env python3
"""Contact sheets of tsplit cuts: splits.tsv -> sheet_NN.png (20 per sheet)."""
import sys
from PIL import Image, ImageDraw
TW, TH = 300, 430
splits, leafdir, out = sys.argv[1:4]
rows = [l.rstrip("\n").split("\t") for l in open(splits)]
th = []
for t, p, x, y0, k in rows:
    im = Image.open(f"{leafdir}/{t}/p{int(p):04d}.png").convert("L").convert("RGB")
    d = ImageDraw.Draw(im); x, y0 = int(x), int(y0)
    d.line((0, y0, im.width, y0), fill=(255, 0, 0), width=14)
    d.line((x, y0, x, im.height), fill=(255, 0, 0), width=14)
    th.append((f"{t[:6]} p{p} {k[:6]}", im.resize((TW, TH))))
for k in range(0, len(th), 20):
    s = Image.new("RGB", (5 * TW, 4 * (TH + 18)), "white"); d = ImageDraw.Draw(s)
    for j, (lab, im) in enumerate(th[k:k + 20]):
        cx, cy = (j % 5) * TW, (j // 5) * (TH + 18)
        s.paste(im, (cx, cy + 18)); d.text((cx + 3, cy + 3), lab, fill=(0, 0, 0))
    s.save(f"{out}/sheet_{k // 20 + 1:02d}.png")
print(len(th), "pages,", (len(th) + 19) // 20, "sheets")
