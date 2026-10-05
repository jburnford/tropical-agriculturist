# Contact sheet of full-res leaves (top 45%, autocontrast) for exact tag:page pairs. Usage: sheet_leaf.py OUT.png TAG:PAGE...
import sys
from PIL import Image, ImageOps, ImageDraw
tiles = []
for a in sys.argv[2:]:
    tag, pg = a.rsplit(":", 1)
    im = Image.open(f"leaves/full/{tag}/p{int(pg):04d}.png").convert("L")
    w, h = im.size
    im = ImageOps.autocontrast(im.crop((0, 0, w, int(h * .45))), cutoff=(1, 1))
    im = im.resize((520, int(520 * im.size[1] / w)))
    d = ImageDraw.Draw(im); d.rectangle((0, 0, 250, 22), fill=255); d.text((4, 4), f"{tag[:22]} p{pg}", fill=0)
    tiles.append(im)
H = max(t.size[1] for t in tiles); rows = (len(tiles) + 3) // 4
S = Image.new("L", (520 * 4, H * rows), 255)
for i, t in enumerate(tiles):
    S.paste(t, ((i % 4) * 520, (i // 4) * H))
S.save(sys.argv[1])
