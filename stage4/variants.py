# Render enhancement candidates for one page (exact tag) side by side: E (autocontrast), X1 (equalize), X2 (local bg-normalise).
import sys, glob, pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageFilter, ImageChops
pdfs={}
for f in glob.glob("chunks/chunk_*.tsv"):
    for l in open(f):
        t,p=l.split("\t")[:2]; pdfs[t]=p
out, tag, pg = sys.argv[1], sys.argv[2], int(sys.argv[3])
t=[k for k in pdfs if k==tag or k.startswith(tag+"_")]; assert len(t)==1, t
doc=pdfium.PdfDocument(pdfs[t[0]]); p=doc[pg]
dpi=max(1024/min(p.get_width(),p.get_height())*72,192)
g=p.render(scale=dpi/72).to_pil().convert("L")
E=ImageOps.autocontrast(g,cutoff=(1,1))
X1=ImageOps.equalize(g)
bg=g.filter(ImageFilter.GaussianBlur(25))
X2=ImageOps.autocontrast(ImageChops.add(ImageChops.subtract(bg,g),Image.new("L",g.size,0),scale=1.0).point(lambda v:255-v),cutoff=(0.5,0.5))
w,h=g.size; box=(int(w*.08),int(h*.15),int(w*.6),int(h*.35))
tiles=[im.crop(box) for im in (g,E,X1,X2)]
S=Image.new("L",(tiles[0].size[0]*2,tiles[0].size[1]*2),255)
for i,tl in enumerate(tiles): S.paste(tl,((i%2)*tl.size[0],(i//2)*tl.size[1]))
S.save(out)
