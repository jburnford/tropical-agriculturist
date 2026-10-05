# Full-resolution crop of a leaf (fractions of width/height). Usage: crop.py OUT TAG PAGE x0 y0 x1 y1 [width]
import sys
from PIL import Image, ImageOps
out, tag, pg = sys.argv[1], sys.argv[2], int(sys.argv[3])
x0, y0, x1, y1 = map(float, sys.argv[4:8]); W = int(sys.argv[8]) if len(sys.argv) > 8 else 1000
im = Image.open(f"leaves/full/{tag}/p{pg:04d}.png").convert("L"); w, h = im.size
c = ImageOps.autocontrast(im.crop((int(x0*w), int(y0*h), int(x1*w), int(y1*h))), cutoff=(1, 1))
c.resize((W, int(W * c.size[1] / c.size[0]))).save(out)
